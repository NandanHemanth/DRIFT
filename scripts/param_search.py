"""End-to-end parameter search for P2's grace period and the retrieval weighting.

The sensitivity sweep in src/analysis/sensitivity.py is free but measures
retrieval only. It answers "does the conclusion depend on this constant?".
It cannot answer "which value is best", because its metrics are flat across
most of the range and it never calls the answer model.

This script answers the second question the way it has to be answered: by
running the real pipeline at each candidate value and comparing accuracy,
staleness, and token cost. Every cell is a normal runner cell, produced by the
same run_cell() the published campaigns use, so the numbers are directly
comparable to Chapter 5.

Candidates are pre-screened by the free sweep. For the weighting, only settings
that hold gold support at its ceiling are worth running, since gold support is a
hard upper bound on accuracy: if the gold fact is not in the context, a
memory-only prompt cannot produce it.

Usage:
    python scripts/param_search.py --config configs/mquake_t.json --search grace
    python scripts/param_search.py --config configs/mquake_t.json --search weights
    python scripts/param_search.py --config configs/mquake_t.json --search grace --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drift.runner import load_dataset, run_cell  # noqa: E402

# Committee asked for 1 to 21 days. 21 is included as the upper bound, and 1 as
# the lower, with three points between them.
GRACE_DAYS = [1.0, 3.0, 7.0, 14.0, 21.0]

# Every candidate below holds gold support at 1.000 on MQuAKE-T, so each one can
# in principle reach the accuracy the published setting reaches. They are chosen
# to be as far apart on the simplex as that constraint allows, which is what
# makes a null result here informative rather than a foregone conclusion.
WEIGHT_CANDIDATES = [
    (0.6, 0.3, 0.1),   # published
    (0.4, 0.4, 0.2),   # best clean among the gold-perfect set
    (0.0, 1.0, 0.0),   # pure lexical corner
    (1.0, 0.0, 0.0),   # pure semantic corner
    (0.5, 0.3, 0.2),   # more recency than published
    # Deliberately included as a falsification test. It has the highest clean
    # score of any weighting, but its gold support is only 0.927, so accuracy
    # should be capped near that. If it wins anyway, the gold-support-as-ceiling
    # argument is wrong and needs rewriting.
    (0.3, 0.4, 0.3),
]

# Reciprocal rank fusion takes no weights at all. It is the method Zep uses, so
# including it turns "which weighting is best" into the more useful question of
# whether the weighted formula earns its hyperparameter at all.
RRF_ARM = "rrf"


def tag_weights(w) -> str:
    return "w" + "-".join(f"{int(round(x * 100)):03d}" for x in w)


def short_model(spec: str) -> str:
    return spec.split("/")[-1].split(":")[0].replace(".", "")


def plan(cfg: dict, search: str, policies: list[str] | None, models: list[str]):
    """Yields (cell_name, cfg_override, policy_spec, model) for each experiment."""
    for model in models:
        tag = f"__{short_model(model)}" if len(models) > 1 else ""
        if search == "grace":
            for g in GRACE_DAYS:
                yield f"P2_grace{int(g):02d}d{tag}", {}, f"P2:grace_days={g}", model
        else:
            for w in WEIGHT_CANDIDATES:
                for pol in (policies or ["P2"]):
                    yield (f"{pol}_{tag_weights(w)}{tag}",
                           {"retrieval_weights": list(w)}, pol, model)
            for pol in (policies or ["P2"]):
                yield f"{pol}_{RRF_ARM}{tag}", {"retrieval_fusion": RRF_ARM}, pol, model


def main() -> None:
    ap = argparse.ArgumentParser(description="End-to-end parameter search")
    ap.add_argument("--config", required=True, help="base campaign config to inherit from")
    ap.add_argument("--search", required=True, choices=["grace", "weights"])
    ap.add_argument("--policies", nargs="*", help="policies for the weights search (default P2)")
    ap.add_argument("--out", help="results dir (default artifacts/results/param_<search>_<name>)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--models", nargs="*",
                    help="answer models to sweep (default: every model in the config)")
    ap.add_argument("--dry-run", action="store_true", help="list the cells and exit")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    dataset = load_dataset(cfg["dataset"])
    name = Path(args.config).stem
    out_dir = Path(args.out or f"artifacts/results/param_{args.search}_{name}")
    out_dir.mkdir(parents=True, exist_ok=True)

    models = args.models or cfg["models"]
    cells = list(plan(cfg, args.search, args.policies, models))
    n_q = sum(len(c["questions"]) for c in dataset["conversations"])
    print(f"{len(cells)} cells over {len(models)} model(s) -> {out_dir}")
    for cell, _, spec, model in cells:
        print(f"  {cell:<34} {spec:<22} {model}")
    print(f"\n{n_q} questions per cell, so at most "
          f"{len(cells) * n_q} answer calls and {len(cells) * n_q} judge calls "
          f"(cached cells cost nothing)")
    if args.dry_run:
        return

    summaries = []
    for cell, override, spec, model in cells:
        out_path = out_dir / f"{cell}.json"
        if out_path.exists() and not args.force:
            print(f"[skip] {cell}")
            summaries.append({"cell": cell, **json.loads(out_path.read_text())["summary"]})
            continue
        print(f"[run ] {cell}")
        cell_cfg = {**cfg, **override}
        try:
            s = run_cell(spec, model, dataset, cell_cfg, out_path)
        except (RuntimeError, OSError) as e:
            print(f"[fail] {cell}: {str(e)[:140]}")
            continue
        print(f"       acc={s['accuracy']:.3f} stale={s['staleness_rate']:.3f} "
              f"tok/q={s['mean_tokens_per_q']:.0f}")
        summaries.append({"cell": cell, "answer_model": model, **s})

    (out_dir / "search_summary.json").write_text(json.dumps(summaries, indent=1))

    header = f"| {'cell':<28} | model | accuracy | staleness | tok/q | facts |"
    lines = ["", f"### {args.search} search on {name}", "", header,
             "|" + "|".join(["---"] * 6) + "|"]
    for s in summaries:
        facts = s.get("final_memory", {}).get("active_facts", "")
        lines.append(f"| {s['cell']:<28} | {short_model(s.get('answer_model',''))} "
                     f"| {s['accuracy']:.3f} | {s['staleness_rate']:.3f} "
                     f"| {s['mean_tokens_per_q']:.0f} | {facts} |")
    table = "\n".join(lines)
    (out_dir / "search_summary.md").write_text(table + "\n")
    print(table)
    print(f"\nWrote {out_dir / 'search_summary.md'}")


if __name__ == "__main__":
    main()
