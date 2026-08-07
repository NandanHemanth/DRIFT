"""Cross-dataset comparison: does the policy ranking generalize?

A result on one benchmark is a measurement; the same ranking on a second
benchmark with different properties is a finding. This script puts two (or more)
results directories side by side and answers three questions a reviewer will ask
about the FactConsolidation result:

  1. Do the policies rank the same way on both datasets?  (Spearman rho over
     per-policy accuracy, plus the raw ranks so a single swapped pair is visible
     rather than hidden inside a correlation coefficient.)
  2. Is P2 still statistically tied with P0, and is P3 still the staleness
     outlier?  (Paired McNemar exact test within each dataset -- the same
     questions go to every policy, so an unpaired test would overstate
     significance.)
  3. How wide are the per-policy accuracy intervals?  (Bootstrap percentile CI,
     so "0.840 vs 0.795" is reported with the uncertainty that makes it
     interpretable.)

Everything is stdlib -- no scipy, no numpy -- to keep the core dependency-free
promise in pyproject.toml. The exact binomial p-value for McNemar is computed
directly from the binomial PMF, which is tractable because discordant-pair
counts here are small.

Usage:
    python analysis/compare_datasets.py results/factconsolidation results/mquake_t
    python analysis/compare_datasets.py results/factconsolidation results/mquake_t \\
        --out results/generalization.md
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

BOOTSTRAP = 5000
SEED = 42


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #

def load_cells(results_dir: Path) -> list[dict]:
    """Every per-cell results JSON in a directory (skipping derived artifacts)."""
    cells = []
    for f in sorted(results_dir.glob("*.json")):
        if f.name in {"summary_table.json"}:
            continue
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if "summary" in data and "records" in data:
            cells.append(data)
    return cells


def by_policy(cells: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for c in cells:
        out[c["summary"]["policy"]].append(c)
    return out


def pooled_records(cells: list[dict]) -> list[dict]:
    """All per-question records for a policy, pooled across answer models."""
    return [r for c in cells for r in c["records"]]


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #

def bootstrap_ci(values: list[float], n: int = BOOTSTRAP,
                 seed: int = SEED) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for a mean."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    k = len(values)
    means = []
    for _ in range(n):
        means.append(sum(values[rng.randrange(k)] for _ in range(k)) / k)
    means.sort()
    return (means[int(0.025 * n)], means[int(0.975 * n)])


def binom_two_sided(b: int, c: int) -> float:
    """Exact two-sided binomial p for McNemar's test on discordant pairs.

    Under H0 each discordant pair is a fair coin, so the p-value is the total
    probability of a split at least as extreme as (b, c).
    """
    n = b + c
    if n == 0:
        return 1.0
    obs = min(b, c)
    total = 0.0
    for k in range(0, obs + 1):
        total += math.comb(n, k)
    p = 2.0 * total / (2 ** n)
    return min(1.0, p)


def mcnemar(a_records: list[dict], b_records: list[dict],
            field: str = "correct") -> tuple[int, int, float]:
    """Paired comparison keyed on question text.

    Records are pooled across models, so the key includes the conversation id to
    avoid collapsing two different conversations that happen to share a question.
    Returns (A-only wins, B-only wins, p).
    """
    def index(records):
        out = {}
        for r in records:
            out.setdefault((r.get("conversation", ""), r["question"]), []).append(r)
        return out

    ai, bi = index(a_records), index(b_records)
    b_wins = c_wins = 0
    for key, ra in ai.items():
        rb = bi.get(key)
        if not rb or len(ra) != len(rb):
            continue
        for x, y in zip(ra, rb):
            if x[field] and not y[field]:
                b_wins += 1
            elif y[field] and not x[field]:
                c_wins += 1
    return b_wins, c_wins, binom_two_sided(b_wins, c_wins)


def spearman(a: list[float], b: list[float]) -> float:
    """Rank correlation with average ranks for ties. Pure stdlib."""
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        rk = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk

    ra, rb = ranks(a), ranks(b)
    n = len(a)
    if n < 2:
        return float("nan")
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((r - ma) ** 2 for r in ra))
    db = math.sqrt(sum((r - mb) ** 2 for r in rb))
    return num / (da * db) if da and db else float("nan")


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def stale_coverage(conv_ids: set[str], data_dir: str = "data") -> tuple[str, int, int]:
    """Find the dataset file that produced these records and count annotations.

    Records carry the conversation id they came from, so the source file can be
    recovered without threading the config through -- which matters because
    staleness coverage is a property of the dataset, and reporting a staleness
    rate without it is how a metric that structurally cannot fire gets mistaken
    for a policy result.
    """
    conv_ids = {c for c in conv_ids if c}
    for f in sorted(Path(data_dir).glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        convs = d.get("conversations")
        if not isinstance(convs, list):
            continue
        ids = {c.get("id") for c in convs}
        if not conv_ids or not conv_ids & ids:
            continue
        qs = [q for c in convs if c.get("id") in conv_ids
              for q in c.get("questions", [])]
        return f.name, len(qs), sum(1 for q in qs if q.get("stale_answer"))
    return "not found", 0, 0


def policy_stats(cells: list[dict]) -> dict:
    recs = pooled_records(cells)
    n = len(recs)
    if not n:
        return {}
    acc = [1.0 if r["correct"] else 0.0 for r in recs]
    stale = [1.0 if r["stale"] else 0.0 for r in recs]
    lo, hi = bootstrap_ci(acc)
    slo, shi = bootstrap_ci(stale)
    mem = [c["summary"].get("final_memory", {}) for c in cells]
    active = [m.get("active_facts") for m in mem if m.get("active_facts") is not None]
    return {
        "n": n,
        "accuracy": sum(acc) / n,
        "acc_ci": (lo, hi),
        "f1": sum(r["f1"] for r in recs) / n,
        "staleness": sum(stale) / n,
        "stale_ci": (slo, shi),
        "tokens": sum(r["tokens"] for r in recs) / n,
        "active_facts": (sum(active) / len(active)) if active else None,
    }


def render(dirs: list[Path]) -> str:
    L: list[str] = []
    data: dict[str, dict[str, dict]] = {}   # dataset -> policy -> stats
    raw: dict[str, dict[str, list[dict]]] = {}  # dataset -> policy -> cells

    for d in dirs:
        cells = load_cells(d)
        if not cells:
            L.append(f"> **{d.name}**: no result cells found -- skipped.\n")
            continue
        grouped = by_policy(cells)
        raw[d.name] = grouped
        data[d.name] = {p: policy_stats(cs) for p, cs in grouped.items()}

    if len(data) < 1:
        return "No comparable results directories.\n"

    names = list(data)
    policies = sorted({p for ds in data.values() for p in ds},
                      key=lambda p: (p != "NOMEM", p))

    L.append("# Cross-dataset generalization\n")
    L.append("Every figure below is pooled over the answer models in each "
             "results directory. Accuracy and staleness carry percentile "
             "bootstrap 95% CIs (5,000 resamples); policy-vs-policy tests are "
             "paired McNemar exact, because the same questions go to every "
             "policy.\n")

    # ---- headline table ---------------------------------------------------
    L.append("## 1. Accuracy and staleness, side by side\n")
    head = "| Policy | " + " | ".join(
        f"{n} acc | {n} stale" for n in names) + " |"
    L.append(head)
    L.append("|---" * (1 + 2 * len(names)) + "|")
    for p in policies:
        cells_out = []
        for n in names:
            s = data[n].get(p)
            if not s:
                cells_out += ["-", "-"]
                continue
            cells_out.append(
                f"{s['accuracy']:.3f} [{s['acc_ci'][0]:.3f}, {s['acc_ci'][1]:.3f}]")
            cells_out.append(
                f"{s['staleness']:.3f} [{s['stale_ci'][0]:.3f}, {s['stale_ci'][1]:.3f}]")
        L.append(f"| {p} | " + " | ".join(cells_out) + " |")
    L.append("")

    L.append("## 2. Cost and memory footprint\n")
    L.append("| Policy | " + " | ".join(
        f"{n} tok/q | {n} active facts" for n in names) + " |")
    L.append("|---" * (1 + 2 * len(names)) + "|")
    for p in policies:
        row = []
        for n in names:
            s = data[n].get(p)
            if not s:
                row += ["-", "-"]
                continue
            row.append(f"{s['tokens']:.0f}")
            row.append(f"{s['active_facts']:.0f}" if s["active_facts"] else "-")
        L.append(f"| {p} | " + " | ".join(row) + " |")
    L.append("")

    # ---- rank agreement ---------------------------------------------------
    if len(names) >= 2:
        L.append("## 3. Does the ranking survive the dataset change?\n")
        shared = [p for p in policies if all(p in data[n] for n in names)]
        L.append("| Policy | " + " | ".join(f"{n} rank" for n in names) + " |")
        L.append("|---" * (1 + len(names)) + "|")
        order = {n: sorted(shared, key=lambda p: -data[n][p]["accuracy"])
                 for n in names}
        for p in shared:
            L.append(f"| {p} | " + " | ".join(
                str(order[n].index(p) + 1) for n in names) + " |")
        L.append("")
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = [data[names[i]][p]["accuracy"] for p in shared]
                b = [data[names[j]][p]["accuracy"] for p in shared]
                rho = spearman(a, b)
                L.append(f"Spearman rho ({names[i]} vs {names[j]}) over "
                         f"{len(shared)} policies: **{rho:.3f}**")
                if rho >= 0.9:
                    L.append("  -> the ranking is essentially preserved; the "
                             "policy effect is a property of forgetting, not of "
                             "one corpus.")
                elif rho >= 0.6:
                    L.append("  -> broadly preserved with local swaps; name the "
                             "swapped pair explicitly rather than claiming a "
                             "clean replication.")
                else:
                    L.append("  -> the ranking does **not** transfer. The "
                             "single-dataset conclusion should be reported as "
                             "regime-specific.")
                L.append("")

    # ---- paired tests within each dataset ---------------------------------
    L.append("## 4. Paired tests within each dataset\n")
    L.append("`A better` / `B better` count discordant pairs only. "
             "p is the exact two-sided binomial.\n")
    key_pairs = [("P0", "P2"), ("P2", "P3"), ("P2", "P5"), ("P0", "P1"),
                 ("P2", "P4")]
    for n in names:
        L.append(f"### {n}\n")
        L.append("| Comparison | Metric | A better | B better | p |")
        L.append("|---|---|---|---|---|")
        for a, b in key_pairs:
            if a not in raw[n] or b not in raw[n]:
                continue
            ra, rb = pooled_records(raw[n][a]), pooled_records(raw[n][b])
            for field, label in (("correct", "accuracy"), ("stale", "staleness")):
                x, y, p = mcnemar(ra, rb, field)
                if x == 0 and y == 0:
                    continue
                ps = "<0.001" if p < 0.001 else f"{p:.3f}"
                L.append(f"| {a} vs {b} | {label} | {x} | {y} | {ps} |")
        L.append("")

    # ---- staleness coverage warning ---------------------------------------
    L.append("## 5. Staleness metric power\n")
    L.append("Staleness can only fire on questions carrying a `stale_answer` "
             "annotation. A dataset with low coverage reports a low staleness "
             "rate for structural reasons, not policy reasons -- which is the "
             "trap LoCoMo (0/300) and LongMemEval (0/150) fell into.\n")
    L.append("| Dataset | Source file | Questions | Annotated | Coverage |")
    L.append("|---|---|---|---|---|")
    for n in names:
        any_policy = next(iter(raw[n].values()))
        conv_ids = {r.get("conversation", "") for r in any_policy[0]["records"]}
        src, nq, na = stale_coverage(conv_ids)
        cov = f"{na / nq:.0%}" if nq else "-"
        L.append(f"| {n} | {src} | {nq or '-'} | {na or '-'} | {cov} |")
    L.append("")
    L.append("> A 0% row means the staleness column below it is uninformative: "
             "the metric could not fire regardless of policy. This is exactly "
             "what happened on LoCoMo (0/300) and LongMemEval (0/150) in the "
             "first campaign, where staleness read 0.000 everywhere and was "
             "briefly mistaken for a result.\n")

    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="results directories to compare")
    ap.add_argument("--out", default=None,
                    help="write markdown here as well as stdout")
    args = ap.parse_args()

    text = render([Path(d) for d in args.dirs])
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"\n[written to {args.out}]")


if __name__ == "__main__":
    main()
