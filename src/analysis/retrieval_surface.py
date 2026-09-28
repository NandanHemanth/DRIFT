"""Retrieval response surface: what the hybrid weighting can and cannot change.

The weights (semantic, lexical, recency) are constrained to sum to one, so the
design space is a simplex rather than a cube. That makes this a *mixture
experiment* in the sense of Scheffe (1958), and the right analysis is the
canonical mixture model rather than ordinary regression with an intercept:

    linear     y = b1*x1 + b2*x2 + b3*x3
    quadratic  y = sum bi*xi + sum bij*xi*xj

There is no intercept term because the three proportions already sum to one, so
an intercept would be perfectly collinear with them. A useful property of this
parameterisation is that the linear coefficients are exactly the predicted
response at each pure corner: b1 is the response at 100 percent semantic, and so
on. The quadratic cross terms measure whether mixing two signals does better or
worse than interpolating between them, which is where "blending helps" would
show up if it were true.

This module is deliberately not an optimiser. It answers three questions:

  1. Which outcomes can the weighting affect at all, and which are structurally
     invariant to it? (Anything decided before retrieval runs cannot move.)
  2. How does each signal drive each outcome, read off the corner responses?
  3. Which weightings are Pareto optimal across the outcomes that matter, so the
     trade-off can be described rather than collapsed into one winner?

Usage:
    python -m analysis.retrieval_surface artifacts/sensitivity/mquake_t_sensitivity.json
    python -m analysis.retrieval_surface <json> --policy P2 --figures
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# Objectives: outcomes with an unambiguous better direction, so a policy
# comparison on them is meaningful.
OBJECTIVES = {
    "gold_support": "max",
    "stale_exposure": "min",
    "clean": "max",
    "est_ctx_tokens": "min",
}

# Diagnostics: these describe the mechanism rather than score it, and they have
# no "better" direction across policies. P2 necessarily has wasted slots because
# it is the only policy that filters at retrieval, and P0 necessarily has none.
# Comparing policies on them would read as P2 losing when it is simply the only
# one doing the work. Reported for P2, excluded from hypothesis comparisons.
DIAGNOSTICS = ("wasted_slots", "ctx_facts")

OUTCOMES = {**OBJECTIVES, "wasted_slots": "min", "ctx_facts": "max"}

# Recorded per run but fixed before retrieval happens, so the weighting cannot
# touch them. Reported as an invariance check rather than as a result.
PRE_RETRIEVAL = ("active_facts", "pruned", "invalidated_active")

PARETO_AXES = (("gold_support", "max"), ("stale_exposure", "min"), ("est_ctx_tokens", "min"))


def _solve(A: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting. Stdlib only, like the rest of
    the analysis package."""
    n = len(A)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(n + 1)]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def fit_mixture(points: list[tuple[float, float, float]], y: list[float],
                quadratic: bool = False) -> dict:
    """Fit the Scheffe canonical mixture model and report R squared."""
    def design(w):
        x1, x2, x3 = w
        row = [x1, x2, x3]
        if quadratic:
            row += [x1 * x2, x1 * x3, x2 * x3]
        return row

    X = [design(w) for w in points]
    n = len(X[0])
    A = [[sum(X[r][i] * X[r][j] for r in range(len(X))) for j in range(n)] for i in range(n)]
    rhs = [sum(X[r][i] * y[r] for r in range(len(X))) for i in range(n)]
    coef = _solve(A, rhs)
    pred = [sum(coef[i] * X[r][i] for i in range(n)) for r in range(len(X))]
    ybar = sum(y) / len(y)
    ss_res = sum((y[r] - pred[r]) ** 2 for r in range(len(y)))
    ss_tot = sum((v - ybar) ** 2 for v in y)
    names = ["semantic", "lexical", "recency"]
    if quadratic:
        names += ["sem x lex", "sem x rec", "lex x rec"]
    return {
        "coefficients": dict(zip(names, coef)),
        "r2": 1 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "rmse": math.sqrt(ss_res / len(y)),
    }


