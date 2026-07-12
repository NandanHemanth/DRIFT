"""Publication-quality figures from DRIFT result directories.

Usage:
    python analysis/plots.py results/smoke                 # single-agent results
    python analysis/plots.py results/swarm_smoke --swarm   # swarm results
    python analysis/plots.py results/locomo -o figures/locomo

Outputs PNG (300 dpi) into <results_dir>/figures/ by default:
    accuracy_staleness.png   grouped bars: accuracy & staleness per policy
    tradeoff_scatter.png     accuracy vs staleness, point size = active facts
    memory_growth.png        active/total facts over sessions per policy
    token_cost.png           mean tokens per question per policy
    swarm_topology.png       (swarm) accuracy per policy per topology
    swarm_variance.png       (swarm) mean+/-std across independent agents
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

POLICY_LABELS = {
    "P0": "P0 no forgetting", "P1": "P1 TTL decay", "P2": "P2 contradiction",
    "P3": "P3 novelty gate", "P4": "P4 LLM consolidation",
}
POLICY_COLORS = {
    "P0": "#8888aa", "P1": "#e07b39", "P2": "#2a9d8f", "P3": "#7b6fb0", "P4": "#c94f5e",
}
TOPOLOGY_MARKERS = {"shared": "o", "independent": "s", "orchestrator": "^"}


def _pid(spec: str) -> str:
    return spec.split(":")[0]


def load_cells(results_dir: Path) -> list[dict]:
    cells = []
    for p in sorted(results_dir.glob("*.json")):
        if p.name == "summary_table.json":
            continue
        data = json.loads(p.read_text())
        if "summary" in data:
            cells.append(data)
    return cells


def _style(ax, title: str, ylabel: str = ""):
    ax.set_title(title, fontsize=11)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


# ------------------------------------------------------------- core figures

def fig_accuracy_staleness(cells: list[dict], out: Path):
    summaries = _dedupe_by_policy(cells)
    pids = [_pid(s["policy"]) for s in summaries]
    acc = [s["accuracy"] for s in summaries]
    stale = [s["staleness_rate"] for s in summaries]
    x = range(len(pids))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - 0.2 for i in x], acc, 0.4, label="accuracy",
           color=[POLICY_COLORS.get(p, "#999") for p in pids])
    ax.bar([i + 0.2 for i in x], stale, 0.4, label="staleness rate",
           color="#d0d0d0", edgecolor="#888", hatch="//")
    ax.set_xticks(list(x), [POLICY_LABELS.get(p, p) for p in pids],
                  rotation=20, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False)
    _style(ax, "Accuracy vs staleness by forgetting policy")
    fig.tight_layout(); fig.savefig(out / "accuracy_staleness.png", dpi=300); plt.close(fig)


def fig_tradeoff(cells: list[dict], out: Path):
    summaries = _dedupe_by_policy(cells)
    fig, ax = plt.subplots(figsize=(6, 5))
    seen_at: dict[tuple, int] = {}  # stack labels when points coincide
    for s in summaries:
        pid = _pid(s["policy"])
        mem = s.get("final_memory", {}) or {}
        size = 60 + 25 * mem.get("active_facts", 5)
        key = (round(s["staleness_rate"], 3), round(s["accuracy"], 3))
        stack = seen_at.get(key, 0)
        seen_at[key] = stack + 1
        ax.scatter(s["staleness_rate"], s["accuracy"], s=size,
                   color=POLICY_COLORS.get(pid, "#999"), alpha=0.85, zorder=3)
        ax.annotate(pid, (s["staleness_rate"], s["accuracy"]),
                    textcoords="offset points", xytext=(10, 4 - 12 * stack),
                    fontsize=9, color=POLICY_COLORS.get(pid, "#333"))
    ax.set_xlabel("staleness rate  (lower = better)")
    ax.set_ylabel("accuracy  (higher = better)")
    ax.annotate("ideal", xy=(0.005, 0.98), fontsize=9, color="#2a9d8f",
                xycoords="axes fraction", va="top")
    _style(ax, "Accuracy–staleness trade-off (point size = active facts)")
    fig.tight_layout(); fig.savefig(out / "tradeoff_scatter.png", dpi=300); plt.close(fig)


def fig_memory_growth(cells: list[dict], out: Path):
    fig, ax = plt.subplots(figsize=(7, 4))
    plotted = set()
    for cell in cells:
        pid = _pid(cell["summary"]["policy"])
        if pid in plotted:
            continue
        curve = cell.get("memory_curves") or cell.get("memory_curve") or []
        if not curve:
            continue
        plotted.add(pid)
        ax.plot(range(len(curve)), [c["active_facts"] for c in curve],
                label=POLICY_LABELS.get(pid, pid),
                color=POLICY_COLORS.get(pid, "#999"), linewidth=1.8)
    ax.set_xlabel("ingestion step (sessions over time)")
    ax.legend(frameon=False, fontsize=8)
    _style(ax, "Memory growth: active facts per policy", "active facts")
    fig.tight_layout(); fig.savefig(out / "memory_growth.png", dpi=300); plt.close(fig)


def fig_token_cost(cells: list[dict], out: Path):
    summaries = _dedupe_by_policy(cells)
    pids = [_pid(s["policy"]) for s in summaries]
    toks = [s["mean_tokens_per_q"] for s in summaries]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.bar(pids, toks, color=[POLICY_COLORS.get(p, "#999") for p in pids], width=0.55)
    _style(ax, "Answer cost by policy", "mean tokens / question")
    fig.tight_layout(); fig.savefig(out / "token_cost.png", dpi=300); plt.close(fig)


# ------------------------------------------------------------ swarm figures

def fig_swarm_topology(cells: list[dict], out: Path):
    by_topo: dict[str, list[dict]] = {}
    for c in cells:
        s = c["summary"]
        if "topology" in s:
            by_topo.setdefault(s["topology"], []).append(s)
    if not by_topo:
        return
    topos = list(by_topo)
    pids = sorted({_pid(s["policy"]) for ss in by_topo.values() for s in ss})
    width = 0.8 / len(topos)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for t_i, topo in enumerate(topos):
        lookup = {_pid(s["policy"]): s["accuracy"] for s in by_topo[topo]}
        xs = [i + t_i * width - 0.4 + width / 2 for i in range(len(pids))]
        ax.bar(xs, [lookup.get(p, 0) for p in pids], width * 0.92, label=topo,
               alpha=0.9 - 0.18 * t_i,
               color=[POLICY_COLORS.get(p, "#999") for p in pids],
               edgecolor="white")
    ax.set_xticks(range(len(pids)), [POLICY_LABELS.get(p, p) for p in pids],
                  rotation=20, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.legend(title="topology", frameon=False, fontsize=8)
    _style(ax, "Swarm: accuracy per policy across agent topologies", "accuracy")
    fig.tight_layout(); fig.savefig(out / "swarm_topology.png", dpi=300); plt.close(fig)


def fig_swarm_variance(cells: list[dict], out: Path):
    rows = [c["summary"] for c in cells
            if c["summary"].get("topology") == "independent" and "accuracy_std" in c["summary"]]
    if not rows:
        return
    pids = [_pid(s["policy"]) for s in rows]
    means = [s["accuracy_mean"] for s in rows]
    stds = [s["accuracy_std"] for s in rows]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.errorbar(pids, means, yerr=stds, fmt="o", capsize=6, linewidth=0,
                elinewidth=1.6, markersize=9,
                color="#2a9d8f", ecolor="#666")
    for p, m, sd in zip(pids, means, stds):
        ax.annotate(f"±{sd:.2f}", (p, m), textcoords="offset points",
                    xytext=(10, -4), fontsize=8, color="#666")
    ax.set_ylim(0, 1.05)
    _style(ax, "Independent agents (80% observation): accuracy mean ± std",
           "accuracy across agents")
    fig.tight_layout(); fig.savefig(out / "swarm_variance.png", dpi=300); plt.close(fig)


def _dedupe_by_policy(cells: list[dict]) -> list[dict]:
    """One summary per policy (first model / first topology wins), ordered P0..P4."""
    seen: dict[str, dict] = {}
    for c in cells:
        s = c["summary"]
        seen.setdefault(_pid(s["policy"]), s)
    return [seen[p] for p in sorted(seen)]


def main() -> None:
    parser = argparse.ArgumentParser(description="DRIFT figure generation")
    parser.add_argument("results_dir")
    parser.add_argument("-o", "--out", default=None, help="output dir (default: <results>/figures)")
    parser.add_argument("--swarm", action="store_true", help="also draw swarm figures")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out = Path(args.out) if args.out else results_dir / "figures"
    out.mkdir(parents=True, exist_ok=True)
    cells = load_cells(results_dir)
    if not cells:
        raise SystemExit(f"no result cells found in {results_dir}")

    fig_accuracy_staleness(cells, out)
    fig_tradeoff(cells, out)
    fig_memory_growth(cells, out)
    fig_token_cost(cells, out)
    if args.swarm:
        fig_swarm_topology(cells, out)
        fig_swarm_variance(cells, out)
    print(f"figures -> {out}/")


if __name__ == "__main__":
    main()
