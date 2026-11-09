"""Every number of the final campaign in one JSON file.

The final report, the interactive dashboard and the Week 6 slides all read
`artifacts/final_results.json`, so a figure quoted in any of them traces back to
exactly one computation. Records are re-graded and re-scored with the same rules
as `analysis.final_report` (refusal = incorrect, plain gold = correct, staleness
= old value asserted without the current one).

Usage:
    python -m analysis.final_dataset
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from analysis.final_report import (Report, boot_ci, enrich, holm, load_cells, load_questions, mcnemar,
                                   mean, paired_diff_ci, pol_id, spearman, kendalls_w)

ROOT = Path(__file__).resolve().parents[2]


def r3(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)


def cell_metrics(c: dict, price) -> dict:
    rr = c["records"]
    s = c["summary"]
    tot = s.get("memory_totals") or {}
    acc = [float(r["correct"]) for r in rr]
    st = [float(r["stale"]) for r in rr]
    lo, hi = boot_ci(acc)
    slo, shi = boot_ci(st)
    pt = mean(r.get("prompt_tokens", r["tokens"]) for r in rr)
    ct = mean(r.get("completion_tokens", 0) for r in rr)
    usd = None
    if price:
        usd = sum(r.get("prompt_tokens", 0) * price[0] + r.get("completion_tokens", 0) * price[1] for r in rr) / 1e6
    known = [r for r in rr if r.get("_ctx_known") and r.get("_stale_answer")]
    exposed = mean(r["stale_in_ctx"] for r in known) if known else None
    both = [r for r in known if r["stale_in_ctx"]]
    return {
        "n": len(rr), "accuracy": r3(mean(acc)), "acc_lo": r3(lo), "acc_hi": r3(hi),
        "staleness": r3(mean(st)), "stale_lo": r3(slo), "stale_hi": r3(shi),
        "mentions_old": r3(mean(r["mentions_old"] for r in rr)),
        "f1": r3(mean(r["f1"] for r in rr)),
        "prompt_tokens": r3(pt), "completion_tokens": r3(ct),
        "usd_answers": r3(usd), "usd_per_1k_correct": r3(usd / sum(acc) * 1000) if usd and sum(acc) else None,
        "facts_active": tot.get("active_facts", s.get("final_memory", {}).get("active_facts")),
        "facts_total": tot.get("total_facts"), "facts_pruned": tot.get("pruned"),
        "facts_closed": tot.get("closed_total"), "write_rejections": tot.get("write_rejections"),
        "closed_in_context": r3(mean(r.get("retrieved_invalidated", 0) for r in rr)),
        "old_value_in_prompt": r3(exposed),
        "reading_error": r3(mean(r["stale"] for r in both)) if both else None,
        "reading_n": len(both),
    }


def main() -> None:
    cfg = json.loads((ROOT / "configs/final_analysis.json").read_text())
    rep = Report(cfg, ROOT)
    out = {"models": {}, "benchmarks": {}, "pairwise": {}, "rq3": {}, "tiers": {}, "ranks": {},
           "substrate": [], "rq4": [], "grace": {}, "heldout": [], "diagnostics": {}}
    for m in rep.minfo:
        out["models"][m] = rep.minfo[m]

    for b in rep.bench:
        ms, ps = rep.models(b), rep.policies(b)
        cells = {}
        for p in ps:
            for m in ms:
                c = rep.bench[b]["grid"].get((p, m))
                if c:
                    cells[f"{p}|{m}"] = cell_metrics(c, rep.minfo.get(m, {}).get("price"))
        # per-policy average over models
        avg = {}
        for p in ps:
            vals = [cells[f"{p}|{m}"] for m in ms if f"{p}|{m}" in cells]
            avg[p] = {k: r3(mean(v[k] for v in vals if v.get(k) is not None))
                      for k in ("accuracy", "staleness", "prompt_tokens", "completion_tokens",
                                "facts_active", "mentions_old", "closed_in_context", "f1")}
        out["benchmarks"][b] = {"models": ms, "policies": ps, "cells": cells, "policy_avg": avg,
                                "flagged": sorted(rep.bench[b].get("flagged", []))}
        # P2 vs every policy, pooled and per model
        pw = []
        comps = [q for q in ps if q not in ("P2", "NOMEM")]
        for scope in ["pooled"] + ms:
            sc = None if scope == "pooled" else [scope]
            for q in comps:
                a2, aq = rep.paired(b, "P2", q, sc)
                s2, sq = rep.paired(b, "P2", q, sc, key="stale")
                if not a2:
                    continue
                d, lo, hi = paired_diff_ci([float(x) for x in aq], [float(x) for x in a2])
                ds, slo, shi = paired_diff_ci([float(x) for x in sq], [float(x) for x in s2])
                bwin, bloss, pa = mcnemar(a2, aq)
                _, _, ps_ = mcnemar(s2, sq)
                pw.append({"scope": scope, "vs": q, "acc_diff": r3(d), "acc_lo": r3(lo), "acc_hi": r3(hi),
                           "p_acc": pa, "stale_diff": r3(ds), "stale_lo": r3(slo), "stale_hi": r3(shi),
                           "p_stale": ps_, "p2_wins": bwin, "p2_losses": bloss})
        for scope in {x["scope"] for x in pw}:
            grp = [x for x in pw if x["scope"] == scope]
            for x, pa in zip(grp, holm([x["p_acc"] for x in grp])):
                x["p_acc_holm"] = pa
            for x, ps_ in zip(grp, holm([x["p_stale"] for x in grp])):
                x["p_stale_holm"] = ps_
        out["pairwise"][b] = pw

    # small vs frontier difference in P2 staleness reduction, and accuracy gain
    for b in rep.bench:
        if "clean_of" in rep.bench[b]:
            continue
        by = defaultdict(lambda: {"stale_red": [], "acc_gain": []})
        for m in rep.models(b):
            r0, r2 = rep.recs(b, "P0", m), rep.recs(b, "P2", m)
            if not r0 or not r2:
                continue
            i2 = {(r.get("conversation"), r["question"]): r for r in r2}
            for r in r0:
                o = i2.get((r.get("conversation"), r["question"]))
                if o is not None:
                    by[rep.tier(m)]["stale_red"].append(float(r["stale"]) - float(o["stale"]))
                    by[rep.tier(m)]["acc_gain"].append(float(o["correct"]) - float(r["correct"]))
        out["tiers"][b] = {t: {"stale_reduction": r3(mean(v["stale_red"])), "acc_gain": r3(mean(v["acc_gain"])),
                               "n": len(v["stale_red"])} for t, v in by.items()}

    # ranking agreement
    for key in ("correct", "stale"):
        vecs, labels = [], []
        for b in rep.bench:
            if "clean_of" in rep.bench[b]:
                continue
            ps = [p for p in rep.policies(b) if p != "NOMEM"]
            for m in rep.models(b):
                v = [mean(r[key] for r in rep.recs(b, p, m)) if rep.recs(b, p, m) else None for p in ps]
                if None not in v:
                    vecs.append([-x if key == "stale" else x for x in v])
                    labels.append(f"{b}|{m}")
        out["ranks"][key] = {"kendalls_w": r3(kendalls_w(vecs)), "n": len(vecs), "labels": labels,
                             "spearman": [[r3(spearman(a, b2)) for b2 in vecs] for a in vecs]}
        # agreement excluding ConvoMem (all policies near the floor there)
        sub = [v for v, l in zip(vecs, labels) if not l.startswith("ConvoMem")]
        out["ranks"][key + "_no_convomem"] = r3(kendalls_w(sub))

    # substrate
    for b, modes in cfg.get("substrate", {}).items():
        if b not in rep.bench:
            continue
        qs = load_questions(str(ROOT / cfg["datasets"][b]))
        rows = {("normalized", m): rep.bench[b]["grid"].get(("P2", m)) for m in rep.models(b)}
        for mode, d in modes.items():
            for c in load_cells(ROOT / d):
                enrich(c, qs)
                rows[(mode, c["summary"]["model"])] = c
        for (mode, m), c in rows.items():
            if c is None or rep.tier(m) != "small":
                continue
            tot = c["summary"].get("memory_totals") or {}
            out["substrate"].append({"benchmark": b, "mode": mode, "model": m,
                                     "accuracy": r3(mean(r["correct"] for r in c["records"])),
                                     "staleness": r3(mean(r["stale"] for r in c["records"])),
                                     "closed": tot.get("closed_total"),
                                     "llm_checks": c["summary"].get("contradiction_judgements", 0)})

    # RQ4
    qs = load_questions(str(ROOT / cfg["datasets"]["MQuAKE-T"]))
    for mode, d in (cfg.get("rq4") or {}).items():
        for c in load_cells(ROOT / d):
            enrich(c, qs)
            s = c["summary"]
            rr = c["records"]
            out["rq4"].append({"matching": mode, "topology": s.get("topology"), "policy": pol_id(s.get("policy", "")),
                               "accuracy": r3(mean(r["correct"] for r in rr)),
                               "staleness": r3(mean(r["stale"] for r in rr)),
                               "tokens": r3(s.get("mean_tokens_per_q")),
                               "closed": s.get("invalidations"), "cross_writer": s.get("cross_writer_invalidations"),
                               "facts": (s.get("final_memory") or {}).get("active_facts")})

    # grace (regraded)
    from drift.pipeline import is_abstention, verbatim_correct
    names = {"mquake_t": "MQuAKE-T", "factconsolidation": "FactConsolidation", "convomem": "ConvoMem"}
    gdir = ROOT / cfg["grace_history_dir"]
    for f in sorted(gdir.glob("*.json")):
        name = names.get(f.stem, f.stem)
        qmap = {q["question"]: q for c in json.loads((ROOT / cfg["datasets"][name]).read_text())["conversations"]
                for q in c["questions"]}
        rows = json.loads(f.read_text())["rows"]
        ret = {r["grace"]: r for r in rows if r["model"] is None}
        res = []
        for g, r in ret.items():
            e = {"grace": g, "facts": r["active_facts"], "wasted_slots": r3(r["wasted_slots"]),
                 "old_stored": r3(r["history_stored"]), "old_retrieved": r3(r["history_support"])}
            for a in rows:
                if a["model"] is None or a["grace"] != g:
                    continue
                cur, his = [], []
                for x in a.get("records", []):
                    q = qmap.get(x["question"], {})
                    ca = x["current_answer"]
                    cur.append(False if is_abstention(ca, q.get("answer", "")) else
                               True if verbatim_correct(ca, q.get("answer", ""), q.get("stale_answer")) else
                               bool(x["current_correct"]))
                    ha = x["history_answer"]
                    his.append(False if is_abstention(ha, q.get("stale_answer", "")) else
                               True if verbatim_correct(ha, q.get("stale_answer", ""), q.get("current_answer")) else
                               bool(x["history_correct"]))
                e[a["model"]] = {"current": r3(mean(cur)), "history": r3(mean(his))}
            res.append(e)
        order = [str(x) for x in cfg.get("grace_grid", [0, 1, 3, 5, 7, 10, 14, 21, "never"])]
        res.sort(key=lambda e: order.index(str(e["grace"])) if str(e["grace"]) in order else 99)
        out["grace"][name] = res

    # held-out weights
    qs = load_questions(str(ROOT / cfg["datasets"]["FactConsolidation"]))
    hd = ROOT / "artifacts/results/heldout_weights_fc"
    cells = {}
    for tag in ("w631", "w912", "w811"):
        for c in load_cells(hd / tag):
            enrich(c, qs)
            cells[(tag, c["summary"]["model"])] = c
    for (tag, m), c in sorted(cells.items()):
        base = cells.get(("w631", m))
        e = {"weights": tag, "model": m, "accuracy": r3(mean(r["correct"] for r in c["records"])),
             "staleness": r3(mean(r["stale"] for r in c["records"]))}
        if base and tag != "w631":
            ib = {r["question"]: r["correct"] for r in base["records"]}
            pairs = [(ib[r["question"]], r["correct"]) for r in c["records"] if r["question"] in ib]
            x, y, pv = mcnemar([q for _, q in pairs], [p for p, _ in pairs])
            e.update(better=x, worse=y, p=pv)
        out["heldout"].append(e)

    # judge and preflight
    ja = ROOT / cfg["judge_agreement"]
    if ja.is_file():
        j = json.loads(ja.read_text())
        out["judge"] = {k: j[k] for k in ("cheap", "reference", "n", "agreement", "kappa",
                                           "cheap_yes_ref_no", "cheap_no_ref_yes", "by_benchmark")}
    pf = ROOT / cfg["preflight"]
    if pf.is_file():
        out["preflight"] = json.loads(pf.read_text())

    path = ROOT / "artifacts/final_results.json"
    path.write_text(json.dumps(out, indent=1, default=str))
    print("wrote", path)


if __name__ == "__main__":
    main()
