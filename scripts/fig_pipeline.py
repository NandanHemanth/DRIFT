"""Figure 3.1: the DRIFT pipeline as configured for the final run.

Writes paper/figures_final/F00_pipeline.{png,pdf}. Labels follow
configs/final_*.json and src/drift/policies.py (which hook each policy uses).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "paper" / "figures_final"

STAGES = [
    ("Sessions", "dated conversation\nsessions", False),
    ("Extraction", "DeepSeek V4.1 Flash\ntriples + rule pass", False),
    ("Write hook", "on_write\n(P3)", True),
    ("Bitemporal\ngraph", "valid + ingestion time;\ncontradiction closes\nthe old fact", False),
    ("Maintenance\nhook", "after_session\n(P1, P2, P4, P5)", True),
    ("Retrieval", "0.6 cos + 0.3 lex\n+ 0.1 recency, top 25", False),
    ("Retrieval\nhook", "on_retrieve\n(P2, NOMEM)", True),
    ("Answer +\ngrading", "5 answer models;\nrules + DeepSeek judge", False),
]

POLICY = "#2a9d8f"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 2.9))
    ax.axis("off")
    step, w = 1.6, 1.36
    for i, (title, sub, hook) in enumerate(STAGES):
        x = i * step
        box = plt.Rectangle((x, 0.2), w, 1.1,
                            fc="#e6f4f2" if hook else "#eef1f6",
                            ec=POLICY if hook else "#5b6478",
                            lw=1.6 if hook else 1.1, zorder=2)
        ax.add_patch(box)
        ax.text(x + w / 2, 1.04, title, ha="center", va="center",
                fontsize=9.5, fontweight="bold", zorder=3)
        ax.text(x + w / 2, 0.52, sub, ha="center", va="center",
                fontsize=7.2, color="#333", zorder=3)
        if i < len(STAGES) - 1:
            ax.annotate("", xy=(x + step, 0.75), xytext=(x + w, 0.75),
                        arrowprops={"arrowstyle": "->", "color": "#5b6478", "lw": 1.3})
    ax.text(len(STAGES) * step / 2 - 0.12, 1.55,
            "highlighted: the three points where the forgetting policy acts; "
            "everything else is identical in every cell",
            ha="center", fontsize=8.5, color=POLICY)
    ax.set_xlim(-0.15, len(STAGES) * step)
    ax.set_ylim(0, 1.75)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"F00_pipeline.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {OUT}/F00_pipeline.png and .pdf")


if __name__ == "__main__":
    main()