def invariance_check(rows: list[dict]) -> dict:
    """Confirm which recorded quantities the weighting cannot move."""
    out = {}
    for key in PRE_RETRIEVAL:
        vals = {r[key] for r in rows if key in r}
        out[key] = {"invariant": len(vals) <= 1, "values": sorted(vals)}
    return out


def pareto_front(rows: list[dict], axes=PARETO_AXES) -> list[dict]:
    """Non-dominated weightings. A point is dominated if another is at least as
    good on every axis and strictly better on one."""
    def better_eq(a, b, key, sense):
        return a[key] >= b[key] if sense == "max" else a[key] <= b[key]

    def strictly(a, b, key, sense):
        return a[key] > b[key] if sense == "max" else a[key] < b[key]

    front = []
    for a in rows:
        dominated = any(
            all(better_eq(b, a, k, s) for k, s in axes)
            and any(strictly(b, a, k, s) for k, s in axes)
            for b in rows if b is not a
        )
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda r: -r["gold_support"])


def corner_rows(rows: list[dict]) -> dict:
    """The three measured pure-signal rows, if present in the grid."""
    want = {"semantic": (1.0, 0.0, 0.0), "lexical": (0.0, 1.0, 0.0), "recency": (0.0, 0.0, 1.0)}
    out = {}
    for name, w in want.items():
        hit = [r for r in rows if (r["w_sem"], r["w_lex"], r["w_rec"]) == w]
        if hit:
            out[name] = hit[0]
    return out


def cox_direction(reference: tuple[float, float, float], component: int,
                  n: int = 21) -> list[tuple[float, tuple[float, float, float]]]:
    """Cox effect direction: vary one component across its full range while the
    other two keep their relative proportions from the reference blend.

    This is the standard way to read a single component's effect out of a mixture
    experiment. You cannot simply "increase semantic weight" in isolation, because
    the three proportions must keep summing to one, so something else has to give.
    The Cox direction makes that trade explicit and fixed: whatever is taken from
    or given to the other two is split in their existing ratio.
    """
    out = []
    r_i = reference[component]
    others = [j for j in range(3) if j != component]
    rest = sum(reference[j] for j in others)
    for step in range(n):
        x = step / (n - 1)
        w = [0.0, 0.0, 0.0]
        w[component] = x
        if rest <= 1e-12:
            for j in others:
                w[j] = (1 - x) / 2
        else:
            for j in others:
                w[j] = reference[j] / rest * (1 - x)
        out.append((x, (w[0], w[1], w[2])))
    return out


def predict(fit: dict, w: tuple[float, float, float]) -> float:
    c = fit["coefficients"]
    x1, x2, x3 = w
    y = c["semantic"] * x1 + c["lexical"] * x2 + c["recency"] * x3
    if "sem x lex" in c:
        y += c["sem x lex"] * x1 * x2 + c["sem x rec"] * x1 * x3 + c["lex x rec"] * x2 * x3
    return y


def cox_table(rows: list[dict], reference=(0.6, 0.3, 0.1)) -> list[dict]:
    """Response at each end of each Cox direction, plus the swing between them."""
    pts = [(r["w_sem"], r["w_lex"], r["w_rec"]) for r in rows]
    names = ["semantic", "lexical", "recency"]
    out = []
    for key in OUTCOMES:
        fit = fit_mixture(pts, [r[key] for r in rows], quadratic=True)
        row = {"outcome": key, "at_reference": predict(fit, reference)}
        for i, name in enumerate(names):
            trace = cox_direction(reference, i)
            lo = predict(fit, trace[0][1])
            hi = predict(fit, trace[-1][1])
            row[f"{name}_at_0"] = lo
            row[f"{name}_at_1"] = hi
            row[f"{name}_swing"] = hi - lo
        out.append(row)
    return out


