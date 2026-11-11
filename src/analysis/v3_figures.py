"""Figures for the v3 campaign, from artifacts/v3_analysis.json.

Every rate is plotted in percent on an axis from 0 to 100. Error bars are one
sample standard deviation over the three runs of the main matrix. Output:
paper/figures_v3/V*.png and .pdf.

Usage:
    python -m analysis.v3_figures
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R = json.loads((ROOT / "artifacts/v3_analysis.json").read_text())
OUT = ROOT / "paper/figures_v3"
OUT.mkdir(parents=True, exist_ok=True)

BENCH = {"mquake_t": "MQuAKE-T", "factconsolidation": "FactConsolidation", "convomem": "ConvoMem"}
MODELS = {"openai_gpt-6.1-sol": "GPT-6.1 Sol", "anthropic_claude-sonnet-5.5": "Claude Sonnet 5.5",
          "google_gemini-3.8-flash": "Gemini 3.8 Flash", "qwen_qwen3-14b": "Qwen3 14B",
          "meta-llama_llama-3.1-8b-instruct": "Llama 3.1 8B"}
POL = ["NOMEM", "P0", "P1", "P2", "P3", "P4", "P5"]
RANKED = ["P0", "P1", "P2", "P3", "P4", "P5"]
# Okabe-Ito colour-blind safe palette
CB = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]
SHORT = ["GPT-6.1", "Claude 5.5", "Gemini 3.8", "Qwen3 14B", "Llama 8B"]
PC = {"NOMEM": "#999999", "P0": CB[0], "P1": CB[5], "P2": CB[2], "P3": CB[1], "P4": CB[4], "P5": CB[3]}

plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e6e6",
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png")
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


def pctax(ax, label="%"):
    ax.set_ylim(0, 100)
    ax.set_ylabel(label)


def v(a):
    return (100 * a["mean"], 100 * a["sd"]) if a and a["mean"] is not None else (0, 0)


# V01: accuracy and staleness by policy (average of five models)
fig, axes = plt.subplots(2, 3, figsize=(10, 5.2), sharey="row")
for j, b in enumerate(BENCH):
    for i, (k, lab) in enumerate((("accuracy", "Accuracy (%)"), ("staleness", "Stale answers (%)"))):
        ax = axes[i, j]
        ms, ss = zip(*[v(R["policy_avg"][f"{b}|{p}"][k]) for p in POL])
        bars = ax.bar(POL, ms, yerr=ss, capsize=2, color=[PC[p] for p in POL], edgecolor="none")
        ax.set_xticks(range(len(POL)))
        ax.set_xticklabels(["None" if p == "NOMEM" else p for p in POL])
        for bar, m, e in zip(bars, ms, ss):
            ax.text(bar.get_x() + bar.get_width() / 2, m + e + 1.5, f"{m:.1f}", ha="center", va="bottom", fontsize=6.5)
        pctax(ax, lab if j == 0 else "")
        if i == 0:
            ax.set_title(BENCH[b])
fig.suptitle("Accuracy and stale answers by forgetting policy (mean of five answer models; error bars: SD over 3 runs; None = NOMEM)",
             fontsize=9.5, y=1.01)
save(fig, "V01_policy_accuracy_staleness")

# V02: P0 against P2 for every model
fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
for j, b in enumerate(BENCH):
    ax = axes[j]
    x = range(len(MODELS))
    for off, p in ((-0.2, "P0"), (0.2, "P2")):
        ms, ss = zip(*[v(R["cells"][f"{b}|{p}|{m}"]["accuracy"]) for m in MODELS])
        ax.bar([i + off for i in x], ms, 0.38, yerr=ss, capsize=2, color=PC[p], label=f"{p}")
        for i, m in zip(x, ms):
            ax.text(i + off, min(m, 92) / 2, f"{m:.0f}", ha="center", fontsize=6.5, color="white", rotation=90)
    ax.set_xticks(list(x))
    ax.set_xticklabels(SHORT, fontsize=7, rotation=30)
    pctax(ax, "Accuracy (%)" if j == 0 else "")
    ax.set_title(BENCH[b])
fig.legend(["P0 append-only", "P2 bitemporal invalidation"], loc="lower center", ncol=2, fontsize=7.5,
           bbox_to_anchor=(0.5, -0.08))
fig.suptitle("Append-only memory (P0) against bitemporal invalidation (P2), per answer model (error bars: SD over 3 runs)",
             fontsize=9.5, y=1.02)
save(fig, "V02_p0_vs_p2_by_model")

# V03: mechanism. Exposure (old value in prompt) and reading error, P0 and P2
fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
ax = axes[0]
w = 0.12
for i, p in enumerate(POL[1:]):
    vals = [v(R["policy_avg"][f"{b}|{p}"]["exposure"])[0] for b in BENCH]
    ax.bar([k + (i - 2.5) * w for k in range(3)], vals, w, color=PC[p], label=p)
ax.set_xticks(range(3))
ax.set_xticklabels(BENCH.values())
pctax(ax, "Questions with the old value in the prompt (%)")
ax.set_title("Exposure: does the superseded value reach the model?")
ax.legend(ncol=6, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.12))
ax = axes[1]
for i, b in enumerate(BENCH):
    vals = [v(R["cells"][f"{b}|P0|{m}"]["reading_error"])[0] for m in MODELS]
    ax.bar([k + (i - 1) * 0.27 for k in range(5)], vals, 0.27, color=CB[i], label=BENCH[b])
ax.set_xticks(range(5))
ax.set_xticklabels(SHORT, fontsize=7)
pctax(ax, "Stale answers when exposed (%)")
ax.set_title("Reading error under P0: who repeats the old value?")
ax.legend(fontsize=7)
save(fig, "V03_exposure_reading_error")

# V04: cost relative to P0 (prompt tokens per question and facts kept)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.2), sharey=True)
for ax, k, title in ((axes[0], "prompt_tokens", "Prompt tokens per question, % of P0"),
                     (axes[1], "facts_active", "Facts kept at the end, % of P0")):
    for i, p in enumerate(RANKED):
        vals = []
        for b in BENCH:
            base = R["policy_avg"][f"{b}|P0"][k]["mean"]
            vals.append(100 * R["policy_avg"][f"{b}|{p}"][k]["mean"] / base)
        bars = ax.bar([x + (i - 2.5) * 0.13 for x in range(3)], vals, 0.13, color=PC[p], label=p)
    ax.set_xticks(range(3))
    ax.set_xticklabels(BENCH.values())
    pctax(ax, "% of P0" if ax is axes[0] else "")
    ax.set_title(title)
axes[0].legend(ncol=6, fontsize=7, loc="upper center", bbox_to_anchor=(1.05, -0.1))
save(fig, "V04_cost_relative_to_p0")

# V05: forgetting correctness (complete and sound), MQuAKE-T and FactConsolidation
fig, axes = plt.subplots(1, 2, figsize=(10, 3.2), sharey=True)
for ax, b in zip(axes, ("mquake_t", "factconsolidation")):
    c = [v(R["correctness"][f"{b}|{p}"]["complete"]) for p in RANKED]
    s = [v(R["correctness"][f"{b}|{p}"]["sound"]) for p in RANKED]
    x = range(len(RANKED))
    ax.bar([i - 0.2 for i in x], [a for a, _ in c], 0.38, yerr=[e for _, e in c], capsize=2,
           color=CB[3], label="Complete: old value hidden")
    ax.bar([i + 0.2 for i in x], [a for a, _ in s], 0.38, yerr=[e for _, e in s], capsize=2,
           color=CB[0], label="Sound: current value still visible")
    ax.set_xticks(list(x))
    ax.set_xticklabels(RANKED)
    pctax(ax, "Changed facts (%)" if b == "mquake_t" else "")
    ax.set_title(BENCH[b])
fig.legend(["Complete: old value hidden", "Sound: current value still visible"], loc="lower center", ncol=2,
           fontsize=7.5, bbox_to_anchor=(0.5, -0.06))
fig.suptitle("Is each policy's forgetting correct? (end-of-run memory; error bars: SD over 3 runs)", fontsize=9.5, y=1.03)
save(fig, "V05_forgetting_correctness")

# V06: run-to-run stability. Flip rate per model and benchmark (mean over policies)
fl = defaultdict(list)
for k, val in R["flip"].items():
    b, p, m = k.split("|")
    if p != "NOMEM":
        fl[(b, m)].append(val)
fig, ax = plt.subplots(figsize=(7, 3))
for i, b in enumerate(BENCH):
    vals = [100 * sum(fl[(b, m)]) / len(fl[(b, m)]) for m in MODELS]
    ax.bar([k + (i - 1) * 0.27 for k in range(5)], vals, 0.27, color=CB[i], label=BENCH[b])
ax.set_xticks(range(5))
ax.set_xticklabels(SHORT, fontsize=7)
pctax(ax, "Questions whose grade changes across runs (%)")
ax.set_title("Flip rate across the three runs (mean over P0 to P5)")
ax.legend(fontsize=7)
save(fig, "V06_flip_rate")

# V07: RQ4 accuracy per policy, single agent against the three topologies
TOPO = {"single": ("Single agent (3-run mean)", "#000000", "o"), "shared": ("Shared (5 writers)", CB[0], "s"),
        "independent": ("Independent (3 agents, 80% of sessions)", CB[1], "^"),
        "orchestrator": ("Orchestrator (router + workers)", CB[2], "D")}
fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
for ax, b in zip(axes, BENCH):
    for t, (lab, col, mk) in TOPO.items():
        ys = []
        for p in RANKED:
            if t == "single":
                ys.append(100 * R["rq4"]["single"][b][p])
            else:
                c = R["rq4"]["cells"].get(f"{b}|{t}|{p}")
                ys.append(100 * c["accuracy"] if c else float("nan"))
        ax.plot(RANKED, ys, marker=mk, color=col, label=lab, lw=1.2, ms=4)
    pctax(ax, "Accuracy (%)" if b == "mquake_t" else "")
    ax.set_title(BENCH[b])
fig.legend([v[0] for v in TOPO.values()], loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, -0.07))
fig.suptitle("RQ4: accuracy of each policy under each topology (mean of five answer models)",
             fontsize=9.5, y=1.03)
save(fig, "V07_rq4_topologies")

# V08: ConvoMem shared memory, accuracy by the model that wrote each conversation
we = R["rq4"].get("writer_effect", {}).get("convomem")
if we:
    names = {"agent_0": "GPT-6.1 Sol", "agent_1": "Claude Sonnet 5.5", "agent_2": "Gemini 3.8 Flash",
             "agent_3": "Llama 3.1 8B", "agent_4": "Qwen3 14B"}
    acc = defaultdict(list)
    for conv, d in we.items():
        w_ = max(d["writers"], key=d["writers"].get)
        acc[w_].append(100 * d["accuracy"])
    fig, ax = plt.subplots(figsize=(6.5, 3))
    keys = sorted(acc)
    vals = [sum(acc[k]) / len(acc[k]) for k in keys]
    single = 100 * R["rq4"]["single"]["convomem"]["P0"]
    ax.bar([names[k] for k in keys], vals, color=CB[0])
    ax.axhline(single, color="#000000", ls="--", lw=1)
    ax.text(-0.4, single + 2, f"DeepSeek V4.1 Flash as extractor (main run): {single:.1f}", ha="left", fontsize=7)
    for i, val in enumerate(vals):
        ax.text(i, val + 2, f"{val:.0f}", ha="center", fontsize=7)
    pctax(ax, "Accuracy (%)")
    ax.set_title("ConvoMem, P0: accuracy by the model that extracted the conversation", fontsize=9)
    ax.tick_params(axis="x", labelsize=7)
    save(fig, "V08_convomem_extractor")

# V09: follow-ups. Contradiction matching and retrieval weighting (P2, mean of five models)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.2), sharey=True)
for ax, key, tags, title in ((axes[0], "matching", ["exact", "normalized", "llm"], "Contradiction matching"),
                             (axes[1], "weights", ["w631", "w912", "w811", "rec0", "rrf"], "Retrieval weighting")):
    labels = {"exact": "exact", "normalized": "normalised", "llm": "LLM", "w631": "0.6/0.3/0.1",
              "w912": "0.9/0.1/0.2", "w811": "0.8/0.1/0.1", "rec0": "0.6/0.3/0", "rrf": "RRF"}
    n = len(tags)
    for i, t in enumerate(tags):
        vals = []
        for b in BENCH:
            xs = [d["accuracy"] for k, d in R["followups"][key].items() if k.startswith(f"{b}|{t}|")]
            vals.append(100 * sum(xs) / len(xs) if xs else 0)
        ax.bar([x + (i - (n - 1) / 2) * 0.8 / n for x in range(3)], vals, 0.8 / n, color=CB[i], label=labels[t])
    ax.set_xticks(range(3))
    ax.set_xticklabels(BENCH.values())
    pctax(ax, "P2 accuracy (%)" if ax is axes[0] else "")
    ax.set_title(title)
    ax.legend(fontsize=7, ncol=n, loc="upper center", bbox_to_anchor=(0.5, -0.1))
save(fig, "V09_matching_and_weights")

# V10: grace period. Current and history accuracy against grace days
fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
for ax, b in zip(axes, BENCH):
    rows = R["followups"]["grace"].get(b, [])
    g = [r["grace"] for r in rows if r["model"] is None]
    cur, his, sto = [], [], []
    for gv in g:
        ms = [r for r in rows if r["model"] and r["grace"] == gv]
        cur.append(100 * sum(r["current_acc"] for r in ms) / len(ms))
        his.append(100 * sum(r["history_acc"] for r in ms) / len(ms))
        sto.append(100 * next(r["history_stored"] for r in rows if r["model"] is None and r["grace"] == gv))
    xs = range(len(g))
    ax.plot(xs, cur, marker="o", color=CB[2], label="Current-value accuracy")
    ax.plot(xs, his, marker="s", color=CB[3], label="History-question accuracy")
    ax.plot(xs, sto, ls="--", color="#777777", label="Old value still stored")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([str(x) for x in g], fontsize=7)
    ax.set_xlabel("P2 grace period (days)")
    pctax(ax, "%" if b == "mquake_t" else "")
    ax.set_title(BENCH[b])
fig.legend(["Current-value accuracy", "History-question accuracy", "Old value still stored"], loc="lower center",
           ncol=3, fontsize=7.5, bbox_to_anchor=(0.5, -0.1))
fig.suptitle("What the grace period buys: history recall rises, current accuracy does not move (mean of five models)",
             fontsize=9.5, y=1.03)
save(fig, "V10_grace")

print("figures in", OUT)
