"""Evidence pack generator: every table, chart, and view for report and paper.

For each results directory this produces `<dir>/report_pack/` containing:

  index.md                   entry point linking everything
  summary_table.md / .csv    main results table (policy x model x topology)
  per_category.md / .csv     accuracy per question category per policy
  baseline_vs_drift.md/.png  NOMEM (no memory) vs P0 (no policy) vs P2 (DRIFT)
  radar_policies.png         multi-metric radar per policy
  figures/                   all standard figures (bars, trade-off, growth,
                             cost, model comparison, swarm)
  memory_view.md             final memory stats, pruned fact text, superseded
                             fact text per cell (needs "save_graph": true)
  graphs/                    node-link JSON + interactive HTML per cell
  architecture.png           pipeline diagram for the paper/report

Usage:
    python analysis/record.py results/smoke results/swarm_smoke
    python analysis/record.py results/*            # after make real-all
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # src/ on path for `analysis.*`
from analysis.graphify_export import HTML as GRAPH_HTML  # noqa: E402
from analysis.graphify_export import facts_to_graph  # noqa: E402
from analysis.timeline import HTML as TIMELINE_HTML  # noqa: E402
from analysis.timeline import build as build_timeline  # noqa: E402
from analysis.plots import (POLICY_COLORS, POLICY_LABELS, fig_accuracy_staleness,  # noqa: E402
                            fig_memory_growth, fig_model_comparison, fig_swarm_topology,
                            fig_swarm_variance, fig_token_cost, fig_tradeoff, load_cells)


def _pid(spec: str) -> str:
    return spec.split(":")[0]


def load_full_cells(results_dir: Path) -> list[dict]:
    cells = []
    for p in sorted(results_dir.glob("*.json")):
        if p.name.endswith(".graph.json") or p.name == "summary_table.json":
            continue
        data = json.loads(p.read_text())
        if "summary" in data:
            data["_file"] = p.stem
            cells.append(data)
    return cells


# ------------------------------------------------------------------- tables

def write_summary_tables(cells: list[dict], out: Path) -> None:
    rows = []
    for c in cells:
        s = c["summary"]
        rows.append({
            "policy": s["policy"], "model": s.get("model", ""),
            "topology": s.get("topology", ""), "n_questions": s.get("n_questions", 0),
            "accuracy": round(s.get("accuracy", 0), 3),
            "f1": round(s.get("mean_f1", 0), 3),
            "staleness": round(s.get("staleness_rate", 0), 3),
            "tokens_per_q": round(s.get("mean_tokens_per_q", 0)),
            "active_facts": (s.get("final_memory") or {}).get("active_facts", ""),
            "pruned": (s.get("final_memory") or {}).get("pruned", ""),
            "write_rejections": (s.get("final_memory") or {}).get("write_rejections", ""),
            "cross_writer_invalidations": s.get("cross_writer_invalidations", ""),
        })
    rows.sort(key=lambda r: (str(r["topology"]), _pid(r["policy"]), str(r["model"])))
    headers = list(rows[0].keys())
    with (out / "summary_table.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(r[h]) for h in headers) + " |" for r in rows]
    (out / "summary_table.md").write_text(
        "# Summary table\n\n" + "\n".join(lines) + "\n")


def write_per_category(cells: list[dict], out: Path) -> None:
    table: dict[str, dict[str, list[int]]] = {}
    for c in cells:
        pid = _pid(c["summary"]["policy"])
        for r in c.get("records", []):
            cat = r.get("category", "single_hop")
            table.setdefault(cat, {}).setdefault(pid, []).append(int(r["correct"]))
    if not table:
        return
    pids = sorted({p for d in table.values() for p in d})
    lines = ["| category | " + " | ".join(pids) + " |", "|" + "---|" * (len(pids) + 1)]
    csv_rows = []
    for cat in sorted(table):
        vals = []
        for p in pids:
            xs = table[cat].get(p, [])
            vals.append(f"{sum(xs)/len(xs):.2f}" if xs else "-")
        lines.append(f"| {cat} | " + " | ".join(vals) + " |")
        csv_rows.append({"category": cat, **dict(zip(pids, vals))})
    (out / "per_category.md").write_text(
        "# Accuracy per question category\n\n" + "\n".join(lines) + "\n")
    with (out / "per_category.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["category"] + pids)
        w.writeheader()
        w.writerows(csv_rows)


# ------------------------------------------------------------------- charts

def fig_radar(cells: list[dict], out: Path) -> None:
    """Five-axis radar per policy: accuracy, freshness, F1, memory and token
    efficiency (higher is better on every axis)."""
    seen: dict[str, dict] = {}
    for c in cells:
        s = c["summary"]
        seen.setdefault(_pid(s["policy"]), s)
    if len(seen) < 2:
        return
    max_facts = max(((s.get("final_memory") or {}).get("active_facts") or 1)
                    for s in seen.values()) or 1
    max_tok = max((s.get("mean_tokens_per_q") or 1) for s in seen.values()) or 1
    axes_labels = ["accuracy", "freshness\n(1 - staleness)", "F1",
                   "memory\nefficiency", "token\nefficiency"]
    n = len(axes_labels)
    angles = [i * 2 * math.pi / n for i in range(n)] + [0.0]
    fig, ax = plt.subplots(figsize=(6.5, 6), subplot_kw={"polar": True})
    for pid in sorted(seen):
        s = seen[pid]
        mem = (s.get("final_memory") or {}).get("active_facts") or max_facts
        vals = [s.get("accuracy", 0), 1 - s.get("staleness_rate", 0), s.get("mean_f1", 0),
                1 - mem / max_facts if max_facts else 0,
                1 - (s.get("mean_tokens_per_q") or max_tok) / max_tok]
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=1.6, label=POLICY_LABELS.get(pid, pid),
                color=POLICY_COLORS.get(pid, "#999"))
        ax.fill(angles, vals, alpha=0.06, color=POLICY_COLORS.get(pid, "#999"))
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axes_labels, fontsize=8)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8, frameon=False)
    ax.set_title("Policy profiles (larger area is better)", fontsize=11, pad=18)
    fig.tight_layout()
    fig.savefig(out / "radar_policies.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_baseline_vs_drift(cells: list[dict], out: Path) -> None:
    """The headline comparison: agent without memory (NOMEM), agent with memory
    but no policy (P0), DRIFT agent (P2)."""
    seen: dict[str, dict] = {}
    for c in cells:
        s = c["summary"]
        seen.setdefault(_pid(s["policy"]), s)
    trio = [p for p in ["NOMEM", "P0", "P2"] if p in seen]
    if len(trio) < 2:
        return
    labels = {"NOMEM": "No memory", "P0": "Memory, no policy", "P2": "DRIFT (P2)"}
    metrics = [("accuracy", "accuracy"), ("staleness_rate", "staleness"),
               ("mean_tokens_per_q", "tokens/q (norm.)")]
    max_tok = max((seen[p].get("mean_tokens_per_q") or 1) for p in trio) or 1
    x = range(len(metrics))
    width = 0.8 / len(trio)
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, p in enumerate(trio):
        vals = []
        for key, _ in metrics:
            v = seen[p].get(key, 0) or 0
            vals.append(v / max_tok if key == "mean_tokens_per_q" else v)
        xs = [j + i * width - 0.4 + width / 2 for j in x]
        ax.bar(xs, vals, width * 0.9, label=labels[p],
               color=POLICY_COLORS.get(p, "#999"))
    ax.set_xticks(list(x), [m[1] for m in metrics])
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("Baseline agents vs DRIFT agent", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "baseline_vs_drift.png", dpi=300)
    plt.close(fig)
    lines = ["# Baseline vs DRIFT\n",
             "| agent | accuracy | staleness | tokens/q | active facts |",
             "|---|---|---|---|---|"]
    for p in trio:
        s = seen[p]
        lines.append(f"| {labels[p]} | {s.get('accuracy',0):.3f} | "
                     f"{s.get('staleness_rate',0):.3f} | "
                     f"{round(s.get('mean_tokens_per_q',0))} | "
                     f"{(s.get('final_memory') or {}).get('active_facts','-')} |")
    if "P0" in seen and "P2" in seen:
        d_acc = seen["P2"]["accuracy"] - seen["P0"]["accuracy"]
        d_st = seen["P0"]["staleness_rate"] - seen["P2"]["staleness_rate"]
        lines.append(f"\nDRIFT delta over no-policy agent: accuracy {d_acc:+.3f}, "
                     f"staleness reduced by {d_st:.3f}.")
    (out / "baseline_vs_drift.md").write_text("\n".join(lines) + "\n")


# ------------------------------------------------------------- memory views

def write_memory_view(cells: list[dict], out: Path) -> None:
    lines = ["# Memory view\n",
             "What each policy did to memory. Pruned and superseded fact text is",
             "recovered from graph snapshots (cells run with \"save_graph\": true).\n"]
    graphs_dir = out / "graphs"
    for c in cells:
        s = c["summary"]
        name = c["_file"]
        fm = s.get("final_memory") or {}
        lines.append(f"\n## {name}")
        lines.append(f"policy `{s['policy']}` · model `{s.get('model','-')}` · "
                     f"topology `{s.get('topology','-')}`")
        lines.append(f"- total facts ever written: {fm.get('total_facts','-')}")
        lines.append(f"- active at end: {fm.get('active_facts','-')} · "
                     f"pruned: {fm.get('pruned','-')} · "
                     f"write rejections: {fm.get('write_rejections','-')} · "
                     f"superseded still visible: {fm.get('invalidated_active','-')}")
        snap = c.get("graph_snapshot")
        if not snap:
            lines.append("- (no snapshot; enable \"save_graph\": true for fact-level views)")
            continue
        pruned = [f for f in snap if not f.get("active", True)]
        superseded = [f for f in snap if f.get("t_invalid_at") is not None]
        if pruned:
            lines.append(f"- **pruned fact text** ({len(pruned)}):")
            lines += [f"    - ~~{f['text']}~~ (written by {f.get('provenance','?')})"
                      for f in pruned[:20]]
        if superseded:
            lines.append(f"- **superseded facts** ({len(superseded)}):")
            lines += [f"    - {f['text']}  ->  invalidated at t={f['t_invalid_at']}"
                      for f in superseded[:20]]
        graphs_dir.mkdir(exist_ok=True)
        g = facts_to_graph(snap)
        (graphs_dir / f"{name}.graph.json").write_text(json.dumps(g, indent=1))
        (graphs_dir / f"{name}.graph.html").write_text(
            GRAPH_HTML.replace("__GRAPH__", json.dumps(g)))
        lines.append(f"- interactive graph: `graphs/{name}.graph.html` · "
                     f"data: `graphs/{name}.graph.json` · "
                     f"communities: {g['graph']['n_communities']} · "
                     f"god nodes: {', '.join(g['graph']['god_nodes'][:3])}")

        # Scrubbable replay of the same cell. The static graph above shows where
        # memory ended up; this shows how it got there, which is the only view
        # in which a supersession is an event rather than an attribute.
        try:
            payload = build_timeline([c], [s["policy"]])
            (graphs_dir / f"{name}.replay.html").write_text(
                TIMELINE_HTML.replace("__DATA__", json.dumps(payload)))
            lines.append(f"- **replay** (scrub through time): "
                         f"`graphs/{name}.replay.html` · "
                         f"{len(payload['times'])} sessions · "
                         f"{len(payload['events'])} with a supersession")
        except SystemExit:
            pass  # no snapshot times; the static graph above still stands
    (out / "memory_view.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------- architecture view

def fig_architecture(out: Path) -> None:
    stages = [
        ("Sessions", "multi-agent\nconversations"),
        ("Extraction", "LLM triples +\nregex predicates"),
        ("Write gate", "hook 1\nP3 / NOMEM"),
        ("Bitemporal\ngraph", "valid + ingestion\ntime, provenance"),
        ("Maintenance", "hook 2\nP1 P2 P4 P5"),
        ("Retrieval", "hybrid search +\nhook 3 (P2)"),
        ("Answer +\nJudge", "answer LLM,\nindependent judge"),
    ]
    fig, ax = plt.subplots(figsize=(12, 2.8))
    ax.axis("off")
    for i, (title, sub) in enumerate(stages):
        x = i * 1.55
        box = plt.Rectangle((x, 0.25), 1.3, 1.0, fc="#eef1f6", ec="#5b6478",
                            lw=1.2, zorder=2, joinstyle="round")
        ax.add_patch(box)
        ax.text(x + 0.65, 1.02, title, ha="center", va="center",
                fontsize=9.5, fontweight="bold", zorder=3)
        ax.text(x + 0.65, 0.55, sub, ha="center", va="center",
                fontsize=7.2, color="#444", zorder=3)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + 1.55, 0.75), xytext=(x + 1.3, 0.75),
                        arrowprops={"arrowstyle": "->", "color": "#5b6478", "lw": 1.4})
    ax.plot([2.9, 8.05], [1.55, 1.55], color="#2a9d8f", lw=1.2, ls="--")
    ax.text(5.5, 1.66, "forgetting policy acts at three hooks",
            ha="center", fontsize=8.5, color="#2a9d8f")
    ax.set_xlim(-0.2, 10.9)
    ax.set_ylim(0, 1.9)
    fig.tight_layout()
    fig.savefig(out / "architecture.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------- main

def build_pack(results_dir: Path) -> None:
    cells = load_full_cells(results_dir)
    if not cells:
        print(f"[skip] {results_dir}: no result cells")
        return
    out = results_dir / "report_pack"
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    write_summary_tables(cells, out)
    write_per_category(cells, out)
    fig_radar(cells, out)
    fig_baseline_vs_drift(cells, out)
    write_memory_view(cells, out)
    fig_architecture(out)

    slim = load_cells(results_dir)  # summary+curves view used by plots.py
    fig_accuracy_staleness(slim, figs)
    fig_tradeoff(slim, figs)
    fig_memory_growth(slim, figs)
    fig_token_cost(slim, figs)
    fig_model_comparison(slim, figs)
    fig_swarm_topology(slim, figs)
    fig_swarm_variance(slim, figs)

    entries = sorted(p.name for p in out.rglob("*") if p.is_file() and p.name != "index.md")
    (out / "index.md").write_text(
        f"# Evidence pack: {results_dir.name}\n\n"
        + "Generated by `python analysis/record.py`. Drop tables into the report,\n"
        + "PNGs into the paper, open HTML files in a browser.\n\n"
        + "\n".join(f"- {e}" for e in entries) + "\n")
    print(f"[pack] {out}  ({len(entries)} artifacts)")


def main() -> None:
    dirs = [Path(d) for d in sys.argv[1:]] or [Path("results/smoke")]
    for d in dirs:
        if d.is_dir():
            build_pack(d)


if __name__ == "__main__":
    main()
