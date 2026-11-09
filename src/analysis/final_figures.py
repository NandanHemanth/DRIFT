"""Publication figures for the final campaign, drawn from artifacts/final_results.json.

Usage:
    python -m analysis.final_figures
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper/figures_final"
TEAL, RUST, INK, MUTE, GOLD, BLUE, PLUM = "#0F766E", "#B5523B", "#1F2933", "#7B8794", "#C08A1E", "#3B6EA8", "#7A4E8C"
POLCOL = {"NOMEM": "#BFC5CC", "P0": "#7B8794", "P1": "#C08A1E", "P2": TEAL, "P3": RUST, "P4": PLUM, "P5": BLUE}
POLNAME = {"NOMEM": "NOMEM no memory", "P0": "P0 append-only", "P1": "P1 time decay", "P2": "P2 bitemporal",
           "P3": "P3 novelty gate", "P4": "P4 LLM consolidation", "P5": "P5 topology"}
BENCH = ["MQuAKE-T", "FactConsolidation", "ConvoMem"]
plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#C9CED4", "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.titleweight": "bold", "axes.titlesize": 10})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=220)
    plt.close(fig)
    print("  ", name)


def main() -> None:
    R = json.loads((ROOT / "artifacts/final_results.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    lab = {m: v["label"] for m, v in R["models"].items()}
    B = R["benchmarks"]
    models = B["MQuAKE-T"]["models"]

    # F1 headline: accuracy and staleness per policy, averaged over models
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.4), sharey="row")
    for j, b in enumerate(BENCH):
        ps = B[b]["policies"]
        for i, key in enumerate(("accuracy", "staleness")):
            ax = axes[i][j]
            vals = [B[b]["policy_avg"][p][key] for p in ps]
            ax.bar(ps, vals, color=[POLCOL[p] for p in ps])
            for x, v in enumerate(vals):
                ax.text(x, v + 0.01, f"{v:.2f}", ha="center", fontsize=7)
            if i == 0:
                ax.set_title(b)
            ax.set_ylabel(key if j == 0 else "")
            ax.set_ylim(0, 1.08 if key == "accuracy" else 0.4)
    save(fig, "F01_headline_accuracy_staleness.png")

    # F2 P0 vs P2 per model (dumbbell)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
    for ax, b in zip(axes, BENCH):
        for y, m in enumerate(models):
            a0 = B[b]["cells"][f"P0|{m}"]["accuracy"]
            a2 = B[b]["cells"][f"P2|{m}"]["accuracy"]
            ax.plot([a0, a2], [y, y], color="#C9CED4", lw=2, zorder=1)
            ax.scatter([a0], [y], color=POLCOL["P0"], s=40, zorder=2, label="P0 append-only" if y == 0 else None)
            ax.scatter([a2], [y], color=TEAL, s=40, zorder=3, label="P2 bitemporal" if y == 0 else None)
        ax.set_yticks(range(len(models)), [lab[m] for m in models])
        ax.set_xlim(0, 1.02)
        ax.set_title(b)
        ax.set_xlabel("accuracy")
    axes[0].legend(frameon=False, fontsize=7, loc="lower left")
    save(fig, "F02_p0_vs_p2_by_model.png")

    # F3 mechanism: old value in the prompt, and how often each model repeats it
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
    ax = axes[0]
    xs = range(len(BENCH))
    e0 = [B[b]["cells"][f"P0|{models[0]}"]["old_value_in_prompt"] for b in BENCH]
    e2 = [B[b]["cells"][f"P2|{models[0]}"]["old_value_in_prompt"] for b in BENCH]
    ax.bar([x - 0.18 for x in xs], e0, 0.36, color=POLCOL["P0"], label="P0 append-only")
    ax.bar([x + 0.18 for x in xs], e2, 0.36, color=TEAL, label="P2 bitemporal")
    for x, a, c in zip(xs, e0, e2):
        ax.text(x - 0.18, a + 0.02, f"{a:.2f}", ha="center", fontsize=7)
        ax.text(x + 0.18, c + 0.02, f"{c:.2f}", ha="center", fontsize=7)
    ax.set_xticks(list(xs), BENCH)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("share of questions")
    ax.set_title("Old value reaches the prompt")
    ax.legend(frameon=False, fontsize=7)
    ax = axes[1]
    w = 0.8 / len(BENCH)
    for k, b in enumerate(BENCH[:2]):
        vals = [B[b]["cells"][f"P0|{m}"]["reading_error"] or 0 for m in models]
        ax.bar([i + k * 0.38 - 0.19 for i in range(len(models))], vals, 0.38,
               color=[TEAL, GOLD][k], label=b)
        for i, v in enumerate(vals):
            ax.text(i + k * 0.38 - 0.19, v + 0.01, f"{v:.2f}", ha="center", fontsize=7)
    ax.set_xticks(range(len(models)), [lab[m] for m in models], rotation=12)
    ax.set_ylabel("stale answers when old value shown")
    ax.set_title("Reading error under P0 (model falls for the old value)")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "F03_mechanism_exposure_reading_error.png")

    # F4 cost: prompt tokens per policy, and USD per 1,000 correct answers
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
    ax = axes[0]
    ps = [p for p in B["MQuAKE-T"]["policies"] if p != "NOMEM"]
    for k, b in enumerate(BENCH):
        vals = [B[b]["policy_avg"][p]["prompt_tokens"] for p in ps]
        ax.plot(ps, vals, marker="o", color=[TEAL, GOLD, RUST][k], label=b)
    ax.set_ylabel("prompt tokens per question")
    ax.set_title("Prompt size by policy (mean over models)")
    ax.legend(frameon=False, fontsize=7)
    ax = axes[1]
    for k, b in enumerate(BENCH[:2]):
        vals = [B[b]["cells"][f"P2|{m}"]["usd_per_1k_correct"] for m in models]
        ax.bar([i + k * 0.38 - 0.19 for i in range(len(models))], vals, 0.38, color=[TEAL, GOLD][k], label=b)
        for i, v in enumerate(vals):
            ax.text(i + k * 0.38 - 0.19, v * 1.15, f"${v:.2f}", ha="center", fontsize=6.5)
    ax.set_yscale("log")
    ax.set_xticks(range(len(models)), [lab[m] for m in models], rotation=12)
    ax.set_ylabel("USD per 1,000 correct answers (log)")
    ax.set_title("Cost of a correct answer under P2")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "F04_tokens_and_cost.png")

    # F5 small vs frontier: what P2 adds over P0, by tier
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    tiers = ["frontier", "mid", "small"]
    for k, b in enumerate(BENCH):
        vals = [R["tiers"][b].get(t, {}).get("acc_gain", 0) for t in tiers]
        ax.bar([i + (k - 1) * 0.26 for i in range(3)], vals, 0.26, color=[TEAL, GOLD, RUST][k], label=b)
        for i, v in enumerate(vals):
            ax.text(i + (k - 1) * 0.26, v + (0.006 if v >= 0 else -0.025), f"{v:+.2f}", ha="center", fontsize=7)
    ax.axhline(0, color=MUTE, lw=0.8)
    ax.set_xticks(range(3), ["frontier (GPT, Claude)", "mid (Gemini Flash)", "small (Llama 8B, Qwen 14B)"])
    ax.set_ylabel("accuracy gain, P2 over P0")
    ax.set_title("Who benefits from forgetting")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "F05_gain_by_model_tier.png")

    # F6 RQ3: P2 against P5 per model
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=True)
    for ax, b in zip(axes, BENCH):
        a2 = [B[b]["cells"][f"P2|{m}"]["accuracy"] for m in models]
        a5 = [B[b]["cells"][f"P5|{m}"]["accuracy"] for m in models]
        xs = range(len(models))
        ax.bar([x - 0.19 for x in xs], a2, 0.38, color=TEAL, label="P2 bitemporal")
        ax.bar([x + 0.19 for x in xs], a5, 0.38, color=BLUE, label="P5 topology, time-blind")
        ax.set_xticks(list(xs), [lab[m].split()[0] for m in models])
        ax.set_title(b)
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("accuracy")
    axes[0].legend(frameon=False, fontsize=7)
    save(fig, "F06_rq3_p2_vs_p5.png")

    # F7 RQ4
    rq = R["rq4"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
    pol = ["P0", "P1", "P2", "P3", "P4", "P5"]
    groups = [("normalized", "independent"), ("normalized", "orchestrator"), ("exact", "shared"),
              ("normalized", "shared"), ("llm", "shared")]
    names = ["independent", "orchestrator", "shared, exact", "shared, normalised", "shared, LLM"]
    cols = [MUTE, GOLD, "#9CC9C3", TEAL, "#0A4F49"]
    for ax, key in zip(axes, ("accuracy", "staleness")):
        for k, (g, nm, col) in enumerate(zip(groups, names, cols)):
            vals = [next((x[key] for x in rq if x["matching"] == g[0] and x["topology"] == g[1]
                          and x["policy"] == p), 0) for p in pol]
            ax.bar([i + (k - 2) * 0.16 for i in range(len(pol))], vals, 0.16, color=col, label=nm)
        ax.set_xticks(range(len(pol)), pol)
        ax.set_title(f"RQ4 {key} by topology (MQuAKE-T, Gemini answers)")
        ax.set_ylabel(key)
    axes[0].legend(frameon=False, fontsize=6.5, ncol=2, loc="lower left")
    save(fig, "F07_rq4_topologies.png")

    # F8 grace
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    for ax, b in zip(axes, BENCH):
        rows = R["grace"].get(b, [])
        if not rows:
            continue
        xs = range(len(rows))
        for m, col in zip(["openrouter:meta-llama/llama-3.1-8b-instruct", "openrouter:qwen/qwen3-14b"], [RUST, TEAL]):
            ax.plot(xs, [r.get(m, {}).get("history", 0) for r in rows], marker="o", color=col,
                    label=f"history Q, {lab[m]}")
            ax.plot(xs, [r.get(m, {}).get("current", 0) for r in rows], ls=":", color=col,
                    label=f"current Q, {lab[m]}")
        ax2 = ax.twinx()
        ax2.plot(xs, [r["facts"] for r in rows], color=MUTE, ls="--", lw=1)
        ax2.set_ylabel("facts stored (dashed)", color=MUTE)
        ax.set_xticks(list(xs), [str(r["grace"]) for r in rows])
        ax.set_xlabel("grace period (days)")
        ax.set_ylim(0, 1.05)
        ax.set_title(b)
    axes[0].set_ylabel("accuracy")
    axes[0].legend(frameon=False, fontsize=6, loc="center left", bbox_to_anchor=(0.0, 0.62))
    save(fig, "F08_grace_tradeoff.png")

    # F9 substrate
    sub = R["substrate"]
    fig, ax = plt.subplots(figsize=(8.5, 3.3))
    modes = ["exact", "normalized", "llm"]
    combos = [(b, m) for b in BENCH for m in ["openrouter:meta-llama/llama-3.1-8b-instruct", "openrouter:qwen/qwen3-14b"]]
    for k, mode in enumerate(modes):
        vals = [next((x["accuracy"] for x in sub if x["benchmark"] == b and x["model"] == m and x["mode"] == mode), 0)
                for b, m in combos]
        ax.bar([i + (k - 1) * 0.26 for i in range(len(combos))], vals, 0.26,
               color=["#9CC9C3", TEAL, "#0A4F49"][k], label=mode)
    ax.set_xticks(range(len(combos)), [f"{b}\n{lab[m].split()[0]}" for b, m in combos], fontsize=7)
    ax.set_ylabel("P2 accuracy")
    ax.set_title("How contradictions are detected: exact, normalised, LLM (Zep-style)")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "F09_substrate_matching.png")

    # F10 heldout weights
    hd = R["heldout"]
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    tags = [("w631", "0.6/0.3/0.1\npublished"), ("w912", "0.9/0.1/0.2\nMQuAKE-T best"), ("w811", "0.8/0.1/0.1\nConvoMem best")]
    for k, m in enumerate(["openrouter:meta-llama/llama-3.1-8b-instruct", "openrouter:qwen/qwen3-14b"]):
        vals = [next((x["accuracy"] for x in hd if x["weights"] == t and x["model"] == m), 0) for t, _ in tags]
        ax.bar([i + (k - 0.5) * 0.36 for i in range(3)], vals, 0.36, color=[RUST, TEAL][k], label=lab[m])
        for i, v in enumerate(vals):
            ax.text(i + (k - 0.5) * 0.36, v + 0.01, f"{v:.2f}", ha="center", fontsize=7)
    ax.set_xticks(range(3), [t for _, t in tags])
    ax.set_ylim(0, 1)
    ax.set_ylabel("accuracy (FactConsolidation, P2)")
    ax.set_title("Retrieval weights on an unseen benchmark")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "F10_heldout_weights.png")

    # F11 cost vs accuracy scatter (every policy x model, two fact benchmarks)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    marks = {m: mk for m, mk in zip(models, ["o", "s", "^", "D", "v"])}
    for ax, b in zip(axes, BENCH[:2]):
        for key, c in B[b]["cells"].items():
            p, m = key.split("|")
            if p == "NOMEM":
                continue
            ax.scatter(c["prompt_tokens"], c["accuracy"], color=POLCOL[p], marker=marks[m], s=30, alpha=.85)
        ax.set_xlabel("prompt tokens per question")
        ax.set_ylabel("accuracy")
        ax.set_title(b)
    hs = [plt.Line2D([], [], color=POLCOL[p], marker="o", ls="", label=POLNAME[p]) for p in ["P0", "P1", "P2", "P3", "P4", "P5"]]
    hs += [plt.Line2D([], [], color=INK, marker=marks[m], ls="", label=lab[m]) for m in models]
    axes[1].legend(handles=hs, frameon=False, fontsize=6, loc="lower left", ncol=2)
    save(fig, "F11_cost_accuracy_scatter.png")

    # F12 diagnostics: extraction ceiling and P4 deletions
    pf = {r["benchmark"]: r for r in R.get("preflight", [])}
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2))
    ax = axes[0]
    det = [pf.get(k, {}).get("detected_normalized", 0) / max(1, pf.get(k, {}).get("questions", 1))
           for k in ("mquake_t_sh", "factconsolidation_sh_6k", "convomem_changing")]
    ax.bar(BENCH, det, color=TEAL)
    for x, v in enumerate(det):
        ax.text(x, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.set_title("Changes P2 can act on (old value closed)")
    ax.set_ylabel("share of questions with a superseded answer")
    ax = axes[1]
    p4 = {"MQuAKE-T": (3, 2, 1), "FactConsolidation": (65, 49, 10), "ConvoMem": (120, 8, 8)}
    xs = range(3)
    ax.bar([x - 0.25 for x in xs], [p4[b][0] for b in BENCH], 0.25, color=MUTE, label="pruned by P4")
    ax.bar(list(xs), [p4[b][1] for b in BENCH], 0.25, color=RUST, label="holding a current answer")
    ax.bar([x + 0.25 for x in xs], [p4[b][2] for b in BENCH], 0.25, color=GOLD, label="holding an old answer")
    ax.set_xticks(list(xs), BENCH)
    ax.set_title("What LLM consolidation (P4) deletes")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "F12_detection_and_p4.png")


if __name__ == "__main__":
    main()
