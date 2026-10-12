"""Held-out test of the retrieval weighting on FactConsolidation.

The deep sensitivity search picked a "best" weighting on MQuAKE-T (0.9/0.1/0.2)
and on ConvoMem (0.8/0.1/0.1), and found the published 0.6/0.3/0.1 inside the
statistical plateau on MQuAKE-T but just outside it on ConvoMem. A weighting
chosen on the same questions it is scored on is optimistic by construction
(about +0.05 there). The honest test is a benchmark that played no part in the
search. FactConsolidation is that benchmark.

This script reads the paired P2 cells written by the three
configs/heldout_weights_fc_*.json runs and compares each candidate with the
published weighting per model, using an exact two-sided McNemar test on the
questions where the two weightings disagree.

Usage:
    python scripts/heldout_weights.py
"""
from __future__ import annotations

import glob
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "artifacts/results/heldout_weights_fc"
LABELS = {"w631": "0.6/0.3/0.1 (published)", "w912": "0.9/0.1/0.2 (MQuAKE-T best)",
          "w811": "0.8/0.1/0.1 (ConvoMem best)"}


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def load(tag: str) -> dict[str, dict]:
    out = {}
    for f in glob.glob(str(ROOT / tag / "P2__*.json")):
        d = json.loads(Path(f).read_text())
        out[d["summary"]["model"]] = d
    return out


def main() -> None:
    base = load("w631")
    if not base:
        raise SystemExit(f"no cells under {ROOT}/w631; run the heldout-weights target first")
    lines = ["# Held-out weighting test (FactConsolidation, P2)", "",
             "| model | weighting | accuracy | staleness | better / worse vs published | McNemar p |",
             "|---|---|---|---|---|---|"]
    for model, b in sorted(base.items()):
        bs = b["summary"]
        lines.append(f"| {model.split('/')[-1]} | {LABELS['w631']} | {bs['accuracy']:.3f} | "
                     f"{bs['staleness_rate']:.3f} | - | - |")
        for tag in ("w912", "w811"):
            other = load(tag).get(model)
            if not other:
                continue
            pairs = list(zip(b["records"], other["records"]))
            assert all(x["question"] == y["question"] for x, y in pairs)
            better = sum(y["correct"] and not x["correct"] for x, y in pairs)
            worse = sum(x["correct"] and not y["correct"] for x, y in pairs)
            s = other["summary"]
            lines.append(f"| {model.split('/')[-1]} | {LABELS[tag]} | {s['accuracy']:.3f} | "
                         f"{s['staleness_rate']:.3f} | {better} / {worse} | "
                         f"{mcnemar_exact(better, worse):.3f} |")
    text = "\n".join(lines) + "\n"
    (ROOT / "heldout_weights.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