def hypothesis_stability(all_rows: list[dict], reference_policy: str = "P2") -> list[dict]:
    """Does the hypothesis survive every weighting on the simplex?

    For each competing policy and each outcome, report the margin in favour of
    the reference policy across the whole design space, and count how often the
    ordering reverses. A hypothesis that only holds at the published weighting
    would be an artifact of that weighting; one that holds everywhere is not.
    """
    by_w: dict[tuple, dict[str, dict]] = {}
    for r in all_rows:
        by_w.setdefault((r["w_sem"], r["w_lex"], r["w_rec"]), {})[r["policy"]] = r
    others = sorted({r["policy"] for r in all_rows} - {reference_policy})
    out = []
    for key, sense in OBJECTIVES.items():
        sign = 1 if sense == "max" else -1
        for opp in others:
            margins = []
            for w, d in by_w.items():
                if reference_policy in d and opp in d:
                    margins.append(sign * (d[reference_policy][key] - d[opp][key]))
            if not margins:
                continue
            out.append({
                "outcome": key,
                "comparison": f"{reference_policy} vs {opp}",
                "settings": len(margins),
                "min": min(margins),
                "mean": sum(margins) / len(margins),
                "max": max(margins),
                "holds": sum(1 for m in margins if m > 1e-9),
                "ties": sum(1 for m in margins if abs(m) <= 1e-9),
                "reversed": sum(1 for m in margins if m < -1e-9),
            })
    return out


