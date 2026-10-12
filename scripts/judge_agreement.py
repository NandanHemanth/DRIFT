"""Does the cheap judge grade like a strong one?

The final matrix is graded by one inexpensive judge so that 10,000 verdicts fit
the budget. That is only defensible if the cheap judge agrees with a strong
reference judge on the same answers. This script measures it before the matrix
is run, on answers that already exist (the published cells), so the check costs
judge calls only.

It draws a stratified sample (equal numbers of answers the published judge
marked correct and incorrect, spread over benchmarks), grades each with both
judges using the exact pipeline prompt, and reports raw agreement, Cohen's
kappa and the disagreement table. Disagreements are written out for reading.

Usage:
    python scripts/judge_agreement.py --cheap openrouter:deepseek/deepseek-v4.1-flash \
        --reference openrouter:anthropic/claude-sonnet-5.5 --n 200
    python scripts/judge_agreement.py --cheap mock --reference mock --n 20   # offline check
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drift.pipeline import judge_answer  # noqa: E402
from drift.providers import SpendLedger, make_provider  # noqa: E402
from drift.runner import configure_provider  # noqa: E402

SOURCES = ["artifacts/results/mquake_t", "artifacts/results/factconsolidation",
           "artifacts/results/convomem"]
NO_REASONING = {"reasoning": {"enabled": False}}


def load_pool(root: Path) -> list[dict]:
    pool = []
    for src in SOURCES:
        for f in sorted(glob.glob(str(root / src / "*.json"))):
            try:
                d = json.loads(Path(f).read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(d, dict) or "records" not in d:
                continue
            for r in d["records"]:
                if r.get("answer") and r.get("gold"):
                    pool.append({"bench": Path(src).name, "cell": Path(f).stem,
                                 "question": r["question"], "gold": r["gold"],
                                 "answer": r["answer"], "published": bool(r["correct"])})
    return pool


def stratified(pool: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    seen, uniq = set(), []
    for r in pool:                           # one copy of each distinct graded answer
        key = (r["question"], r["gold"], r["answer"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    groups: dict[tuple, list[dict]] = {}
    for r in uniq:
        groups.setdefault((r["bench"], r["published"]), []).append(r)
    per = max(1, n // len(groups))
    out = []
    for key in sorted(groups):
        g = groups[key]
        rng.shuffle(g)
        out.extend(g[:per])
    rng.shuffle(out)
    return out[:n]


def kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def judge(spec: str, cache_dir: str):
    """Grade with the same provider pin the final run uses, and no reasoning."""
    p = make_provider(spec, cache_dir)
    if spec.startswith("openrouter:"):
        final = Path(__file__).resolve().parents[1] / "configs/final_mquake_t.json"
        # Exactly the settings the final run uses for this model. Forcing
        # reasoning off is not possible on every model (some refuse the request).
        extras = dict(json.loads(final.read_text()).get("request_extras", {}).get(spec, {}))
        p = configure_provider(p, spec, {"request_extras": {spec: extras}})
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cheap", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="artifacts/judge_agreement.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    sample = stratified(load_pool(root), args.n, args.seed)
    if not sample:
        sys.exit("no graded answers found under artifacts/results/{mquake_t,factconsolidation,convomem}")
    cache = str(root / ".drift_cache")
    cheap, ref = judge(args.cheap, cache), judge(args.reference, cache)

    rows, skipped = [], []
    for i, r in enumerate(sample, 1):
        try:
            c = judge_answer(r["question"], r["gold"], r["answer"], cheap)["correct"]
            g = judge_answer(r["question"], r["gold"], r["answer"], ref)["correct"]
        except RuntimeError as exc:
            # A provider can refuse one item (OpenRouter returns 403 when its
            # moderation flags the text). Skip it and report it, rather than
            # losing the whole check.
            skipped.append({"question": r["question"], "error": str(exc)[:300]})
            if len(skipped) == 1:
                print(f"  item refused: {str(exc)[:300]}", flush=True)
            if len(skipped) >= 5 and not rows:
                raise SystemExit("The first 5 items all failed; stopping. Error above.")
            continue
        rows.append({**r, "cheap": c, "reference": g})
        if i % 25 == 0:
            print(f"  {i}/{len(sample)}  {SpendLedger.report()}", flush=True)

    if not rows:
        raise SystemExit(f"No item could be graded by both judges; first error: {skipped[0]['error'] if skipped else 'none'}")
    a = [r["cheap"] for r in rows]
    b = [r["reference"] for r in rows]
    agree = sum(x == y for x, y in zip(a, b)) / len(rows)
    report = {"cheap": args.cheap, "reference": args.reference, "n": len(rows),
              "agreement": round(agree, 4), "kappa": round(kappa(a, b), 4),
              "cheap_yes_ref_no": sum(x and not y for x, y in zip(a, b)),
              "cheap_no_ref_yes": sum(y and not x for x, y in zip(a, b)),
              "by_benchmark": {}}
    for bench in sorted({r["bench"] for r in rows}):
        sub = [r for r in rows if r["bench"] == bench]
        report["by_benchmark"][bench] = {
            "n": len(sub),
            "agreement": round(sum(r["cheap"] == r["reference"] for r in sub) / len(sub), 4)}
    report["disagreements"] = [r for r in rows if r["cheap"] != r["reference"]]
    report["skipped"] = skipped
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print(f"\n{args.cheap}  vs  {args.reference}   n={len(rows)}")
    print(f"agreement {agree:.3f}   kappa {report['kappa']:.3f}")
    print(f"cheap says correct, reference says incorrect: {report['cheap_yes_ref_no']}")
    print(f"cheap says incorrect, reference says correct: {report['cheap_no_ref_yes']}")
    for bench, v in report["by_benchmark"].items():
        print(f"  {bench:18s} n={v['n']:3d} agreement {v['agreement']:.3f}")
    if skipped:
        print(f"skipped {len(skipped)} item(s) the provider refused (listed in the json)")
    print(f"{SpendLedger.report()}\nwrote {out}")


if __name__ == "__main__":
    main()
