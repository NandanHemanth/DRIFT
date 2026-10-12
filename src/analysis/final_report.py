"""Deep analysis of the final campaign: every table, figure and test in one pass.

Reads the result cells written by the final matrix (five answer models x seven
policies x three benchmarks), the substrate ablation, RQ4, the grace-period and
held-out-weight experiments, and the judge check, and writes

    paper/FINAL_ANALYSIS.md      the report, section per research question
    paper/figures_final/*.png    every figure the report cites
    paper/tables_final/*.csv     every table, for the thesis and for checking

Nothing here calls a model. Every number is recomputed from the saved
per-question records, so the report can be rebuilt at any time and partial runs
are reported as partial rather than silently skipped.

Statistics (all paired, since every policy answers the same questions):
  * percentile bootstrap 95% intervals, 5,000 resamples
  * exact two-sided McNemar test on discordant pairs
  * paired bootstrap interval on the per-question difference
  * Holm correction across each family of comparisons
  * Spearman correlation and Kendall's W for ranking agreement

Usage:
    python -m analysis.final_report
    python -m analysis.final_report --config configs/final_analysis.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import defaultdict
from math import comb
from pathlib import Path

BOOT = 5000
SEED = 7


# ------------------------------------------------------------------ statistics

def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def boot_ci(xs: list[float], n: int = BOOT) -> tuple[float, float]:
    if not xs:
        return (float("nan"), float("nan"))
    rng = random.Random(SEED)
    k = len(xs)
    ms = sorted(sum(xs[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def paired_diff_ci(a: list[float], b: list[float], n: int = BOOT) -> tuple[float, float, float]:
    """Mean of b - a with a paired bootstrap 95% interval."""
    d = [y - x for x, y in zip(a, b)]
    lo, hi = boot_ci(d, n)
    return mean(d), lo, hi


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """(a right b wrong, a wrong b right, exact two-sided p)."""
    x = sum(1 for p, q in zip(a, b) if p and not q)
    y = sum(1 for p, q in zip(a, b) if q and not p)
    n = x + y
    if n == 0:
        return x, y, 1.0
    tail = sum(comb(n, i) for i in range(0, min(x, y) + 1)) / 2 ** n
    return x, y, min(1.0, 2 * tail)


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0.0] * len(ps)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def ranks(xs: list[float]) -> list[float]:
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


def spearman(a: list[float], b: list[float]) -> float:
    if len(a) < 3:
        return float("nan")
    ra, rb = ranks(a), ranks(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def kendalls_w(rows: list[list[float]]) -> float:
    """Agreement of m rankings over n items (rows = raters)."""
    m, n = len(rows), len(rows[0]) if rows else 0
    if m < 2 or n < 2:
        return float("nan")
    R = [ranks(r) for r in rows]
    tot = [sum(R[i][j] for i in range(m)) for j in range(n)]
    mt = mean(tot)
    s = sum((t - mt) ** 2 for t in tot)
    return 12 * s / (m ** 2 * (n ** 3 - n))


def fmt(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def fmt_p(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ------------------------------------------------------------------ loading

def pol_id(spec: str) -> str:
    return spec.split(":")[0]


def load_cells(d: str | Path) -> list[dict]:
    out = []
    p = Path(d)
    if not p.exists():
        return out
    for f in sorted(p.glob("*.json")):
        if f.name == "summary_table.json":
            continue
        try:
            c = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(c, dict) and "summary" in c and "records" in c:
            out.append(c)
    return out


def id_text_map(cell: dict) -> dict[str, str]:
    m = {}
    snaps = cell.get("graph_snapshots")
    if snaps:
        for facts in snaps.values():
            for f in facts:
                m[f["id"]] = f["text"]
    for f in cell.get("graph_snapshot", []) or []:
        m.setdefault(f["id"], f["text"])
    return m


def enrich(cell: dict, questions: dict) -> None:
    """Add stale_in_ctx / gold_in_ctx to every record when the saved graphs allow.

    The answer prompt shows only fact text, so 'the superseded value reached the
    model' is exactly 'the stale string appears in a retrieved fact's text'.
    """
    m = id_text_map(cell)
    for r in cell["records"]:
        q = questions.get((r.get("conversation"), r["question"])) or questions.get((None, r["question"]))
        stale = (q or {}).get("stale_answer")
        r["_stale_answer"] = stale
        r["_category"] = (q or {}).get("category", r.get("category"))
        texts = [m[i] for i in r.get("retrieved_ids", []) if i in m]
        r["_ctx_known"] = bool(texts) and len(texts) == len(r.get("retrieved_ids", []))
        if r["_ctx_known"]:
            low = [t.lower() for t in texts]
            r["stale_in_ctx"] = bool(stale) and any(stale.lower() in t for t in low)
            # gold strings in ConvoMem are full sentences; fall back to "not known"
            gold = r.get("gold", "")
            r["gold_in_ctx"] = any(gold.lower() in t for t in low) if len(gold) <= 60 else None


def load_questions(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    out = {}
    for c in data["conversations"]:
        for q in c["questions"]:
            out[(c["id"], q["question"])] = q
            out.setdefault((None, q["question"]), q)
    return out


# ------------------------------------------------------------------ data audit

_SUBJ = [r"head of the (.+) government", r"head of state (?:in|of) (.+)\?",
         r"headquarter of (.+) located", r"(?:of|for|does|is) (.+?)[?]"]


def restated_stale(path: str) -> set[str]:
    """Questions whose superseded value is stated again, about the same subject,
    in a session after the new value first appears. Memory then genuinely says
    the old value is current, so a 'stale' answer there is a data artefact, not a
    forgetting failure. Reported separately and excluded in the clean subset."""
    data = json.loads(Path(path).read_text())
    flagged = set()
    for c in data["conversations"]:
        lines = [(s["time"], l) for s in c["sessions"] for l in s["lines"]]
        for q in c["questions"]:
            st, g = q.get("stale_answer"), q.get("answer", "")
            if not st or len(g) > 60:
                continue
            subj = None
            for p in _SUBJ:
                m = re.search(p, q["question"])
                if m:
                    subj = m.group(1)
                    break
            if not subj:
                continue
            tg = [t for t, l in lines if g in l and subj in l]
            if tg and any(st in l and subj in l and t > min(tg) for t, l in lines):
                flagged.add(q["question"])
    return flagged


# ------------------------------------------------------------------ figures

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    return plt


def heatmap(mat, rows, cols, title, path, fmt_s="{:.2f}", cmap="Greens"):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(1.1 * len(cols) + 2, 0.45 * len(rows) + 1.4))
    vals = [[v if v is not None else float("nan") for v in r] for r in mat]
    im = ax.imshow(vals, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(cols)), cols, rotation=30, ha="right")
    ax.set_yticks(range(len(rows)), rows)
    for i, r in enumerate(vals):
        for j, v in enumerate(r):
            if not math.isnan(v):
                ax.text(j, i, fmt_s.format(v), ha="center", va="center", fontsize=8)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def write_csv(path: Path, header: list[str], rows: list[list]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ------------------------------------------------------------------ the report

class Report:
    def __init__(self, cfg: dict, root: Path):
        self.cfg, self.root = cfg, root
        self.fig_dir = root / cfg["out_figures"]
        self.tab_dir = root / cfg["out_tables"]
        self.fig_dir.mkdir(parents=True, exist_ok=True)
        self.md: list[str] = []
        self.minfo = cfg.get("models", {})
        self.porder = cfg.get("policy_order", ["NOMEM", "P0", "P1", "P2", "P3", "P4", "P5"])
        self.bench: dict[str, dict] = {}
        self.findings: list[str] = []
        for name, d in cfg["benchmarks"].items():
            cells = load_cells(root / d)
            if not cells:
                continue
            qs = load_questions(str(root / cfg["datasets"][name]))
            for c in cells:
                enrich(c, qs)
            grid = {(pol_id(c["summary"]["policy"]), c["summary"]["model"]): c for c in cells}
            self.bench[name] = {"grid": grid, "flagged": set()}
            flagged = restated_stale(str(root / cfg["datasets"][name]))
            if flagged:
                self.bench[name]["flagged"] = flagged
                clean = {}
                for k, c in grid.items():
                    c2 = dict(c)
                    c2["records"] = [r for r in c["records"] if r["question"] not in flagged]
                    clean[k] = c2
                self.bench[name + " (clean)"] = {"grid": clean, "flagged": set(), "clean_of": name}

    # helpers
    def label(self, m):
        return self.minfo.get(m, {}).get("label", m.split("/")[-1])

    def tier(self, m):
        return self.minfo.get(m, {}).get("tier", "unknown")

    def models(self, b):
        ms = sorted({m for _, m in self.bench[b]["grid"]},
                    key=lambda m: (["frontier", "mid", "small", "unknown"].index(self.tier(m)), m))
        return ms

    def policies(self, b):
        ps = {p for p, _ in self.bench[b]["grid"]}
        return [p for p in self.porder if p in ps]

    def recs(self, b, p, m):
        c = self.bench[b]["grid"].get((p, m))
        return c["records"] if c else None

    def h(self, level, text):
        self.md += ["", "#" * level + " " + text, ""]

    def p(self, text):
        self.md += [text, ""]

    def table(self, header, rows, csv_name=None):
        self.md.append("| " + " | ".join(header) + " |")
        self.md.append("|" + "---|" * len(header))
        for r in rows:
            self.md.append("| " + " | ".join(str(x) for x in r) + " |")
        self.md.append("")
        if csv_name:
            write_csv(self.tab_dir / csv_name, header, rows)

    def fig(self, name, caption):
        self.md += [f"![{caption}](figures_final/{name})", "", f"*{caption}*", ""]

    # ---------------------------------------------------------------- sections
    def s_integrity(self):
        self.h(2, "0. What was run, and is it clean")
        rows = []
        for b, B in self.bench.items():
            if "clean_of" in B:
                continue
            cells = list(B["grid"].values())
            fps = {c["summary"].get("prompt_fingerprint") for c in cells}
            rm = {c["summary"].get("relation_matching") for c in cells}
            nq = {c["summary"].get("n_questions") for c in cells}
            ctx = mean(r["_ctx_known"] for c in cells for r in c["records"])
            fails = sum((c["summary"].get("extraction_parse_failures") or {}).get("after_retry", 0) for c in cells)
            rows.append([b, f"{len(cells)} / {len(self.models(b)) * len(self.policies(b))}",
                         len(self.models(b)), ", ".join(sorted(str(x) for x in nq)),
                         len(fps), ", ".join(sorted(str(x) for x in rm)), f"{ctx:.0%}", fails])
        self.table(["benchmark", "cells", "models", "questions per cell", "prompt versions",
                    "relation matching", "records with context recovered", "extraction failures after retry"],
                   rows, "integrity.csv")
        self.p("Every cell of a benchmark should show one prompt version and one relation-matching "
               "mode. Context recovery is the share of answers whose retrieved facts could be mapped "
               "back to text, which the mechanism analysis (Section 2) needs.")
        for b, B in self.bench.items():
            if B["flagged"]:
                self.p(f"**Data artefact in {b}.** {len(B['flagged'])} questions have their superseded "
                       "value stated again, about the same subject, in a session after the update, so "
                       "memory itself says the old value is current. They are kept in the main tables and "
                       f"removed in the '{b} (clean)' rows. Questions: " + "; ".join(sorted(B["flagged"])))
        pf = self.root / self.cfg.get("preflight", "")
        if pf.is_file():
            rows = []
            for r in json.loads(pf.read_text()):
                rows.append([r["benchmark"], r["questions"], r.get("detected_exact"), r.get("detected_normalized"),
                             r.get("missed_normalized"), r.get("gold_closed_normalized")])
            self.p("Contradiction detection coverage, from the offline preflight (questions whose superseded "
                   "value sits in a closed fact):")
            self.table(["benchmark", "questions with a superseded answer", "detected (exact)",
                        "detected (normalised)", "stored but missed", "current answer wrongly closed"],
                       rows, "detection_coverage.csv")

    def s_main(self):
        self.h(2, "1. Main results")
        for b in self.bench:
            ms, ps = self.models(b), self.policies(b)
            acc = [[mean(r["correct"] for r in (self.recs(b, p, m) or [])) if self.recs(b, p, m) else None
                    for m in ms] for p in ps]
            stl = [[mean(r["stale"] for r in (self.recs(b, p, m) or [])) if self.recs(b, p, m) else None
                    for m in ms] for p in ps]
            self.h(3, b)
            rows = []
            for i, p in enumerate(ps):
                row = [p]
                for j, m in enumerate(ms):
                    rr = self.recs(b, p, m)
                    if not rr:
                        row.append("missing")
                        continue
                    lo, hi = boot_ci([float(r["correct"]) for r in rr])
                    row.append(f"{acc[i][j]:.3f} [{lo:.2f}, {hi:.2f}] / {stl[i][j]:.3f}")
                rows.append(row)
            self.p("Each cell: accuracy [95% interval] / staleness rate.")
            safe = re.sub(r"[^a-z0-9]+", "_", b.lower()).strip("_")
            self.table(["policy"] + [self.label(m) for m in ms], rows, f"main_{safe}.csv")
            cols = [self.label(m) for m in ms]
            heatmap(acc, ps, cols, f"{b}: accuracy", self.fig_dir / f"acc_{safe}.png")
            heatmap(stl, ps, cols, f"{b}: staleness rate", self.fig_dir / f"stale_{safe}.png", cmap="Reds")
            self.fig(f"acc_{safe}.png", f"{b}: accuracy by policy and model")
            self.fig(f"stale_{safe}.png", f"{b}: staleness rate by policy and model")

    def s_rq1(self):
        self.h(2, "2. RQ1: does append-only memory surface superseded facts?")
        rows, read = [], []
        for b in self.bench:
            for m in self.models(b):
                r0 = self.recs(b, "P0", m)
                if not r0:
                    continue
                st = [float(r["stale"]) for r in r0]
                lo, hi = boot_ci(st)
                known = [r for r in r0 if r["_ctx_known"] and r["_stale_answer"]]
                exposed = mean(r["stale_in_ctx"] for r in known) if known else float("nan")
                both = [r for r in known if r["stale_in_ctx"]]
                misread = mean(r["stale"] for r in both) if both else float("nan")
                r2 = self.recs(b, "P2", m)
                k2 = [r for r in (r2 or []) if r["_ctx_known"] and r["_stale_answer"]]
                exposed2 = mean(r["stale_in_ctx"] for r in k2) if k2 else float("nan")
                rows.append([b, self.label(m), self.tier(m), f"{mean(st):.3f} [{lo:.3f}, {hi:.3f}]",
                             fmt(exposed), fmt(exposed2), f"{fmt(misread)} (n={len(both)})"])
                if both and "clean_of" not in self.bench[b]:
                    read.append((self.label(m), self.tier(m), b, misread))
        self.table(["benchmark", "model", "tier", "P0 staleness [95% CI]", "old value in prompt, P0",
                    "old value in prompt, P2", "stale answer when the old value was in the prompt"],
                   rows, "rq1_mechanism.csv")
        self.p("The last column is the model's reading error: the share of answers that repeat the old "
               "value when it was shown next to the new one. Retrieval decides whether the old value is "
               "shown; the model decides only how often it falls for it.")
        if read:
            plt = _plt()
            labels = sorted({x[0] for x in read}, key=lambda l: [y[1] for y in read if y[0] == l][0])
            benches = sorted({x[2] for x in read})
            fig, ax = plt.subplots(figsize=(7, 3.2))
            w = 0.8 / max(1, len(benches))
            for k, bn in enumerate(benches):
                ys = [next((x[3] for x in read if x[0] == l and x[2] == bn), float("nan")) for l in labels]
                ax.bar([i + k * w for i in range(len(labels))], ys, w, label=bn)
            ax.set_xticks([i + w * (len(benches) - 1) / 2 for i in range(len(labels))], labels, rotation=20)
            ax.set_ylabel("stale answers when old value shown")
            ax.legend(frameon=False)
            fig.tight_layout()
            fig.savefig(self.fig_dir / "reading_error.png", dpi=200)
            plt.close(fig)
            self.fig("reading_error.png", "Reading error by model: how often a model repeats the old value when it is in the prompt (P0)")

    def paired(self, b, pa, pb, models=None, key="correct"):
        """Concatenate per-question outcomes of two policies over models, aligned by question."""
        xs, ys = [], []
        for m in models or self.models(b):
            ra, rb = self.recs(b, pa, m), self.recs(b, pb, m)
            if not ra or not rb:
                continue
            ib = {(r.get("conversation"), r["question"]): r for r in rb}
            for r in ra:
                o = ib.get((r.get("conversation"), r["question"]))
                if o is not None:
                    xs.append(bool(r[key]))
                    ys.append(bool(o[key]))
        return xs, ys

    def s_rq2(self):
        self.h(2, "3. RQ2: which policy gives the best trade-off?")
        for b in self.bench:
            ps, ms = self.policies(b), self.models(b)
            rows, pts = [], []
            for p in ps:
                acc = [mean(r["correct"] for r in self.recs(b, p, m)) for m in ms if self.recs(b, p, m)]
                st = [mean(r["stale"] for r in self.recs(b, p, m)) for m in ms if self.recs(b, p, m)]
                tok = [mean(r.get("prompt_tokens", r["tokens"]) for r in self.recs(b, p, m)) for m in ms if self.recs(b, p, m)]
                facts = [((self.bench[b]["grid"][(p, m)]["summary"].get("memory_totals") or {}).get("active_facts")
                          or self.bench[b]["grid"][(p, m)]["summary"].get("final_memory", {}).get("active_facts"))
                         for m in ms if (p, m) in self.bench[b]["grid"]]
                facts = [f for f in facts if f is not None]
                rows.append([p, fmt(mean(acc)), fmt(mean(st)), fmt(mean(tok), 0), fmt(mean(facts), 0) if facts else "n/a"])
                pts.append((p, mean(tok), mean(acc), mean(st)))
            self.h(3, b)
            self.p("Averaged over answer models. Tokens are prompt tokens per question; facts are those stored at the end.")
            safe = re.sub(r"[^a-z0-9]+", "_", b.lower()).strip("_")
            self.table(["policy", "accuracy", "staleness", "prompt tokens / q", "facts stored"], rows, f"tradeoff_{safe}.csv")
            # P2 against every other policy, pooled over models, Holm-corrected
            comp = [q for q in ps if q not in ("P2", "NOMEM")]
            res = []
            for q in comp:
                a2, aq = self.paired(b, "P2", q)
                s2, sq = self.paired(b, "P2", q, key="stale")
                if not a2:
                    continue
                d, lo, hi = paired_diff_ci([float(x) for x in aq], [float(x) for x in a2])
                _, _, pa = mcnemar(a2, aq)
                ds, los, his = paired_diff_ci([float(x) for x in sq], [float(x) for x in s2])
                _, _, ps_ = mcnemar(s2, sq)
                res.append([q, d, lo, hi, pa, ds, los, his, ps_])
            if res:
                pa_adj = holm([r[4] for r in res])
                ps_adj = holm([r[8] for r in res])
                rows = [[r[0], f"{r[1]:+.3f} [{r[2]:+.3f}, {r[3]:+.3f}]", fmt_p(pa_adj[i]),
                         f"{r[5]:+.3f} [{r[6]:+.3f}, {r[7]:+.3f}]", fmt_p(ps_adj[i])] for i, r in enumerate(res)]
                self.p("P2 minus each other policy, per question, pooled over models. Intervals are paired "
                       "bootstrap; p-values are exact McNemar, Holm-corrected within each column.")
                self.table(["vs", "accuracy difference", "p (Holm)", "staleness difference", "p (Holm)"],
                           rows, f"p2_vs_all_{safe}.csv")
                for r, padj in zip(res, pa_adj):
                    if r[0] == "P0":
                        verdict = ("equivalent within" if r[2] > -0.05 and r[3] < 0.05 else "not shown equivalent within")
                        self.findings.append(
                            f"{b}: P2 vs P0 accuracy {r[1]:+.3f} [{r[2]:+.3f}, {r[3]:+.3f}] ({verdict} ±0.05); "
                            f"staleness {r[5]:+.3f} [{r[6]:+.3f}, {r[7]:+.3f}].")
                    if r[0] == "P3":
                        self.findings.append(f"{b}: P3 (novelty gate) vs P2 staleness {-r[5]:+.3f}, p {fmt_p(ps_adj[res.index(r)])}.")
            plt = _plt()
            fig, ax = plt.subplots(figsize=(5, 3.4))
            for p, t, a, s in pts:
                ax.scatter(t, a, s=40 + 600 * (s if not math.isnan(s) else 0), alpha=.7)
                ax.annotate(p, (t, a), textcoords="offset points", xytext=(5, 4), fontsize=8)
            ax.set_xlabel("prompt tokens per question")
            ax.set_ylabel("accuracy")
            ax.set_title(f"{b}: cost vs accuracy (marker size = staleness)")
            fig.tight_layout()
            fig.savefig(self.fig_dir / f"tradeoff_{safe}.png", dpi=200)
            plt.close(fig)
            self.fig(f"tradeoff_{safe}.png", f"{b}: accuracy against prompt tokens, averaged over models")

    def s_rq3(self):
        self.h(2, "4. RQ3: is it the timeline, or any graph-aware clean-up? (P2 vs P5)")
        rows, ps_a, ps_s = [], [], []
        for b in self.bench:
            for m in self.models(b) + ["pooled"]:
                a2, a5 = self.paired(b, "P2", "P5", None if m == "pooled" else [m])
                s2, s5 = self.paired(b, "P2", "P5", None if m == "pooled" else [m], key="stale")
                if not a2:
                    continue
                d, lo, hi = paired_diff_ci([float(x) for x in a5], [float(x) for x in a2])
                ds, los, his = paired_diff_ci([float(x) for x in s5], [float(x) for x in s2])
                _, _, pa = mcnemar(a2, a5)
                _, _, ps_ = mcnemar(s2, s5)
                rows.append([b, "all models" if m == "pooled" else self.label(m), d, lo, hi, pa, ds, los, his, ps_])
        if rows:
            pa = holm([r[5] for r in rows])
            ps_ = holm([r[9] for r in rows])
            out = [[r[0], r[1], f"{r[2]:+.3f} [{r[3]:+.3f}, {r[4]:+.3f}]", fmt_p(pa[i]),
                    f"{r[6]:+.3f} [{r[7]:+.3f}, {r[8]:+.3f}]", fmt_p(ps_[i])] for i, r in enumerate(rows)]
            self.table(["benchmark", "model", "accuracy P2 - P5", "p (Holm)", "staleness P2 - P5", "p (Holm)"],
                       out, "rq3_p2_vs_p5.csv")
            for r, q in zip(rows, pa):
                if r[1] == "all models" and "clean" not in r[0]:
                    self.findings.append(f"{r[0]}: P2 vs P5 accuracy {r[2]:+.3f} [{r[3]:+.3f}, {r[4]:+.3f}], p {fmt_p(q)}.")

    def s_models(self):
        self.h(2, "5. Small models against frontier models")
        rows, effect = [], defaultdict(list)
        for b in self.bench:
            if "clean_of" in self.bench[b]:
                continue
            for m in self.models(b):
                r0, r2 = self.recs(b, "P0", m), self.recs(b, "P2", m)
                rn = self.recs(b, "NOMEM", m)
                if not r0 or not r2:
                    continue
                price = self.minfo.get(m, {}).get("price")
                cost = None
                if price and "prompt_tokens" in r2[0]:
                    usd = sum(r["prompt_tokens"] * price[0] + r.get("completion_tokens", 0) * price[1] for r in r2) / 1e6
                    ok = sum(r["correct"] for r in r2)
                    cost = usd / ok * 1000 if ok else None
                drop = mean(r["stale"] for r in r0) - mean(r["stale"] for r in r2)
                gain = mean(r["correct"] for r in r2) - mean(r["correct"] for r in r0)
                effect[self.tier(m)].append((b, m, r0, r2))
                rows.append([b, self.label(m), self.tier(m),
                             fmt(mean(r["correct"] for r in rn)) if rn else "n/a",
                             fmt(mean(r["correct"] for r in r0)), fmt(mean(r["correct"] for r in r2)),
                             f"{gain:+.3f}", f"{drop:+.3f}", fmt(cost, 2) if cost else "n/a"])
        self.table(["benchmark", "model", "tier", "accuracy NOMEM", "accuracy P0", "accuracy P2",
                    "P2 accuracy gain", "P2 staleness reduction", "USD per 1,000 correct answers (P2)"],
                   rows, "models.csv")
        # does P2 help small models more? difference in differences, paired by question
        def dd(items):
            vals = []
            for _, _, r0, r2 in items:
                i2 = {(r.get("conversation"), r["question"]): r for r in r2}
                for r in r0:
                    o = i2.get((r.get("conversation"), r["question"]))
                    if o is not None:
                        vals.append(float(r["stale"]) - float(o["stale"]))
            return vals
        sm, fr = dd(effect.get("small", [])), dd(effect.get("frontier", []))
        if sm and fr:
            rng = random.Random(SEED)
            diffs = sorted(mean(rng.choice(sm) for _ in sm) - mean(rng.choice(fr) for _ in fr) for _ in range(2000))
            est = mean(sm) - mean(fr)
            lo, hi = diffs[50], diffs[1949]
            self.p(f"Staleness removed by P2, small models minus frontier models: {est:+.3f} "
                   f"[{lo:+.3f}, {hi:+.3f}] (bootstrap over questions). A positive value means forgetting "
                   "matters more for the small models, which misread conflicting facts more often.")
            self.findings.append(f"P2 removes {est:+.3f} [{lo:+.3f}, {hi:+.3f}] more staleness for small models than for frontier models.")

    def s_ranks(self):
        self.h(2, "6. Do policy rankings agree across models and benchmarks?")
        for key, name in (("correct", "accuracy"), ("stale", "staleness")):
            labels, vecs = [], []
            for b in self.bench:
                if "clean_of" in self.bench[b]:
                    continue
                ps = [p for p in self.policies(b) if p != "NOMEM"]
                for m in self.models(b):
                    v = [mean(r[key] for r in self.recs(b, p, m)) if self.recs(b, p, m) else None for p in ps]
                    if None in v:
                        continue
                    labels.append(f"{b[:6]} {self.label(m)}")
                    vecs.append([-x if key == "stale" else x for x in v])
            if len(vecs) < 2:
                continue
            w = kendalls_w(vecs)
            n = len(vecs)
            mat = [[spearman(vecs[i], vecs[j]) for j in range(n)] for i in range(n)]
            heatmap(mat, labels, labels, f"Spearman agreement of policy rankings ({name})",
                    self.fig_dir / f"rank_agreement_{name}.png", cmap="RdBu", fmt_s="{:.1f}")
            self.p(f"Kendall's W over all {n} model and benchmark combinations ({name}, six policies): **{w:.2f}** "
                   "(1 = every combination ranks the policies identically, 0 = no agreement).")
            self.fig(f"rank_agreement_{name}.png", f"Pairwise Spearman correlation of policy rankings by {name}")
            self.findings.append(f"Policy rankings by {name} agree across models and benchmarks with Kendall's W = {w:.2f}.")

    def s_judge(self):
        self.h(2, "7. How far to trust the judge")
        rows = []
        for b in self.bench:
            if "clean_of" in self.bench[b]:
                continue
            allr = [r for c in self.bench[b]["grid"].values() for r in c["records"]]
            f1c = mean(r["f1"] for r in allr if r["correct"])
            f1w = mean(r["f1"] for r in allr if not r["correct"])
            short = [r for r in allr if len(r.get("gold", "")) <= 40]
            missed = [r for r in short if r["gold"].lower() in r["answer"].lower() and not r["correct"] and not r["stale"]]
            rows.append([b, len(allr), fmt(f1c), fmt(f1w), f"{len(missed)} of {len(short)}"])
        self.table(["benchmark", "graded answers", "mean token F1 when judged correct", "when judged incorrect",
                    "gold answer quoted verbatim but judged incorrect"], rows, "judge_checks.csv")
        ja = self.root / self.cfg.get("judge_agreement", "")
        if ja.is_file():
            j = json.loads(ja.read_text())
            self.p(f"Judge check: {j['cheap']} against {j['reference']} on {j['n']} existing answers: "
                   f"agreement {j['agreement']:.3f}, Cohen's kappa {j['kappa']:.3f}; the cheap judge said correct "
                   f"where the reference said incorrect {j['cheap_yes_ref_no']} times, and the reverse {j['cheap_no_ref_yes']} times.")
            self.findings.append(f"The fixed judge agrees with the reference judge on {j['agreement']:.1%} of answers (kappa {j['kappa']:.2f}).")

    def s_substrate(self):
        sub = self.cfg.get("substrate", {})
        rows = []
        for b, modes in sub.items():
            if b not in self.bench:
                continue
            variants = {"normalized": {m: self.bench[b]["grid"].get(("P2", m)) for m in self.models(b)}}
            for mode, d in modes.items():
                variants[mode] = {c["summary"]["model"]: c for c in load_cells(self.root / d)}
            for mode in ("exact", "normalized", "llm"):
                for m, c in sorted((variants.get(mode) or {}).items()):
                    if not c or not any(m in (variants.get(x) or {}) for x in ("exact", "llm")):
                        continue
                    s = c["summary"]
                    tot = s.get("memory_totals") or {}
                    rows.append([b, mode, self.label(m), fmt(mean(r["correct"] for r in c["records"])),
                                 fmt(mean(r["stale"] for r in c["records"])),
                                 tot.get("closed_total", "n/a"), s.get("contradiction_judgements", 0)])
        if rows:
            self.h(2, "8. How contradictions are detected: exact, normalised, language model")
            self.p("P2 under the three relation-matching modes. Exact compares relation names as written; "
                   "normalised compares cleaned names and also matches facts written in the opposite direction; "
                   "the language model mode asks a fixed model which stored facts a new fact replaces, as Zep does.")
            self.table(["benchmark", "matching", "model", "accuracy", "staleness", "facts closed",
                        "language model checks"], rows, "substrate.csv")

    def s_rq4(self):
        rows = []
        for mode, d in (self.cfg.get("rq4") or {}).items():
            for c in load_cells(self.root / d):
                s = c["summary"]
                rows.append([mode, s.get("topology"), pol_id(s.get("policy", "")), fmt(s.get("accuracy")),
                             fmt(s.get("staleness_rate")), fmt(s.get("mean_tokens_per_q"), 0),
                             s.get("invalidations", "n/a"), s.get("cross_writer_invalidations", "n/a")])
        if not rows:
            return
        self.h(2, "9. RQ4: several agents sharing one memory")
        order = {p: i for i, p in enumerate(self.porder)}
        rows.sort(key=lambda r: (str(r[1]), r[0], order.get(r[2], 99)))
        self.table(["matching", "topology", "policy", "accuracy", "staleness", "tokens / q",
                    "contradictions closed", "closed by a different writer"], rows, "rq4.csv")
        single = self.bench.get("MQuAKE-T")
        if single:
            out = []
            for topo in sorted({r[1] for r in rows if r[0] == "normalized"}):
                v = {r[2]: float(r[3]) for r in rows if r[0] == "normalized" and r[1] == topo and r[3] != "n/a"}
                base = {p: mean(mean(r["correct"] for r in self.recs("MQuAKE-T", p, m))
                                for m in self.models("MQuAKE-T") if self.recs("MQuAKE-T", p, m))
                        for p in v}
                common = [p for p in v if p in base and p != "NOMEM"]
                if len(common) >= 3:
                    out.append([topo, len(common), fmt(spearman([base[p] for p in common], [v[p] for p in common]), 2)])
            if out:
                self.p("Does the single-agent ranking (MQuAKE-T, averaged over models) hold in each topology? "
                       "Spearman correlation of policy accuracies:")
                self.table(["topology", "policies compared", "Spearman with single agent"], out, "rq4_rank_transfer.csv")

    def s_grace(self):
        d = self.root / self.cfg.get("grace_history_dir", "")
        files = sorted(d.glob("*.json")) if d.is_dir() else []
        if not files:
            return
        self.h(2, "10. The grace period, with questions about the past")
        plt = _plt()
        fig, axes = plt.subplots(1, len(files), figsize=(4.2 * len(files), 3.2), squeeze=False)
        for ax, f in zip(axes[0], files):
            rows = [r for r in json.loads(f.read_text())["rows"] if r["model"] is None]
            order = {str(g): i for i, g in enumerate(self.cfg.get("grace_grid", [0, 1, 3, 5, 7, 10, 14, 21, "never"]))}
            rows.sort(key=lambda r: order.get(r["grace"], 99))
            xs = list(range(len(rows)))
            ax.plot(xs, [r["history_support"] for r in rows], marker="o", label="old value retrievable")
            ax.plot(xs, [r["current_gold"] for r in rows], marker="o", label="current value in context")
            ax2 = ax.twinx()
            ax2.plot(xs, [r["active_facts"] for r in rows], color="grey", ls="--", label="facts stored")
            ax.set_xticks(xs, [r["grace"] for r in rows])
            ax.set_xlabel("grace period (days)")
            ax.set_title(f.stem)
            ax.set_ylim(0, 1.05)
            if f is files[0]:
                ax.legend(frameon=False, fontsize=7, loc="lower right")
        fig.tight_layout()
        fig.savefig(self.fig_dir / "grace_history.png", dpi=200)
        plt.close(fig)
        self.fig("grace_history.png", "Grace period: history kept against storage, per benchmark")
        md = self.root / self.cfg.get("grace_history_md", "")
        if md.is_file():
            self.md += md.read_text().splitlines()[2:]

    def s_heldout(self):
        md = self.root / self.cfg.get("heldout_md", "")
        if md.is_file():
            self.h(2, "11. Retrieval weights on a benchmark the search never saw")
            self.md += md.read_text().splitlines()[2:]

    def s_findings(self):
        self.h(2, "12. Findings in one place")
        self.p("Generated from the numbers above. Each line is a measured result, not an interpretation; "
               "read it with its interval and its table.")
        self.md += [f"* {f}" for f in self.findings] + [""]

    def run(self) -> str:
        self.md = ["# DRIFT final campaign: deep analysis", "",
                   "Rebuilt from saved per-question records by `python -m analysis.final_report`."]
        if not self.bench:
            self.p("No final result cells found. Run the final matrix first.")
        else:
            self.s_integrity()
            self.s_main()
            self.s_rq1()
            self.s_rq2()
            self.s_rq3()
            self.s_models()
            self.s_ranks()
            self.s_judge()
            self.s_substrate()
        self.s_rq4()
        self.s_grace()
        self.s_heldout()
        self.s_findings()
        text = "\n".join(self.md) + "\n"
        out = self.root / self.cfg["out_md"]
        out.write_text(text)
        return str(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/final_analysis.json")
    ap.add_argument("--benchmarks", help="override, as name=dir,name=dir (for testing on other runs)")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads((root / args.config).read_text())
    if args.benchmarks:
        cfg["benchmarks"] = dict(kv.split("=", 1) for kv in args.benchmarks.split(","))
    print("wrote", Report(cfg, root).run())


if __name__ == "__main__":
    main()