def cox_figure(rows: list[dict], path: Path, reference=(0.6, 0.3, 0.1)) -> None:
    """One panel per outcome, one line per component, over that component's range."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pts = [(r["w_sem"], r["w_lex"], r["w_rec"]) for r in rows]
    keys = list(OUTCOMES)
    colours = {"semantic": "#0f766e", "lexical": "#b45309", "recency": "#6d28d9"}
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.4), dpi=200)
    for ax, key in zip(axes.ravel(), keys):
        fit = fit_mixture(pts, [r[key] for r in rows], quadratic=True)
        for i, name in enumerate(("semantic", "lexical", "recency")):
            trace = cox_direction(reference, i)
            xs = [t[0] for t in trace]
            ys = [predict(fit, t[1]) for t in trace]
            ax.plot(xs, ys, label=name, color=colours[name], lw=1.8)
        ax.axvline(reference[0], color="#9ca3af", ls=":", lw=0.9)
        ax.set_title(key.replace("_", " "), fontsize=9.5)
        ax.set_xlabel("component weight", fontsize=8)
        ax.tick_params(labelsize=7.5)
        ax.grid(alpha=0.25, lw=0.5)
    axes.ravel()[0].legend(fontsize=8, frameon=False)
    fig.suptitle("Cox effect directions: one component varied, the other two held in proportion",
                 fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)


def hypothesis_figure(all_rows: list[dict], path: Path, outcome: str = "clean",
                      reference_policy: str = "P2") -> None:
    """Margin in favour of the reference policy at every weighting, sorted."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_w: dict[tuple, dict[str, dict]] = {}
    for r in all_rows:
        by_w.setdefault((r["w_sem"], r["w_lex"], r["w_rec"]), {})[r["policy"]] = r
    others = sorted({r["policy"] for r in all_rows} - {reference_policy})
    sense = OBJECTIVES[outcome]
    sign = 1 if sense == "max" else -1

    fig, ax = plt.subplots(figsize=(7.4, 4.0), dpi=200)
    palette = ["#0f766e", "#b45309", "#6d28d9", "#be123c"]
    for colour, opp in zip(palette, others):
        margins = sorted(sign * (d[reference_policy][outcome] - d[opp][outcome])
                         for d in by_w.values() if reference_policy in d and opp in d)
        ax.plot(range(1, len(margins) + 1), margins, lw=1.8, color=colour,
                label=f"{reference_policy} minus {opp}")
    ax.axhline(0, color="#c1121f", lw=1.2)
    ax.set_xlabel("weightings on the simplex, sorted by margin", fontsize=9)
    ax.set_ylabel(f"margin favouring {reference_policy} ({outcome.replace('_', ' ')})", fontsize=9)
    ax.set_title("Hypothesis margin across the whole design space", fontsize=10.5)
    ax.legend(fontsize=8.5, frameon=False)
    ax.grid(alpha=0.25, lw=0.5)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def ternary_figure(rows: list[dict], outcome: str, path: Path, title: str) -> None:
    """Barycentric scatter of one outcome over the weight simplex."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs, ys, vals = [], [], []
    for r in rows:
        a, b, c = r["w_sem"], r["w_lex"], r["w_rec"]
        xs.append(b + c / 2.0)
        ys.append(c * math.sqrt(3) / 2.0)
        vals.append(r[outcome])

    fig, ax = plt.subplots(figsize=(5.2, 4.6), dpi=200)
    tri = [(0, 0), (1, 0), (0.5, math.sqrt(3) / 2), (0, 0)]
    ax.plot([p[0] for p in tri], [p[1] for p in tri], color="#333333", lw=1.0)
    sc = ax.scatter(xs, ys, c=vals, s=120, cmap="viridis", edgecolors="white", linewidths=0.4)
    pub = [r for r in rows if (r["w_sem"], r["w_lex"], r["w_rec"]) == (0.6, 0.3, 0.1)]
    if pub:
        px = pub[0]["w_lex"] + pub[0]["w_rec"] / 2.0
        py = pub[0]["w_rec"] * math.sqrt(3) / 2.0
        ax.scatter([px], [py], s=230, facecolors="none", edgecolors="#c1121f", linewidths=2.0)
        ax.annotate("published\n0.6 / 0.3 / 0.1", (px, py), textcoords="offset points",
                    xytext=(10, -22), fontsize=7.5, color="#c1121f")
    ax.text(-0.04, -0.05, "semantic", ha="center", fontsize=9)
    ax.text(1.04, -0.05, "lexical", ha="center", fontsize=9)
    ax.text(0.5, math.sqrt(3) / 2 + 0.04, "recency", ha="center", fontsize=9)
    fig.colorbar(sc, ax=ax, shrink=0.8, label=outcome.replace("_", " "))
    ax.set_title(title, fontsize=10)
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def report(rows: list[dict], policy: str) -> str:
    pts = [(r["w_sem"], r["w_lex"], r["w_rec"]) for r in rows]
    lines = [f"# Retrieval response surface: {policy}", "",
             f"{len(rows)} weightings on the simplex, step 0.1. The weights are constrained to",
             "sum to one, so this is a mixture experiment and the model below is the Scheffe",
             "canonical form. Linear coefficients are the predicted response at each pure corner.",
             ""]

    inv = invariance_check(rows)
    lines += ["## 1. What the weighting cannot change", "",
              "| quantity | invariant | value |", "|---|---|---|"]
    for k, v in inv.items():
        lines.append(f"| {k} | {'yes' if v['invariant'] else 'NO'} | "
                     f"{v['values'][0] if len(v['values']) == 1 else v['values']} |")
    lines += ["", "These are fixed during ingestion and maintenance, before retrieval runs, so no",
              "weighting can move them. Memory footprint, storage saved and hygiene are therefore",
              "out of scope for this parameter by construction.", ""]

    lines += ["## 2. Corner responses and model fit", "",
              "| outcome | pure semantic | pure lexical | pure recency | linear R2 | quadratic R2 |",
              "|---|---|---|---|---|---|"]
    for key in OUTCOMES:
        y = [r[key] for r in rows]
        lin = fit_mixture(pts, y)
        quad = fit_mixture(pts, y, quadratic=True)
        c = lin["coefficients"]
        lines.append(f"| {key} | {c['semantic']:.3f} | {c['lexical']:.3f} | {c['recency']:.3f} "
                     f"| {lin['r2']:.3f} | {quad['r2']:.3f} |")
    lines += ["", "A linear R2 near 1 means the outcome is close to a straight interpolation",
              "between the corners, so mixing buys nothing that the corners do not already",
              "explain. A large jump from linear to quadratic means the blend itself matters.", ""]

    corners = corner_rows(rows)
    if corners:
        lines += ["## 3. Measured pure corners", "",
                  "| corner | gold support | stale exposure | clean | wasted slots | est tokens |",
                  "|---|---|---|---|---|---|"]
        for name, r in corners.items():
            lines.append(f"| {name} | {r['gold_support']:.3f} | {r['stale_exposure']:.3f} | "
                         f"{r['clean']:.3f} | {r['wasted_slots']:.2f} | {r['est_ctx_tokens']:.0f} |")
        pub = [r for r in rows if (r["w_sem"], r["w_lex"], r["w_rec"]) == (0.6, 0.3, 0.1)]
        if pub:
            r = pub[0]
            lines.append(f"| published 0.6/0.3/0.1 | {r['gold_support']:.3f} | "
                         f"{r['stale_exposure']:.3f} | {r['clean']:.3f} | "
                         f"{r['wasted_slots']:.2f} | {r['est_ctx_tokens']:.0f} |")
        lines.append("")

    front = pareto_front(rows)
    lines += [f"## 4. Pareto frontier ({len(front)} of {len(rows)} weightings)", "",
              "Non-dominated on gold support up, stale exposure down, tokens down. No single",
              "weighting wins on all three, which is why a single best value does not exist",
              "independently of which outcome is being prioritised.", "",
              "| sem | lex | rec | gold | stale | tokens |", "|---|---|---|---|---|---|"]
    for r in front:
        lines.append(f"| {r['w_sem']:.1f} | {r['w_lex']:.1f} | {r['w_rec']:.1f} | "
                     f"{r['gold_support']:.3f} | {r['stale_exposure']:.3f} | "
                     f"{r['est_ctx_tokens']:.0f} |")
    lines.append("")

    lines += ["## 5. Cox effect directions", "",
              "Each component varied from 0 to 1 while the other two keep their relative",
              "proportions from the published blend. This is how a single component's effect",
              "is read out of a mixture experiment, since the proportions must always sum to",
              "one and something has to give.", "",
              "| outcome | at published | semantic 0 to 1 | lexical 0 to 1 | recency 0 to 1 |",
              "|---|---|---|---|---|"]
    for row in cox_table(rows):
        lines.append(f"| {row['outcome']} | {row['at_reference']:.3f} | "
                     f"{row['semantic_at_0']:.3f} to {row['semantic_at_1']:.3f} "
                     f"({row['semantic_swing']:+.3f}) | "
                     f"{row['lexical_at_0']:.3f} to {row['lexical_at_1']:.3f} "
                     f"({row['lexical_swing']:+.3f}) | "
                     f"{row['recency_at_0']:.3f} to {row['recency_at_1']:.3f} "
                     f"({row['recency_swing']:+.3f}) |")
    lines.append("")

    ceiling = [r for r in rows if r["gold_support"] >= 0.999]
    if ceiling:
        lines += [f"## 5. Best choice per objective, among the {len(ceiling)} at the accuracy ceiling",
                  "", "| objective | weighting | gold | stale | tokens | clean |",
                  "|---|---|---|---|---|---|"]
        for label, key, sense in (("fewest tokens", "est_ctx_tokens", "min"),
                                  ("lowest stale exposure", "stale_exposure", "min"),
                                  ("highest clean", "clean", "max")):
            best = sorted(ceiling, key=lambda r: (-r[key] if sense == "max" else r[key]))[0]
            lines.append(f"| {label} | {best['w_sem']:.1f} / {best['w_lex']:.1f} / "
                         f"{best['w_rec']:.1f} | {best['gold_support']:.3f} | "
                         f"{best['stale_exposure']:.3f} | {best['est_ctx_tokens']:.0f} | "
                         f"{best['clean']:.3f} |")
        lines.append("")
    return "\n".join(lines)


def hypothesis_section(all_rows: list[dict], reference_policy: str = "P2") -> str:
    stab = hypothesis_stability(all_rows, reference_policy)
    if not stab:
        return ""
    lines = ["## 6. Does the hypothesis depend on the weighting?", "",
             "Margin in favour of " + reference_policy + " at every weighting on the simplex.",
             "A claim that only holds at the published blend would be an artifact of that",
             "blend. One that holds everywhere is not.", "",
             "Objectives only. Wasted slots and context size are mechanism diagnostics with",
             "no better direction across policies, so they are excluded here.", "",
             "| outcome | comparison | min | mean | max | holds | ties | reversed |",
             "|---|---|---|---|---|---|---|---|"]
    for r in stab:
        lines.append(f"| {r['outcome']} | {r['comparison']} | {r['min']:.3f} | {r['mean']:.3f} "
                     f"| {r['max']:.3f} | {r['holds']}/{r['settings']} | {r['ties']} "
                     f"| {r['reversed']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Retrieval weight response surface")
    ap.add_argument("sweep", help="the *_sensitivity.json written by analysis.sensitivity")
    ap.add_argument("--policy", default="P2")
    ap.add_argument("--out", help="output directory (default beside the sweep)")
    ap.add_argument("--figures", action="store_true", help="also write ternary plots")
    args = ap.parse_args()

    sweep = Path(args.sweep)
    if not sweep.exists():
        # The usual cause is running this in a second terminal while the sweep
        # is still going. The sweep writes its JSON once, at the end, so the
        # file is absent for the whole run rather than growing.
        stem = sweep.stem.replace("_sensitivity", "")
        target = {"mquake_t": "sensitivity",
                  "factconsolidation": "sensitivity-fc",
                  "smoke": "sensitivity-smoke"}.get(stem, f"sensitivity-{stem}")
        raise SystemExit(
            f"{sweep} does not exist yet.\n"
            f"This file is written only when the sweep finishes, so it is missing\n"
            f"both before the sweep starts and all the way through it.\n"
            f"Let 'make {target}' complete, then rerun this."
        )

    data = json.loads(sweep.read_text())
    key = next((k for k in data if k == "weights"), None)
    if key is None:
        raise SystemExit("no 'weights' sweep in that file; run make sensitivity first")
    all_rows = data[key]
    rows = [r for r in all_rows if r["policy"] == args.policy]
    if not rows:
        raise SystemExit(f"no rows for policy {args.policy}")

    out_dir = Path(args.out or Path(args.sweep).parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.sweep).stem.replace("_sensitivity", "")
    text = report(rows, args.policy) + "\n" + hypothesis_section(all_rows, args.policy)
    md = out_dir / f"{stem}_surface_{args.policy}.md"
    md.write_text(text)
    print(text)
    print(f"\nWrote {md}")

    if args.figures:
        for outcome in ("gold_support", "stale_exposure", "clean", "est_ctx_tokens"):
            path = out_dir / f"{stem}_surface_{args.policy}_{outcome}.png"
            ternary_figure(rows, outcome, path,
                           f"{outcome.replace('_', ' ')} over the weight simplex ({args.policy})")
            print(f"Wrote {path}")
        cox_path = out_dir / f"{stem}_cox_{args.policy}.png"
        cox_figure(rows, cox_path)
        print(f"Wrote {cox_path}")
        if len({r["policy"] for r in all_rows}) > 1:
            hyp_path = out_dir / f"{stem}_hypothesis_{args.policy}.png"
            hypothesis_figure(all_rows, hyp_path)
            print(f"Wrote {hyp_path}")


if __name__ == "__main__":
    main()
