"""Every number of the v3 campaign, computed once from the compacted cells.

Reads artifacts/v3_compact (written by analysis.v3_compact) and writes
    artifacts/v3_analysis.json   every statistic, for the report and the figures
    paper/tables_v3/*.csv         every table, in percent

All rates are percentages. Statistics:
  * mean and sample SD over the three runs of the main matrix
  * flip rate: share of questions whose grade differs between at least two runs
  * paired difference with a question-level (cluster) bootstrap 95% interval,
    5,000 resamples; a question keeps all its runs (and models) when resampled
  * exact two-sided McNemar test per run, Holm-corrected within each family
  * RQ4 ranking agreement: Kendall tau-b, Spearman rho, Pearson r, each with an
    exact one-sided permutation p over all 720 orderings of six policies

Usage:
    python -m analysis.v3_analysis
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

from analysis.final_report import holm, mcnemar

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "artifacts/v3_compact"
TAB = ROOT / "paper/tables_v3"
OUT = ROOT / "artifacts/v3_analysis.json"
BENCH = {"mquake_t": "MQuAKE-T", "factconsolidation": "FactConsolidation", "convomem": "ConvoMem"}
DATA = {"mquake_t": "data/mquake_t_sh.json", "factconsolidation": "data/factconsolidation_sh_6k.json",
        "convomem": "data/convomem_changing.json"}
MODELS = {"openai_gpt-6.1-sol": "GPT-6.1 Sol", "anthropic_claude-sonnet-5.5": "Claude Sonnet 5.5",
          "google_gemini-3.8-flash": "Gemini 3.8 Flash", "qwen_qwen3-14b": "Qwen3 14B",
          "meta-llama_llama-3.1-8b-instruct": "Llama 3.1 8B"}
SPEC = {k: "openrouter:" + k.replace("_", "/", 1) for k in MODELS}
TIER = {"openai_gpt-6.1-sol": "frontier", "anthropic_claude-sonnet-5.5": "frontier",
        "google_gemini-3.8-flash": "mid", "qwen_qwen3-14b": "small", "meta-llama_llama-3.1-8b-instruct": "small"}
PRICE = {"openai_gpt-6.1-sol": (2.0, 10.0), "anthropic_claude-sonnet-5.5": (2.0, 10.0),
         "google_gemini-3.8-flash": (0.75, 3.75), "qwen_qwen3-14b": (0.12, 0.24),
         "meta-llama_llama-3.1-8b-instruct": (0.02, 0.04)}
POL = ["NOMEM", "P0", "P1", "P2", "P3", "P4", "P5"]
RANKED = ["P0", "P1", "P2", "P3", "P4", "P5"]
RUNS = (1, 2, 3)
BOOT, SEED = 5000, 7


def pct(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(100 * x, 2)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    xs = list(xs)
    return st.stdev(xs) if len(xs) > 1 else 0.0


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


_CACHE: dict = {}


def cell(run, b, p, m):
    k = (run, b, p, m)
    if k not in _CACHE:
        _CACHE[k] = load(C / f"run{run}/main_{b}/{p}__openrouter_{m}.json")
    return _CACHE[k]


def qkey(r):
    return (r.get("conversation"), r["question"])


def cluster_boot(diffs_by_q: dict, n=BOOT):
    """Mean difference and 95% interval, resampling questions (each keeps all its values)."""
    keys = list(diffs_by_q)
    vals = [diffs_by_q[k] for k in keys]
    tot = sum(sum(v) for v in vals) / sum(len(v) for v in vals)
    rng = random.Random(SEED)
    ms = []
    for _ in range(n):
        s = c = 0
        for _ in keys:
            v = vals[rng.randrange(len(keys))]
            s += sum(v)
            c += len(v)
        ms.append(s / c)
    ms.sort()
    return tot, ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


# --------------------------------------------------------------------- metrics

def metrics(c, m):
    rr = c["records"]
    n = len(rr)
    acc = mean(float(r["correct"]) for r in rr)
    stale = mean(float(r["stale"]) for r in rr)
    known = [r for r in rr if r.get("_ctx_known") and r.get("_stale_answer")]
    exp = [r for r in known if r.get("stale_in_ctx")]
    pt = mean(r.get("prompt_tokens") or r.get("tokens") or 0 for r in rr)
    ctok = mean(r.get("completion_tokens") or 0 for r in rr)
    pin, pout = PRICE[m]
    usd = sum((r.get("prompt_tokens") or 0) * pin + (r.get("completion_tokens") or 0) * pout for r in rr) / 1e6
    tot = c["summary"].get("memory_totals") or {}
    wrong = [r for r in rr if not r["correct"]]
    gk = [r for r in wrong if r.get("gold_in_ctx") is not None]
    return {
        "n": n, "accuracy": acc, "staleness": stale,
        "mentions_old": mean(float(bool(r.get("mentions_old"))) for r in rr),
        "f1": mean(r.get("f1") or 0 for r in rr),
        "exposure": mean(float(bool(r["stale_in_ctx"])) for r in known) if known else None,
        "reading_error": mean(float(r["stale"]) for r in exp) if exp else None,
        "reading_n": len(exp),
        "closed_in_context": mean(r.get("retrieved_invalidated") or 0 for r in rr),
        "prompt_tokens": pt, "completion_tokens": ctok,
        "usd_per_1k_correct": usd / (acc * n) * 1000 if acc else None,
        "facts_total": tot.get("total_facts"), "facts_active": tot.get("active_facts"),
        "facts_closed": tot.get("closed_total"), "facts_pruned": tot.get("pruned"),
        "write_rejections": tot.get("write_rejections"),
        "wrong_gold_absent": mean(float(not r["gold_in_ctx"]) for r in gk) if gk else None,
        "judge_override": mean(float(bool(r["correct"]) != bool(r.get("judge_correct", r["correct"]))) for r in rr),
    }


def agg(vals):
    vals = [v for v in vals if v is not None and v == v]
    if not vals:
        return {"mean": None, "sd": None, "min": None, "max": None, "runs": []}
    return {"mean": mean(vals), "sd": sd(vals), "min": min(vals), "max": max(vals), "runs": vals}


# ------------------------------------------------------------------ forgetting

def slot(f, value, question):
    text, q = (f.get("text") or "").lower(), question.lower()
    if value not in text:
        return False
    s, o = (f.get("subject") or "").lower().strip(), (f.get("object") or "").lower().strip()
    other = s if value in o else o
    return len(other) > 2 and other in q


def visible(facts, hide_closed):
    return [f for f in facts if f.get("active", True) and not (hide_closed and f.get("t_invalid_at"))]


def correctness(ref_graphs, graphs, qs, hide_closed):
    """complete = old value no longer visible; sound = current value still visible."""
    n_old = vis_old = n_cur = vis_cur = 0
    for cid, q in qs:
        ref = ref_graphs.get(cid) or ref_graphs.get("_all") or []
        g = visible(graphs.get(cid) or graphs.get("_all") or [], hide_closed)
        cur = (q.get("current_answer") or q["answer"]).lower()
        old = q["stale_answer"].lower()
        if any(slot(f, old, q["question"]) for f in ref):
            n_old += 1
            vis_old += any(slot(f, old, q["question"]) and cur not in f["text"].lower() for f in g)
        if any(slot(f, cur, q["question"]) for f in ref):
            n_cur += 1
            vis_cur += any(slot(f, cur, q["question"]) for f in g)
    return {"n_old": n_old, "n_cur": n_cur,
            "complete": 1 - vis_old / n_old if n_old else None,
            "sound": vis_cur / n_cur if n_cur else None}


def stale_questions(b):
    data = json.loads((ROOT / DATA[b]).read_text())
    return [(c["id"], q) for c in data["conversations"] for q in c["questions"] if q.get("stale_answer")]


# ------------------------------------------------------------------ rankings

def ranks(xs):
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float("nan")


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def kendall_tau_b(a, b):
    nc = nd = ta = tb = 0
    for i, j in itertools.combinations(range(len(a)), 2):
        da, db = a[i] - a[j], b[i] - b[j]
        if da == 0 and db == 0:
            continue
        if da == 0:
            ta += 1
        elif db == 0:
            tb += 1
        elif da * db > 0:
            nc += 1
        else:
            nd += 1
    den = math.sqrt((nc + nd + ta) * (nc + nd + tb))
    return (nc - nd) / den if den else float("nan")


def perm_p(fn, a, b):
    """Exact one-sided p: share of all orderings of b at least as concordant as observed."""
    obs = fn(a, b)
    if math.isnan(obs):
        return obs, float("nan")
    perms = list(itertools.permutations(b))
    hits = sum(1 for p in perms if fn(a, list(p)) >= obs - 1e-12)
    return obs, hits / len(perms)


def agreement(a, b):
    out = {}
    for name, fn in (("kendall_tau", kendall_tau_b), ("spearman", spearman), ("pearson", pearson)):
        v, p = perm_p(fn, a, b)
        out[name] = round(v, 4)
        out[name + "_p"] = round(p, 4)
    return out


# ------------------------------------------------------------------ main matrix

def main_matrix(res):
    res["cells"] = {}
    res["policy_avg"] = {}
    res["flip"] = {}
    qsets = {b: stale_questions(b) for b in BENCH}
    res["correctness"] = {}
    for b in BENCH:
        for p in POL:
            for m in MODELS:
                ms = [metrics(c, m) for c in (cell(r, b, p, m) for r in RUNS) if c]
                if not ms:
                    continue
                res["cells"][f"{b}|{p}|{m}"] = {k: agg([x[k] for x in ms]) for k in ms[0] if k != "reading_n"}
                res["cells"][f"{b}|{p}|{m}"]["reading_n"] = sum(x["reading_n"] for x in ms)
                # flips across runs
                grades = defaultdict(list)
                for r in RUNS:
                    c = cell(r, b, p, m)
                    for x in c["records"]:
                        grades[qkey(x)].append(bool(x["correct"]))
                flips = [len(set(v)) > 1 for v in grades.values() if len(v) == 3]
                res["flip"][f"{b}|{p}|{m}"] = mean(float(f) for f in flips)
            # policy average over models, per run, then mean/SD over runs
            per_run = defaultdict(list)
            for r in RUNS:
                for m in MODELS:
                    c = cell(r, b, p, m)
                    if c:
                        per_run[r].append(metrics(c, m))
            keys = ["accuracy", "staleness", "mentions_old", "f1", "exposure", "reading_error",
                    "prompt_tokens", "usd_per_1k_correct", "facts_active", "facts_total", "closed_in_context"]
            res["policy_avg"][f"{b}|{p}"] = {
                k: agg([mean(x[k] for x in per_run[r] if x[k] is not None) for r in per_run]) for k in keys}
        # forgetting correctness (per run, mean over models)
        for p in RANKED:
            per = []
            for r in RUNS:
                vals = []
                for m in MODELS:
                    ref, g = cell(r, b, "P0", m), cell(r, b, p, m)
                    if ref and g and ref.get("graphs") and g.get("graphs"):
                        vals.append(correctness(ref["graphs"], g["graphs"], qsets[b], p == "P2"))
                if vals:
                    per.append({"complete": mean(v["complete"] for v in vals if v["complete"] is not None),
                                "sound": mean(v["sound"] for v in vals if v["sound"] is not None),
                                "n_old": mean(v["n_old"] for v in vals), "n_cur": mean(v["n_cur"] for v in vals)})
            res["correctness"][f"{b}|{p}"] = {k: agg([x[k] for x in per]) for k in ("complete", "sound", "n_old", "n_cur")}
        # extraction per run (from P0 GPT cell)
        res.setdefault("extraction", {})[b] = []
        for r in RUNS:
            c = cell(r, b, "P0", "openai_gpt-6.1-sol")
            t = c["summary"].get("memory_totals") or {}
            res["extraction"][b].append({"run": r, "facts": t.get("total_facts"), "closed": t.get("closed_total"),
                                         "parse_fail": (c["summary"].get("extraction_parse_failures") or {})})


def paired(res):
    """P2 against every other policy: per model and pooled over models."""
    res["paired"] = []
    for b in BENCH:
        fam = []
        for other in [p for p in POL if p != "P2"]:
            for m in list(MODELS) + ["ALL"]:
                ms = list(MODELS) if m == "ALL" else [m]
                diffs = defaultdict(list)
                pvals = []
                for r in RUNS:
                    a_all, o_all = [], []
                    for mm in ms:
                        a, o = cell(r, b, "P2", mm), cell(r, b, other, mm)
                        if not (a and o):
                            continue
                        om = {qkey(x): x for x in o["records"]}
                        for x in a["records"]:
                            y = om.get(qkey(x))
                            if y is None:
                                continue
                            diffs[(qkey(x), mm)].append(float(x["correct"]) - float(y["correct"]))
                            a_all.append(bool(x["correct"]))
                            o_all.append(bool(y["correct"]))
                    if a_all:
                        pvals.append(mcnemar(o_all, a_all))
                if not diffs:
                    continue
                # cluster on the question (pooled models share the question cluster)
                byq = defaultdict(list)
                for (q, mm), v in diffs.items():
                    byq[q].extend(v)
                d, lo, hi = cluster_boot(byq)
                fam.append({"benchmark": b, "other": other, "model": m, "diff": d, "lo": lo, "hi": hi,
                            "mcnemar": [{"p2_only": y, "other_only": x, "p": p} for x, y, p in pvals]})
        # Holm within benchmark, separately for each run
        for r_i in range(3):
            ps = [f["mcnemar"][r_i]["p"] if len(f["mcnemar"]) > r_i else 1.0 for f in fam]
            adj = holm(ps)
            for f, a in zip(fam, adj):
                if len(f["mcnemar"]) > r_i:
                    f["mcnemar"][r_i]["p_holm"] = a
        for f in fam:
            f["sig_runs"] = sum(1 for x in f["mcnemar"] if x.get("p_holm", 1) < 0.05)
        res["paired"].extend(fam)


def tiers(res):
    """P2 minus P0 gain by model, and small-model P2 against frontier P0."""
    out = []
    for b in BENCH:
        for m in MODELS:
            a = res["cells"].get(f"{b}|P2|{m}")
            o = res["cells"].get(f"{b}|P0|{m}")
            if a and o:
                out.append({"benchmark": b, "model": m, "tier": TIER[m],
                            "p0": o["accuracy"]["mean"], "p2": a["accuracy"]["mean"],
                            "gain": a["accuracy"]["mean"] - o["accuracy"]["mean"],
                            "p0_stale": o["staleness"]["mean"], "p2_stale": a["staleness"]["mean"],
                            "p0_reading_error": o["reading_error"]["mean"],
                            "p0_exposure": o["exposure"]["mean"], "p2_exposure": a["exposure"]["mean"]})
    res["tiers"] = out


# ------------------------------------------------------------------ RQ4

def rq4(res):
    out = {"cells": {}, "agreement": {}, "per_model_agreement": [], "matching": {}, "correctness": {},
           "missing": []}
    qsets = {b: stale_questions(b) for b in BENCH}
    for b in BENCH:
        single = {p: mean(res["cells"][f"{b}|{p}|{m}"]["accuracy"]["mean"] for m in MODELS) for p in RANKED}
        single_m = {m: {p: res["cells"][f"{b}|{p}|{m}"]["accuracy"]["mean"] for p in RANKED} for m in MODELS}
        out["single"] = out.get("single", {})
        out["single"][b] = single
        for topo in ("shared", "independent", "orchestrator"):
            accs, accs_m = {}, defaultdict(dict)
            for p in RANKED:
                c = load(C / f"run1/rq4_normalized_{b}/{topo}__{p}.json")
                if not c:
                    out["missing"].append(f"{b}/{topo}/{p}")
                    continue
                rr = c["records"]
                by_m = defaultdict(list)
                for x in rr:
                    by_m[x.get("answer_model")].append(x)
                cm = {}
                for m, spec in SPEC.items():
                    xs = by_m.get(spec, [])
                    if not xs:
                        continue
                    known = [x for x in xs if x.get("_ctx_known") and x.get("_stale_answer")]
                    exp = [x for x in known if x.get("stale_in_ctx")]
                    cm[m] = {"accuracy": mean(float(x["correct"]) for x in xs),
                             "staleness": mean(float(x["stale"]) for x in xs),
                             "exposure": mean(float(bool(x["stale_in_ctx"])) for x in known) if known else None,
                             "reading_error": mean(float(x["stale"]) for x in exp) if exp else None,
                             "prompt_tokens": mean(x.get("prompt_tokens") or 0 for x in xs)}
                    accs_m[m][p] = cm[m]["accuracy"]
                s = c["summary"]
                entry = {"by_model": cm,
                         "accuracy": mean(v["accuracy"] for v in cm.values()),
                         "staleness": mean(v["staleness"] for v in cm.values()),
                         "exposure": mean(v["exposure"] for v in cm.values() if v["exposure"] is not None),
                         "invalidations": s.get("invalidations"),
                         "cross_writer": s.get("cross_writer_invalidations"),
                         "facts": (s.get("final_memory") or {}).get("total_facts"),
                         "active": (s.get("final_memory") or {}).get("active_facts"),
                         "routing": s.get("routing"),
                         "acc_agent_sd": None}
                if topo == "independent":
                    # SD of accuracy across the three private agents (pooled over models)
                    ag = defaultdict(list)
                    for x in rr:
                        ag[x.get("agent")].append(float(x["correct"]))
                    entry["agent_acc"] = {str(k): mean(v) for k, v in ag.items()}
                    entry["acc_agent_sd"] = sd(list(entry["agent_acc"].values()))
                if c.get("graphs") and topo != "independent":
                    # reference = the same topology's P0 memory (same writers, nothing forgotten)
                    ref = load(C / f"run1/rq4_normalized_{b}/{topo}__P0.json")
                    if ref and ref.get("graphs"):
                        entry["correctness"] = correctness(ref["graphs"], c["graphs"], qsets[b], p == "P2")
                accs[p] = entry["accuracy"]
                out["cells"][f"{b}|{topo}|{p}"] = entry
            if len(accs) == len(RANKED):
                a = [single[p] for p in RANKED]
                t = [accs[p] for p in RANKED]
                out["agreement"][f"{b}|{topo}"] = agreement(a, t)
                for m in MODELS:
                    if len(accs_m[m]) == len(RANKED):
                        ag = agreement([single_m[m][p] for p in RANKED], [accs_m[m][p] for p in RANKED])
                        out["per_model_agreement"].append({"benchmark": b, "topology": topo, "model": m, **ag})
        # matching modes, shared memory, P0 and P2
        for mode in ("exact", "normalized", "llm"):
            for p in ("P0", "P2"):
                c = load(C / f"run1/rq4_{mode}_{b}/shared__{p}.json")
                if not c:
                    continue
                s = c["summary"]
                out["matching"][f"{b}|{mode}|{p}"] = {
                    "accuracy": mean(float(x["correct"]) for x in c["records"]),
                    "staleness": mean(float(x["stale"]) for x in c["records"]),
                    "invalidations": s.get("invalidations"), "cross_writer": s.get("cross_writer_invalidations"),
                    "judgements": s.get("contradiction_judgements")}
    # who wrote each conversation in shared memory (ConvoMem: one writer per conversation)
    out["writer_effect"] = {}
    for b in BENCH:
        c = load(C / f"run1/rq4_normalized_{b}/shared__P0.json")
        if not c or not c.get("graphs"):
            continue
        writers = {}
        for conv, facts in c["graphs"].items():
            prov = defaultdict(int)
            for f in facts:
                prov[f.get("provenance")] += 1
            writers[conv] = {"writers": dict(prov), "facts": len(facts)}
        acc = defaultdict(list)
        for x in c["records"]:
            acc[x.get("conversation")].append(float(x["correct"]))
        for conv in writers:
            writers[conv]["accuracy"] = mean(acc.get(conv, []))
        out["writer_effect"][b] = writers
    # pooled agreement: concatenate the three benchmarks' 18 policy scores per topology
    res["rq4"] = out


# ------------------------------------------------------------------ follow-ups

def followups(res):
    out = {"matching": {}, "weights": {}, "grace": {}}
    for b in BENCH:
        for tag, d in (("normalized", None), ("exact", "matching_exact"), ("llm", "matching_llm"),
                       ("w631", None), ("w912", "weights_w912"), ("w811", "weights_w811"),
                       ("rec0", "weights_rec0"), ("rrf", "weights_rrf")):
            for m in MODELS:
                c = cell(1, b, "P2", m) if d is None else load(C / f"once/{d}_{b}/P2__openrouter_{m}.json")
                if not c:
                    continue
                x = metrics(c, m)
                x["closed"] = (c["summary"].get("memory_totals") or {}).get("closed_total")
                key = "matching" if tag in ("normalized", "exact", "llm") else "weights"
                out[key][f"{b}|{tag}|{m}"] = {k: x[k] for k in ("accuracy", "staleness", "exposure", "prompt_tokens", "closed")}
    for b in BENCH:
        g = load(ROOT / f"artifacts/results/v3/once/grace_history/{b}.json")
        if g:
            out["grace"][b] = [{k: v for k, v in r.items() if k != "records"} for r in g["rows"]]
    res["followups"] = out


# ------------------------------------------------------------------ tables

def write_tables(res):
    TAB.mkdir(parents=True, exist_ok=True)

    def w(name, header, rows):
        with open(TAB / name, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(header)
            wr.writerows(rows)

    def ms(a):
        return "" if a["mean"] is None else f"{100*a['mean']:.1f} ± {100*a['sd']:.1f}"

    rows = []
    for k, v in res["cells"].items():
        b, p, m = k.split("|")
        rows.append([BENCH[b], p, MODELS[m], ms(v["accuracy"]), ms(v["staleness"]),
                     "" if v["exposure"]["mean"] is None else f"{100*v['exposure']['mean']:.1f}",
                     "" if v["reading_error"]["mean"] is None else f"{100*v['reading_error']['mean']:.1f}",
                     f"{v['prompt_tokens']['mean']:.0f}",
                     "" if v["facts_active"]["mean"] is None else f"{v['facts_active']['mean']:.0f}",
                     "" if v["usd_per_1k_correct"]["mean"] is None else f"{v['usd_per_1k_correct']['mean']:.3f}",
                     f"{100*res['flip'][k]:.1f}"])
    w("main_cells.csv", ["benchmark", "policy", "model", "accuracy % (mean ± SD, 3 runs)",
                         "stale % (mean ± SD)", "old value in prompt %", "reading error %",
                         "prompt tokens / question", "facts kept", "USD per 1,000 correct", "flip rate %"], rows)
    rows = []
    for k, v in res["policy_avg"].items():
        b, p = k.split("|")
        rows.append([BENCH[b], p, ms(v["accuracy"]), ms(v["staleness"]),
                     "" if v["exposure"]["mean"] is None else f"{100*v['exposure']['mean']:.1f}",
                     "" if v["reading_error"]["mean"] is None else f"{100*v['reading_error']['mean']:.1f}",
                     f"{v['prompt_tokens']['mean']:.0f}", f"{v['facts_active']['mean']:.0f}" if v["facts_active"]["mean"] else ""])
    w("policy_average.csv", ["benchmark", "policy", "accuracy %", "stale %", "old value in prompt %",
                             "reading error %", "prompt tokens / question", "facts kept"], rows)
    rows = []
    for f in res["paired"]:
        rows.append([BENCH[f["benchmark"]], f"P2 vs {f['other']}", MODELS.get(f["model"], "all five"),
                     f"{100*f['diff']:+.1f}", f"[{100*f['lo']:+.1f}, {100*f['hi']:+.1f}]",
                     "; ".join(f"{x['p2_only']}/{x['other_only']}" for x in f["mcnemar"]),
                     "; ".join(f"{x.get('p_holm', 1):.3g}" for x in f["mcnemar"]), f"{f['sig_runs']}/3"])
    w("paired_p2.csv", ["benchmark", "comparison", "model", "accuracy difference (points of %)",
                        "95% CI (question bootstrap)", "discordant P2-only/other-only per run",
                        "Holm-adjusted McNemar p per run", "runs significant"], rows)
    rows = [[BENCH[k.split('|')[0]], k.split('|')[1], ms(v["complete"]), ms(v["sound"]), f"{v['n_old']['mean']:.0f}"]
            for k, v in res["correctness"].items() if v["complete"]["mean"] is not None]
    w("forgetting_correctness.csv", ["benchmark", "policy", "complete % (old value hidden)",
                                     "sound % (current value visible)", "changed slots found"], rows)
    rows = []
    for k, v in res["rq4"]["cells"].items():
        b, t, p = k.split("|")
        rows.append([BENCH[b], t, p, f"{100*v['accuracy']:.1f}", f"{100*v['staleness']:.1f}",
                     f"{100*v['exposure']:.1f}" if v["exposure"] == v["exposure"] else "",
                     v.get("invalidations") or "", v.get("cross_writer") or "",
                     f"{100*v['acc_agent_sd']:.1f}" if v.get("acc_agent_sd") is not None else ""])
    w("rq4_cells.csv", ["benchmark", "topology", "policy", "accuracy %", "stale %", "old value in prompt %",
                        "invalidations", "cross-writer invalidations", "SD across private agents (%)"], rows)
    rows = [[BENCH[k.split('|')[0]], k.split('|')[1], v["kendall_tau"], v["kendall_tau_p"], v["spearman"],
             v["spearman_p"], v["pearson"], v["pearson_p"]] for k, v in res["rq4"]["agreement"].items()]
    w("rq4_agreement.csv", ["benchmark", "topology", "Kendall tau-b", "exact p", "Spearman rho", "exact p",
                            "Pearson r", "exact p"], rows)


def main() -> None:
    res = {}
    main_matrix(res)
    paired(res)
    tiers(res)
    rq4(res)
    followups(res)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    write_tables(res)
    print("wrote", OUT, "and", TAB)
    if res["rq4"]["missing"]:
        print("RQ4 cells missing:", res["rq4"]["missing"])


if __name__ == "__main__":
    main()
