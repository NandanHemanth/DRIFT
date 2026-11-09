"""Checkpoint 2: distribution of results across all 1,000 retrieval weightings.

Reads the completed deep sensitivity run (artifacts/deep_sensitivity_bydate),
computes, for every weighting, accuracy and staleness under P2 (per model and
averaged over the two models) and retrieval gold support, then reports mean,
variance, standard deviation, min, max and where the published 0.6/0.3/0.1 sits.

Outputs:
  paper/tables_final/weights_1000_summary.csv
  paper/figures_final/F13_weights_1000_distribution.{png,pdf}

No model is called; everything comes from saved results.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analysis.deep_sensitivity import Grid, _load_gz  # noqa: E402

CFG = json.loads((ROOT / "configs/deep_sensitivity_bydate.json").read_text())
D = ROOT / CFG["out_dir"]
MODELS = CFG["answer_models"]
LABEL = {MODELS[0]: "Llama 3.1 8B", MODELS[1]: "Qwen3 8B"}
BENCH = {"mquake_t": "MQuAKE-T", "convomem": "ConvoMem"}
PUBLISHED = (0.6, 0.3, 0.1)
POL = "P2"


def load():
    answers = {}
    for line in (D / "results.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            answers[(r["h"], r["m"])] = r
    return {b["name"]: Grid(_load_gz(D / f"{b['name']}_plan.json.gz"), answers, MODELS)
            for b in CFG["benchmarks"]}


def stats(v: np.ndarray, pub: float, lower_better: bool = False) -> dict:
    better = (v < pub) if lower_better else (v > pub)
    worse = (v > pub) if lower_better else (v < pub)
    return {"n": len(v), "mean": v.mean(), "variance": v.var(ddof=1), "sd": v.std(ddof=1),
            "min": v.min(), "p25": np.percentile(v, 25), "median": np.median(v),
            "p75": np.percentile(v, 75), "max": v.max(), "published": pub,
            "pct_better_than_published": 100.0 * better.mean(),
            "pct_worse_than_published": 100.0 * worse.mean()}


def main() -> None:
    grids = load()
    rows, series = [], {}
    for name, G in grids.items():
        ok = G.usable(POL)
        pi = G.grid.index(PUBLISHED)
        assert ok[pi], "published weighting not fully answered"
        for metric, key in (("accuracy", "correct"), ("staleness", "stale")):
            for m in MODELS + [None]:
                v = G.per_w(POL, key, m)
                who = LABEL[m] if m else "mean of both"
                s = stats(v[ok], v[pi], lower_better=(metric == "staleness"))
                rows.append({"benchmark": BENCH[name], "metric": metric, "model": who, **s})
                series[(name, metric, who)] = (v[ok], v[pi])
        gs = G.per_w(POL, "gold_support")
        s = stats(gs[ok], gs[pi])
        rows.append({"benchmark": BENCH[name], "metric": "gold fact reaches prompt",
                     "model": "retrieval (no model)", **s})

    out_t = ROOT / "paper/tables_final/weights_1000_summary.csv"
    with out_t.open("w", newline="") as fh:
        w = csv.writer(fh)
        keys = ["benchmark", "metric", "model", "n", "mean", "variance", "sd", "min",
                "p25", "median", "p75", "max", "published", "pct_better_than_published",
                "pct_worse_than_published"]
        w.writerow(keys)
        for r in rows:
            w.writerow([r[k] if isinstance(r[k], (str, int)) else f"{r[k]:.4f}" for k in keys])
    for r in rows:
        print(f"{r['benchmark']:9s} {r['metric']:25s} {r['model']:21s} n={r['n']} "
              f"mean={r['mean']:.3f} var={r['variance']:.4f} sd={r['sd']:.3f} "
              f"min={r['min']:.3f} max={r['max']:.3f} published={r['published']:.3f} "
              f"| weightings better {r['pct_better_than_published']:.1f}% worse {r['pct_worse_than_published']:.1f}%")

    # figure: rows = benchmark, cols = accuracy / staleness
    who_order = ["Llama 3.1 8B", "Qwen3 8B", "mean of both"]
    colors = ["#5b6478", "#8a6fb3", "#2a9d8f"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2))
    rng = np.random.default_rng(7)
    for i, name in enumerate(grids):
        for j, metric in enumerate(("accuracy", "staleness")):
            ax = axes[i, j]
            for k, who in enumerate(who_order):
                v, pub = series[(name, metric, who)]
                x = k + rng.uniform(-0.28, 0.28, len(v))
                ax.scatter(x, v * 100, s=4, alpha=0.25, color=colors[k], lw=0)
                mu, sd = v.mean() * 100, v.std(ddof=1) * 100
                ax.errorbar(k + 0.42, mu, yerr=sd, fmt="o", color="black", ms=4, capsize=4, lw=1.2)
                ax.plot([k - 0.32, k + 0.32], [v.min() * 100] * 2, color="#999", lw=1)
                ax.plot([k - 0.32, k + 0.32], [v.max() * 100] * 2, color="#999", lw=1)
                ax.scatter([k], [pub * 100], marker="*", s=140, color="#e76f51",
                           edgecolor="white", lw=0.6, zorder=5)
            ax.set_xticks(range(3))
            ax.set_xticklabels(who_order, fontsize=9)
            ax.set_ylim(0, 100)
            ax.set_ylabel(f"{metric} (%)")
            ax.set_title(f"{BENCH[name]}: {metric} across 1,000 weightings (P2)", fontsize=10)
            ax.grid(axis="y", color="#eee")
            ax.spines[["top", "right"]].set_visible(False)
    handles = [
        plt.Line2D([], [], marker="o", ls="", color="#888", alpha=0.5, label="one weighting"),
        plt.Line2D([], [], marker="o", color="black", label="mean ± 1 SD"),
        plt.Line2D([], [], color="#999", label="min / max"),
        plt.Line2D([], [], marker="*", ls="", ms=12, color="#e76f51", label="published 0.6 / 0.3 / 0.1"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out_f = ROOT / "paper/figures_final"
    for ext in ("png", "pdf"):
        fig.savefig(out_f / f"F13_weights_1000_distribution.{ext}", dpi=200, bbox_inches="tight")
    print(f"wrote {out_t} and {out_f}/F13_weights_1000_distribution.png")


if __name__ == "__main__":
    main()
