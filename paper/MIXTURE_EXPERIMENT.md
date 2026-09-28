# The retrieval mixture experiment

The three retrieval weights are constrained to sum to one, so the design space is
a simplex rather than a cube. In experimental design that makes this a **mixture
experiment** (Scheffe, 1958) rather than an ordinary factorial, and it comes with
its own standard design, model and plots. Calling it that in the thesis is more
precise than "sensitivity analysis" and signals that the right tool was used.

Three consequences follow from the constraint, and they are worth stating because
they are the reason the analysis looks the way it does.

You cannot vary one component in isolation. Raising the semantic weight forces
something else down. Any statement of the form "the effect of semantic weight"
must therefore say what gave way, which is what a Cox direction fixes.

The model has no intercept. Since the proportions already sum to one, an
intercept would be perfectly collinear with them. In the Scheffe canonical form
the linear coefficients are the predicted response at each pure corner, which
makes them directly interpretable.

Interactions mean something specific here. A positive cross term says blending
two signals beats interpolating between them, which is the only form in which
"the hybrid formula earns its keep" could be true.

## The design

`configs/sensitivity_*.json` defines a **simplex-lattice design** at step 0.1,
which is 66 points covering the whole space, including the three pure corners and
the published 0.6 / 0.3 / 0.1 blend. Five policies run at every point (P0, P1, P2,
P3, P5), so the design covers every arm of the hypothesis: append-only, time
based, bitemporal, novelty gated and structure blind.

Everything is measured at the retrieval layer, before any answer or judge model
is called, so the whole sweep is free and deterministic. Step 0.05, giving 231
points, is a one-line change if the surfaces need to be smoother.

## Running it

```bash
make sensitivity        # the sweep itself, 66 points x 5 policies, free
make surface            # the mixture analysis, tables and all five figures
make sensitivity-fc     # the same sweep on the second benchmark
make surface-fc
```

## What comes out

`artifacts/sensitivity/<benchmark>_surface_P2.md` contains six sections.

**Invariance check.** Which recorded quantities the weighting cannot move at all.
On MQuAKE-T, active facts (357), pruned (25) and invalidated-active (34) are
identical at all 66 points, because retrieval runs after ingestion and
maintenance. Memory footprint, storage saved and hygiene are decided by the
policy, not the retriever, so three of the six outcomes originally on the list
are out of scope for this parameter by construction.

**Corner responses and model fit.** The Scheffe coefficients with linear and
quadratic R squared. Linear fit is 0.94 for gold support, 0.91 for stale
exposure, 0.80 for tokens, so those are close to straight interpolations between
corners. The exception is `clean`, which rises from 0.46 linear to 0.88
quadratic, meaning the blend genuinely matters for that outcome and not for the
others.

**Measured pure corners.** Semantic and lexical are nearly interchangeable on
MQuAKE-T (both reach gold support 1.000). Recency collapses it to 0.240.

**Pareto frontier.** 27 of 66 weightings are non-dominated on gold support,
stale exposure and token cost together. No weighting wins on all three, which is
why a single best value does not exist independently of what is being optimised.

**Cox effect directions.** One component swept from 0 to 1 while the other two
hold their published ratio. This is the figure that answers "what does changing
each weight actually do", and the six panels show it for every outcome at once.

**Hypothesis stability.** The margin favouring P2 over each competing policy at
every one of the 66 weightings, with reversals counted.

## What it has established so far, on MQuAKE-T

The hypothesis does not depend on the weighting. P2 beats P5 on clean retrieval
at 66 of 66 weightings with zero reversals, and the margin never drops below
0.052. P2 and P0 tie exactly on gold support at every single point, 0.000 at all
66, which is a stronger statement of the equivalence claim than the single
published comparison gives.

Recency's apparent hygiene advantage is an artifact. Pure recency scores 0.010 on
stale exposure, which looks ideal until gold support is seen at 0.240. It is not
filtering stale facts, it is failing to retrieve anything relevant, and a
superseded fact that was never retrieved cannot be served. The ternary plots for
gold support and stale exposure have nearly identical gradients: staleness falls
exactly where answerability falls. Hygiene cannot be bought from the retriever,
which is the thesis argument demonstrated one layer further down than before.

Token cost moves in the opposite direction to intuition. More semantic or lexical
weight means fewer tokens, 343 against recency's 423, because those retrievers
surface the superseded facts that P2 then filters, shrinking the context from 25
facts to about 20. The saving requires the retriever to find the stale material
so the policy can remove it, and the effect exists only for P2, since P0 and P5
have no retrieval-time filter.

`clean` has an interior optimum near 0.2 to 0.3 recency, visible as curvature in
the Cox panel, which is higher than the published 0.1. That is the one place the
surface suggests the published blend is not at the peak, and it is worth naming
rather than hiding.

## Both benchmarks have now run

See `paper/SENSITIVITY_RESULTS.md` for the full cross-benchmark analysis. The
short version: the hypothesis is invariant across the entire usable region on
both benchmarks with zero reversals, the novelty-gate and accuracy-ceiling
findings replicate, and the grace-period invariance claim holds exactly on
MQuAKE-T but only approximately on FactConsolidation, for a reason traced to the
string-match proxy rather than to the policy.

## What is still missing

Everything here is retrieval-layer evidence, so the end-to-end confirmation
through `make weights-search` remains the step that turns these into accuracy
claims. A step-0.05 lattice would resolve the `clean` optimum more precisely if
that becomes a point of discussion.
