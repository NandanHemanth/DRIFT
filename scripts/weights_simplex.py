"""Retrieval weights normalised to sum to 1 (the simplex), from the saved 1,000-weighting sweep.

1. Every grid weighting (s, l, r) is rescaled to sum to 1. Weightings that rescale to the
   same point rank facts identically, so their results must be identical; this is checked.
2. The 36 grid points that already sum to 1 (each weight 0.1 to 0.8 in steps of 0.1) are
   reported directly, and drawn on a triangle (ternary) plot.
No model is called.

Outputs: paper/tables_final/weights_sum1.csv, paper/figures_final/F14_weights_simplex.{png,pdf}
"""
import csv, json, sys, math
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from analysis.deep_sensitivity import Grid, _load_gz

CFG = json.loads((ROOT / "configs/deep_sensitivity_bydate.json").read_text())
D = ROOT / CFG["out_dir"]; MODELS = CFG["answer_models"]
LAB = {MODELS[0]: "Llama 3.1 8B", MODELS[1]: "Qwen3 8B"}
BENCH = {"mquake_t": "MQuAKE-T", "convomem": "ConvoMem"}

answers = {}
for line in (D / "results.jsonl").read_text().splitlines():
    if line.strip():
        r = json.loads(line); answers[(r["h"], r["m"])] = r
grids = {b["name"]: Grid(_load_gz(D / f"{b['name']}_plan.json.gz"), answers, MODELS) for b in CFG["benchmarks"]}

def norm(w):
    s = sum(w); return tuple(round(x / s, 6) for x in w)

rows, pts = [], {}
for name, G in grids.items():
    acc = G.per_w("P2", "correct"); st = G.per_w("P2", "stale"); gs = G.per_w("P2", "gold_support")
    accm = {m: G.per_w("P2", "correct", m) for m in MODELS}
    # 1. proportional groups give identical results
    groups = defaultdict(list)
    for i, w in enumerate(G.grid):
        groups[norm(w)].append(i)
    multi = [g for g in groups.values() if len(g) > 1]
    maxdiff = max(max(abs(acc[i] - acc[g[0]]) for i in g) for g in multi)
    prompts_same = all(len({G.f["P2"]["prompt"][i][q] for i in g}) == 1 for g in multi for q in range(len(G.q)))
    print(f"{BENCH[name]}: {len(groups)} distinct directions, {len(multi)} proportional groups; "
          f"identical prompts in every group: {prompts_same}; max accuracy difference within a group: {maxdiff:.4f}")
    # 2. sum-to-1 points
    idx = [i for i, w in enumerate(G.grid) if abs(sum(w) - 1.0) < 1e-6]
    order = sorted(idx, key=lambda i: -acc[i])
    pub = G.grid.index((0.6, 0.3, 0.1))
    rank = 1 + sum(acc[i] > acc[pub] for i in idx)
    print(f"  {len(idx)} weightings sum to 1; 0.6/0.3/0.1 accuracy {100*acc[pub]:.1f}% ranks {rank} of {len(idx)} "
          f"(ties share the better rank); best {100*acc[order[0]]:.1f}% at {G.grid[order[0]]}; worst {100*acc[order[-1]]:.1f}% at {G.grid[order[-1]]}")
    for i in idx:
        s, l, r = G.grid[i]
        rows.append([BENCH[name], s, l, r, f"{100*acc[i]:.1f}", f"{100*accm[MODELS[0]][i]:.1f}", f"{100*accm[MODELS[1]][i]:.1f}",
                     f"{100*st[i]:.1f}", f"{100*gs[i]:.1f}"])
    pts[name] = [(G.grid[i], acc[i], st[i]) for i in idx] + [("pub", acc[pub], st[pub])]
    a = np.array([acc[i] for i in idx])
    print(f"  over the 36: mean {100*a.mean():.1f}%, SD {100*a.std(ddof=1):.1f}, min {100*a.min():.1f}%, max {100*a.max():.1f}%; "
          f"share better than published {100*(a>acc[pub]).mean():.1f}%")
    rr = sorted(set(round(w[2],1) for w,_,_ in pts[name][:-1]))
    for rv in rr:
        v=[x for w,x,_ in pts[name][:-1] if round(w[2],1)==rv]
        print(f"    recency {rv:.1f}: mean acc {100*np.mean(v):.1f}% over {len(v)} weightings")

out = ROOT / "paper/tables_final/weights_sum1.csv"
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["benchmark", "semantic", "lexical", "recency", "accuracy_mean_%", "accuracy_llama_%", "accuracy_qwen_%", "staleness_%", "gold_in_prompt_%"])
    w.writerows(rows)

def tern(s, l, r):  # semantic at bottom-left, lexical bottom-right, recency top
    return l + r / 2, r * math.sqrt(3) / 2

fig, axes = plt.subplots(1, 2, figsize=(12, 5.4))
for ax, (name, P) in zip(axes, pts.items()):
    xs, ys, cs = [], [], []
    for w, a, _ in P[:-1]:
        x, y = tern(*w); xs.append(x); ys.append(y); cs.append(100 * a)
    sc = ax.scatter(xs, ys, c=cs, cmap="viridis", s=260, edgecolor="white", lw=0.8)
    for x, y, c in zip(xs, ys, cs):
        ax.text(x, y, f"{c:.0f}", ha="center", va="center", fontsize=7, color="white" if c < (min(cs)+max(cs))/2 else "black")
    x, y = tern(0.6, 0.3, 0.1)
    ax.scatter([x], [y], s=520, facecolor="none", edgecolor="#e76f51", lw=2.2, label="0.6 / 0.3 / 0.1")
    ax.plot([0, 1, 0.5, 0], [0, 0, math.sqrt(3)/2, 0], color="#999", lw=1)
    ax.text(-0.03, -0.05, "semantic = 1", ha="center", fontsize=9)
    ax.text(1.03, -0.05, "lexical = 1", ha="center", fontsize=9)
    ax.text(0.5, math.sqrt(3)/2 + 0.03, "recency = 1", ha="center", fontsize=9)
    ax.set_title(f"{BENCH[name]}: P2 accuracy (%), weights summing to 1", fontsize=10.5)
    ax.set_aspect("equal"); ax.axis("off")
    plt.colorbar(sc, ax=ax, shrink=0.7, label="accuracy (%)")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(ROOT / f"paper/figures_final/F14_weights_simplex.{ext}", dpi=200, bbox_inches="tight")
print("wrote", out)
