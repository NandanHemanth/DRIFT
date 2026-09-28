# Answering the defense feedback: sensitivity, scale, and statistics

Five questions came out of the defense. Four of them are answerable with
experiments that already run from this repository, and the fifth is a
definitional point to have ready in the room.

| Question from the committee | What answers it | Cost |
|---|---|---|
| Why 0.6 / 0.3 / 0.1 for hybrid retrieval? | `make sensitivity` | free |
| Why grace_days = 7, not 6 or 8? | `make sensitivity` | free |
| Why k = 25? Why ttl = 20, tau = 0.9? | `make sensitivity` | free |
| Would frontier models change the result? | `make frontier`, `make judge-upgrade` | paid, small |
| What is a p-value and why does it matter? | Section 6 below | none |

## 1. The argument to make, and the one to avoid

Do not try to show that 0.6 / 0.3 / 0.1 is optimal. Searching for the best
weighting on the same questions used to report results is tuning on the
evaluation set, which is worse methodology than not tuning at all, and a
committee will say so.

The defensible claim has two parts, and the second is what the sweeps supply.

1. Every one of these constants is identical in every cell. The same weighting,
   depth, and thresholds are given to NOMEM, P0, P1, P2, P3, P4 and P5 on both
   benchmarks. A constant applied equally to all conditions cannot explain a
   difference between conditions, and every research question in this thesis is
   about a difference between conditions.
2. The conclusions do not depend on the specific values. Across the whole
   weighting simplex, across retrieval depths from 5 to 50, and across the full
   range of each policy hyperparameter, the ordering of the policies is
   unchanged.

Claim 1 is about internal validity and is already true by construction. Claim 2
is what `src/analysis/sensitivity.py` measures.

## 2. What the sweeps measure, and why not accuracy

Running the full pipeline at every setting would mean an answer call and a judge
call per question per setting: thousands of paid calls, and it would fold judge
noise into a measurement about retrieval. The harness instead measures the
retrieval step directly, before any model is called:

- `gold_support`: the gold answer appears in some retrieved fact, so the answer
  model *could* answer correctly. This is retrieval's actual job.
- `stale_exposure`: the superseded answer appears in some retrieved fact, so the
  answer model *could* answer from a stale value.
- `clean`: gold supported and stale not exposed. The unambiguous case.
- `wasted_slots`: facts that consumed one of the k slots and were then dropped by
  `policy.on_retrieve`.
- `ctx_facts`: facts actually handed to the answer model.

These are deterministic, free, and judge-independent. `make sensitivity-validate`
then checks the proxy against reality by cross-tabulating `gold_support` against
the judge's verdict on the cells that were really run. Report the phi coefficient
from that table when you introduce the proxy, so the sweeps rest on a measured
relationship rather than an assumed one.

## 3. Run order

Free, no keys, proves the machinery works:

```bash
make test               # 106 offline tests, including 7 new sensitivity tests
make sensitivity-smoke  # all five sweeps on synthetic data
```

Free but needs Ollama running for `nomic-embed-text`, and reuses the extraction
cache from the campaigns already run:

```bash
make sensitivity        # MQuAKE-T: weights, k, grace, ttl, tau
make sensitivity-fc     # FactConsolidation: same five sweeps
make sensitivity-validate
```

Paid, small, and the highest-value external-validity evidence:

```bash
make frontier       # NOMEM, P0, P2, P5 on MQuAKE-T with openai/gpt-5.1
make judge-upgrade  # regrade the full matrix with claude-opus-4.8
```

`make judge-upgrade` is the cheapest of the paid runs because answers are already
in `.drift_cache` and are reused byte for byte. Only the judge calls are new, so
it isolates judge quality with the answers held fixed. Alternative frontier
answer models, all confirmed live on OpenRouter: `openai/gpt-5.1`,
`anthropic/claude-opus-4.8`, `anthropic/claude-sonnet-5`,
`google/gemini-3.1-pro-preview`.

Everything writes to `artifacts/sensitivity/` and `artifacts/results/*_frontier*`,
so no published number is touched.

## 4. What each result licenses you to write

### Retrieval weights

The harness reports the ordering at the published weighting and the percentage of
the simplex where that ordering holds. The paragraph to write:

> The hybrid weighting of 0.6 semantic, 0.3 lexical, and 0.1 recency was fixed
> before any results were collected and applied identically to every policy in
> every cell, so it cannot account for any difference between policies. To
> establish that the conclusions are not an artifact of the specific values, the
> weighting was swept across the full simplex in steps of 0.1, a total of 66
> settings. The ordering of P2, P0 and P5 observed at the published weighting is
> preserved in N of 66 settings, and the P2 over P5 ordering specifically is
> preserved in M of 66. The weighting therefore determines the absolute level of
> retrieval quality but not the ranking on which every claim in this thesis rests.

### P2 grace period

The mechanism here is already pinned by a test, and it is a stronger answer than
a sweep alone. `on_retrieve` excludes every invalidated fact regardless of its
age, so the grace period cannot decide whether a stale fact reaches the answer
model. It only decides how long an invalidated fact keeps occupying one of the k
retrieval slots before being pruned. On the synthetic check, `clean` is identical
at 0, 7 and 30 days while `wasted_slots` rises from 0.000 to 1.214 and context
size falls from 8.0 to 6.8 facts.

> The grace period governs when an already-invalidated fact is physically pruned.
> Because the retrieval hook excludes invalidated facts regardless of age, the
> grace period cannot affect whether a superseded value reaches the answer model;
> it affects only how many retrieval slots superseded facts continue to occupy,
> and therefore the token cost. A sweep over 0, 1, 3, 7, 14 and 30 days confirms
> this: the clean-retrieval rate is invariant while wasted slots and context size
> vary monotonically. The value of 7 days is therefore a cost parameter rather
> than a correctness parameter, which is why it was not tuned.

### Retrieval depth, ttl, and tau

Same shape of argument. For k, expect `gold_support` to rise and then flatten
while `est_ctx_tokens` keeps climbing, which justifies 25 as the point past which
depth buys context cost rather than answerable questions. For P1's ttl and P3's
tau, the sweep shows how much of each policy's poor showing is intrinsic to the
mechanism and how much is the specific parameter, which directly answers the
"maybe you just tuned P1 badly" objection.

## 5. Frontier models: state it as a prediction

Write the prediction down before running it, so the run tests a claim rather than
producing a number.

- The NOMEM floor rises on MQuAKE-T, because a frontier model knows many real
  office-holders parametrically, and stays at zero on FactConsolidation, whose
  gold answers are counterfactual by construction. This asymmetry is a property
  of the benchmarks, not the models.
- The P0 ceiling rises toward 1.0, compressing the room available for any policy
  to differ. This is the genuine risk to the results: a stronger answer model is
  better at picking the current value out of a context that also contains the
  stale one, which is exactly the mechanism keeping P0's staleness low already.
- `retrieved_invalidated` does not move at all. P0 surfaces 4.2 to 4.8 superseded
  facts per retrieval and P2 surfaces exactly 0.00 by construction, measured
  before the answer model is called. No model can change this number.
- The 12 percent token saving does not move either, and is worth more at frontier
  prices.

If the P2 over P5 gap survives at frontier scale, external validity is
substantially strengthened. If it shrinks, the honest finding is that bitemporal
invalidation matters most when the answer model is weakest, which is a useful and
publishable result in its own right, and it is still the right default because
the guarantee does not depend on the model being careful.

## 6. The p-value, for the room

A p-value is the probability of seeing evidence at least this extreme if the null
hypothesis were true. The null here is always "these two policies are equivalent".

The tests in this thesis are paired because every policy answers the identical
question set, so outcomes are correlated and an unpaired test would overstate
significance. McNemar's test discards every question where the two policies agree
and looks only at the discordant pairs. For P2 against P5 on accuracy there are
36 discordant questions, 34 favouring P2 and 2 favouring P5. Under the null each
discordant pair is a coin flip, so the exact two-sided p-value is

```
p = 2 * [C(36,0) + C(36,1) + C(36,2)] / 2^36 = 2 * 667 / 68,719,476,736 = 1.9e-8
```

which is why the tables report `< 0.001`. The staleness comparison, 3 against 37,
gives essentially the same value.

What it does not tell you is whether the difference is large enough to matter.
That is the job of the paired bootstrap intervals, and of the judge-reliability
audit, which sets a floor of roughly 3 points below which no difference in this
thesis is interpreted regardless of its p-value. The P2 against P4 comparison sits
below that floor at +0.016 with p = 0.549 and is correctly declared uninterpretable.

## 7. P2 is not a KV cache

A KV cache stores key and value tensors for tokens already processed so attention
is not recomputed. It lives inside one model's inference for one context window,
it is ephemeral, and it is semantically blind: it has no concept of a fact, cannot
distinguish a current fact from a superseded one, and evicting an entry changes
compute cost rather than truth. Prompt caching is the same category of thing, an
optimisation for latency and price.

P2 operates above the model on symbolic subject-predicate-object facts carrying
validity windows, persists across sessions and across model swaps, and its
decisions are semantic: this fact was contradicted by that later fact, so exclude
it. A KV cache has no way to express "no longer true", which is the only thing P2
exists to express.

## 8. Where the results go in the thesis

- Sensitivity tables: a new appendix section, referenced from Chapter 4 where the
  constants are first stated and from the threats list in Chapter 6.
- Proxy validation table: same appendix, immediately before the sweeps, since it
  is what licenses the intrinsic metric.
- Frontier cells: Chapter 5 as a subsection of external validity, and threat 8 in
  Chapter 6 gets rewritten from a limitation into a tested boundary.
- Judge upgrade: Section 5.8, extending the existing judge-reliability audit.
