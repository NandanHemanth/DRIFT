# September campaign: what ran, what it showed, what it changes

Analysis of every result directory produced up to 24 September 2026. Every number
below was recomputed from the per-question records in `artifacts/results/`, not
copied from summary tables. Paired tests are exact two-sided McNemar on the same
questions; "pooled" means both answer models (GLM-5.2 and MiniMax-M3) together.

Figures: `paper/figures_sept24/`.

## 0. The one-paragraph version

The published FactConsolidation matrix was answered under the old answer prompt,
the one that told every policy to "prefer the most recent fact" and marked
superseded facts. That gave P0 the P2 mechanism for free and produced the P0 = P2
tie on that benchmark. Rerun under the current prompt, P2 beats P0 on
FactConsolidation: staleness 0.18 to 0.06 (p = 0.004, judge-free) and accuracy
0.70 to 0.80. This makes the thesis stronger, not weaker, but the FactConsolidation
numbers in Chapter 5 and the cross-dataset Spearman must be regenerated. Separately,
the tuning protocol worked as designed: no retrieval weighting beats 0.6/0.3/0.1 on
the tuning set, and the pre-registered falsification arm (0.3/0.4/0.3) lost on the
held-out set exactly as gold-support predicted. The grace period has no
correctness effect on either benchmark and trades storage against prompt tokens.
ConvoMem, the third benchmark, replicates P2's staleness reduction in natural
dialogue (p = 0.008) but exposes a hard boundary: contradiction detection only
works when the extractor produces aligned subject and predicate keys.

## 1. Inventory

| Directory | Cells | Status | Trust |
|---|---|---|---|
| `mquake_t` | 14 / 14 | published, Aug 6 | clean |
| `factconsolidation` | 14 / 14 | published, Aug 5 | **contaminated, see section 2** |
| `convomem` | 14 / 14 | new, Sep 24 | clean |
| `param_weights_factconsolidation` | 14 / 14 | tuning set | clean |
| `param_weights_mquake_t` | 14 / 14 | held-out test | clean |
| `param_grace_factconsolidation` | 10 / 10 | complete | clean |
| `param_grace_mquake_t` | 10 / 10 | complete | clean |
| `param_*_convomem` | 0 | not run | |
| `mquake_t_regraded` | 13 / 14 | P4 GLM missing | P0 to P3 are true regrades; P4 and P5 are not (section 6) |
| `factconsolidation_regraded` | 3 / 14 | interrupted | these are clean reruns, not regrades (section 2) |
| `artifacts/sensitivity/convomem_*` | done | | gold-support column unusable (section 5) |

## 2. Finding 1: the published FactConsolidation matrix used the pre-fix prompt

### How it was found

The P2 cell at 0.6/0.3/0.1 in `param_weights_factconsolidation` is supposed to be
identical to the published P2 cell. On MQuAKE-T it is, answer for answer, 96 of 96.
On FactConsolidation it is not: 62 of 100 answers match for GLM, 38 of 100 for
MiniMax, and the fresh cells are significantly more stale (GLM p = 0.031, MiniMax
p = 0.022).

Memory was identical (all 380 fact texts and timelines match). Retrieval was
identical (the ordered top-k for all 100 questions matches). So the difference had
to be in the prompt.

### Proof

The answer cache is content-addressed by SHA-256 of the exact prompt. For every
record in every published FactConsolidation cell I rebuilt the prompt two ways,
with the current prompt and with the prompt as it stood before commit `187575e`
("Stop the answer prompt from doing the forgetting policy's job"), and looked up
the resulting cache key.

| Matrix | Records whose cached answer is the response to the OLD prompt |
|---|---|
| FactConsolidation P0, P2, P3, P5, both models | 100 / 100 in every cell |
| MQuAKE-T P0, P2, P3, P5, both models | 0 / 96 in every cell |

That is not a statistical inference. Each published FactConsolidation answer is
byte-identical to the response the cache holds for the leaky prompt.

### How it happened

The FactConsolidation run started at about 15:30 on 5 August. The prompt fix was
committed at 16:12, and most cells finished after that, which is why their
timestamps look clean. But a running Python process keeps the module it imported
at startup. Editing `pipeline.py` mid-run changed nothing for that process. The
commit message itself warned that `results/factconsolidation` had to be cleared
and rerun; it was not. Its symptom matches the published data exactly: GLM P0 at
0.86 accuracy with staleness 0.000.

### What the clean data says

Only GLM has a clean P0 cell so far (from the interrupted regrade). Staleness is a
string match, so it is judge-independent and the cleanest comparison available:

| FactConsolidation, GLM-5.2 | Published (leaky) | Clean |
|---|---|---|
| P0 accuracy | 0.86 | 0.70 |
| P2 accuracy | 0.85 | 0.80 |
| P0 staleness | 0.00 | **0.18** |
| P2 staleness | 0.00 | **0.06** |
| P0 token F1 | 0.64 | 0.40 |
| P2 token F1 | 0.61 | 0.53 |

Paired, clean P0 vs clean P2 (GLM):

| Metric | P0 worse only | P2 worse only | p |
|---|---|---|---|
| Staleness (judge-free) | 14 | 2 | **0.004** |
| Accuracy | 13 | 3 | 0.021 |
| Token F1 (judge-free) | 0.402 | 0.529 | |

The accuracy test mixes judges (Opus 4.8 graded P0, the original ensemble graded
P2), so quote the staleness and F1 results as primary. The regrade on MQuAKE-T
(section 7) shows the judge swap moves accuracy by one to two points, far less
than this ten-point gap.

The same P2-over-P0 staleness result holds at all 12 weighting and grace settings
tested (p between 0.0001 and 0.031), so it is not a property of one setting.

### What it changes in the thesis

1. Chapter 5 FactConsolidation numbers and `paper/generalization.md` are invalid
   and must be regenerated. The Spearman rho of 0.891 compares a contaminated
   matrix with a clean one.
2. The headline changes in your favour. The previous story was "P2 matches P0 on
   accuracy while cutting cost". The clean story on FactConsolidation is "P2 beats
   P0 on staleness and accuracy". MQuAKE-T still shows the tie, so the honest
   framing is that P2's advantage depends on how much stale content reaches the
   context, which FactConsolidation (built entirely from supersessions) stresses
   more than MQuAKE-T.
3. This is also a methodological contribution worth one paragraph: an answer
   prompt that tells the model how to resolve conflicts silently implements the
   forgetting policy for every condition. Here it erased an 18-point staleness gap.

## 3. Finding 2: the tuning and test protocol on the retrieval weights

Protocol fixed in advance: tune on FactConsolidation, test on MQuAKE-T. Keep the
published weighting unless a candidate beats it significantly on the tuning set.

### Tuning set: FactConsolidation (pooled, n = 200)

| Weighting (sem/lex/rec) | Accuracy | Staleness | Tok/q | vs published: better/worse | p |
|---|---|---|---|---|---|
| 0.6/0.3/0.1 (published) | 0.785 | 0.100 | 716 | | |
| 1.0/0.0/0.0 | 0.795 | 0.090 | 692 | 4 / 2 | 0.688 |
| 0.4/0.4/0.2 | 0.795 | 0.085 | 737 | 5 / 3 | 0.727 |
| 0.5/0.3/0.2 | 0.780 | 0.085 | 725 | 5 / 6 | 1.000 |
| 0.3/0.4/0.3 | 0.765 | 0.095 | 737 | 5 / 9 | 0.424 |
| RRF (no weights) | 0.750 | 0.100 | 715 | 7 / 14 | 0.189 |
| 0.0/1.0/0.0 | **0.575** | 0.080 | 726 | 2 / 44 | **< 0.001** |

Decision: nothing beats the published blend. The rule says keep 0.6/0.3/0.1.

### Held-out test: MQuAKE-T (pooled, n = 192)

| Weighting | Accuracy | Staleness | Tok/q | vs published | p |
|---|---|---|---|---|---|
| 0.6/0.3/0.1 (published) | 0.969 | 0.036 | 716 | | |
| 1.0/0.0/0.0 | 0.974 | 0.016 | 686 | 2 / 1 | 1.000 |
| 0.4/0.4/0.2 | 0.974 | 0.047 | 750 | 2 / 1 | 1.000 |
| 0.5/0.3/0.2 | 0.969 | 0.036 | 750 | 3 / 3 | 1.000 |
| RRF | 0.979 | 0.031 | 727 | 3 / 1 | 0.625 |
| 0.0/1.0/0.0 | 0.964 | 0.031 | 690 | 2 / 3 | 1.000 |
| 0.3/0.4/0.3 | **0.906** | 0.042 | 746 | 3 / 15 | **0.008** |

### What was learnt

- **The falsification test passed.** 0.3/0.4/0.3 has the best free-sweep "clean"
  score of any weighting, but its gold support on MQuAKE-T is 0.927. The
  gold-support-as-ceiling argument predicted its accuracy would be capped near
  0.93. It scored 0.906 and is the only arm that loses significantly on the test
  set. A cheap retrieval measurement correctly predicted an expensive end-to-end
  failure before any money was spent on it.
- **Accuracy is flat inside the gold-support-preserving region.** Every arm with
  gold support at the ceiling lands within 1.5 points of the published blend on
  both benchmarks. This is the answer to "why 0.6/0.3/0.1": not because it is the
  optimum, but because the conclusion is the same anywhere in that region.
- **Pure lexical fails on the tuning set only, and only for GLM** (GLM 0.40,
  MiniMax 0.75, same contexts). FactConsolidation facts share most of their tokens,
  so lexical scoring produces long ties and a poorly ordered context, and GLM is
  far more sensitive to context order than MiniMax. This is why a benchmark-specific
  tune would be dangerous: the same corner is harmless on MQuAKE-T.
- **The weighted formula does not clearly earn its three parameters over RRF.** RRF
  is 3.5 points behind on FactConsolidation (p = 0.19) and one point ahead on
  MQuAKE-T. The defensible claim is "the conclusions hold under a parameter-free
  fusion too", which is stronger than defending the specific constants.
- **Recency is the component that buys least.** Pure semantic is never worse than
  the published blend, has the lowest staleness on both sets, and uses 3 to 4
  percent fewer tokens. If you ever do change the default, drop recency first. Do
  not change it now: the pre-registered rule says keep it.

## 4. Finding 3: the grace period, end to end

| Grace | FC acc | FC stale | FC tok/q | FC active facts | MQ acc | MQ stale | MQ tok/q | MQ active facts |
|---|---|---|---|---|---|---|---|---|
| 1 day | 0.770 | 0.085 | 738 | 298 | 0.979 | 0.031 | 737 | 340 |
| 3 days | 0.780 | 0.085 | 737 | 303 | 0.979 | 0.036 | 734 | 345 |
| 7 days | 0.785 | 0.100 | 716 | 324 | 0.969 | 0.036 | 716 | 357 |
| 14 days | 0.795 | 0.090 | 701 | 345 | 0.969 | 0.036 | 699 | 370 |
| 21 days | 0.785 | 0.090 | 683 | 364 | 0.964 | 0.036 | 697 | 377 |

Every accuracy and staleness comparison against 7 days has p >= 0.45 on both
benchmarks. The earlier concern that grace moved correctness on FactConsolidation
came from the string-match proxy and does not survive the end-to-end test.

What does move is a clean trade-off (figure `grace_tradeoff.png`):

- Shorter grace stores fewer facts: 1 day keeps 18 percent fewer active facts than
  21 days on FactConsolidation, 10 percent fewer on MQuAKE-T.
- Shorter grace costs more prompt tokens: 1 day uses 8 percent more tokens per
  question on FactConsolidation, 6 percent more on MQuAKE-T.

The mechanism is the one the sweeps predicted. P2 already hides invalidated facts
at retrieval. When they are kept (long grace), they are fetched and then filtered,
so fewer live facts reach the prompt. When they are pruned (short grace), their
slots go to other live facts, so the prompt grows. Grace therefore trades storage
against per-query cost, with no correctness consequence in either direction. That
makes 7 days a defensible midpoint and confirms the deployment argument in
`GRACE_PERIOD_SCENARIOS.md`: the right value is set by how much history the
application must keep, not by accuracy.

## 5. Finding 4: ConvoMem, the third benchmark

### Results (pooled, n = 200)

| Policy | Accuracy | Staleness | Tok/q |
|---|---|---|---|
| NOMEM | 0.000 | 0.000 | 248 |
| P0 | 0.235 | 0.225 | 1026 |
| P1 (ttl 20) | 0.235 | 0.225 | 1026 |
| P2 | 0.225 | **0.165** | **849** |
| P3 | 0.245 | 0.240 | 1032 |
| P4 | 0.230 | 0.200 | 998 |
| P5 | 0.235 | 0.200 | 921 |

| Comparison | Accuracy p | Staleness (more stale only) | Staleness p |
|---|---|---|---|
| P2 vs P0 | 0.774 | P0 15, P2 3 | **0.008** |
| P2 vs P3 | 0.388 | P3 19, P2 4 | **0.003** |
| P2 vs P5 | 0.625 | P5 11, P2 4 | 0.118 |
| P2 vs P4 | 1.000 | P4 12, P2 5 | 0.143 |

### What it shows

- **The staleness mechanism replicates in natural dialogue.** P2 cuts staleness by
  27 percent relative to P0 (p = 0.008) and uses 17 percent fewer tokens. P2's
  staleness advantage over P3 is now significant on MQuAKE-T and ConvoMem;
  FactConsolidation needs the clean rerun before it can be counted.
- **Accuracy is floored at about 0.23 for every policy, for a reason unrelated to
  forgetting.** P0 answers "I don't know" on 58 to 60 percent of questions. The
  bottleneck is recall: extraction keeps about 77 facts from roughly 610 lines per
  conversation, and many question-relevant values never become facts.
- **P1 is a no-op on ConvoMem.** Its twenty sessions span 19 days, so a 20-day TTL
  never fires. P1 and P0 are identical cell for cell. Report it as such, not as a
  tie.

### The boundary condition it exposes

I audited all 17 invalidations in the final conversation. Roughly two are real
supersessions (the dentist appointment moving from Tuesday to Friday is one). The
rest are false: `has_meeting`, `deliverable`, `manages_account` and
`set_reminder` are multi-valued, but `functional_predicates = "*"` treats every
predicate as single-valued, so each new meeting "supersedes" the previous one.
Meanwhile the real changes in the questions were mostly missed, because the
extractor wrote the old and new values under different keys:

    technical training session | scheduled_for | Monday
    apex_digital_training_session | rescheduled_to | wednesday_of_same_week

Different subject, different predicate, so no contradiction is ever detected.

This is the most important limitation the thesis can now state with evidence:
**P2's benefit is bounded by contradiction-detection quality, which is bounded by
key canonicalization.** MQuAKE-T and FactConsolidation are templated, so aligned
keys come for free. Natural dialogue does not supply them. That P2 still reduces
staleness here, with low precision, is encouraging; the size of the effect is
what canonicalization would have to improve.

### ConvoMem sensitivity sweep

The ordering and token results are usable: P2 has lower stale exposure than P0 at
63 of 66 weightings and lower context tokens at 66 of 66. The gold-support column
(0.05 everywhere) is not usable. ConvoMem's gold answers are full sentences ("The
call is scheduled for 10 AM."), and the proxy checks whether that whole sentence
appears inside a fact, which it essentially never does. The stale needles are
short values ("3 PM"), so stale exposure works. Fixing this needs the converter to
store the short current value alongside the sentence.

## 6. Finding 5: LLM-based maintenance is fragile; P2 is not

This was not a planned experiment, but it is informative. The NVIDIA route that
served the original extraction and consolidation calls is gone. During the
MQuAKE-T regrade, cached calls were replayed, but some of P4's consolidation calls
were cache misses and fell through to a different model.

| MQuAKE-T, MiniMax-M3 | Published | Rerun with fallback consolidator |
|---|---|---|
| P4 facts pruned | 8 | **172** |
| P4 active facts | 374 | 208 |
| P4 accuracy | 0.948 | **0.573** |
| P5 facts differing | | 4 |
| P5 questions with changed retrieval | | 73 / 96 |

Swapping the model that runs consolidation turned P4 from near-best to the worst
memory-bearing policy. P2 and P0 reproduced exactly, answer for answer, because
their maintenance uses no model at all. This supports a reliability argument for
deterministic invalidation that the thesis does not currently make. Treat it as an
observation (one cell, unplanned), not a result.

It also means the regraded P4 and P5 cells are reruns, not regrades, and must not
be used as judge-robustness evidence.

## 7. Finding 6: the MQuAKE-T results are robust to the judge

For P0 to P3 on MQuAKE-T the answers are identical in both runs, so this isolates
the judge. Claude Opus 4.8 agrees with the original judge ensemble on 748 of 768
graded answers (97.4 percent).

| MQuAKE-T (pooled) | Original judge | Opus 4.8 |
|---|---|---|
| P0 | 0.969 | 0.974 |
| P1 | 0.870 | 0.885 |
| P2 | 0.969 | 0.974 |
| P3 | 0.792 | 0.807 |

Every accuracy moves by at most 1.5 points and the ordering does not change. The
judge is not what the MQuAKE-T conclusions rest on.

## 8. Every perspective, P2 against P0

Clean data only. FactConsolidation uses GLM because that is the only clean P0 cell.

| Perspective | MQuAKE-T | FactConsolidation (GLM) | ConvoMem |
|---|---|---|---|
| Accuracy | 0.969 vs 0.969, tie | 0.80 vs 0.70, P2 better (p = 0.02, judges differ) | 0.225 vs 0.235, tie (p = 0.77) |
| Staleness | 0.036 vs 0.052, n.s. | 0.06 vs 0.18, **p = 0.004** | 0.165 vs 0.225, **p = 0.008** |
| Tokens per question | 716 vs 816, **-12%** | 648 vs 748, **-13%** | 849 vs 1026, **-17%** |
| Active facts stored | 357 vs 382, -6.5% | 324 vs 380, -14.7% | 912 vs 1006, -9.3% |
| Answer quality (F1) | 0.806 vs 0.797 | 0.529 vs 0.402 | 0.299 vs 0.294 |
| Maintenance model calls | 0 | 0 | 0 |
| Reproducible under provider change | yes, exact | yes, exact | yes |

Efficiency, as accuracy per thousand prompt tokens: MQuAKE-T 1.35 vs 1.19,
FactConsolidation 1.23 vs 0.94, ConvoMem 0.27 vs 0.23. P2 is ahead on all three.

"Benchmark beating": P2 never loses significantly to P0 on any metric on any
benchmark (its largest shortfall is one point of accuracy on ConvoMem, p = 0.77).
On two of three it wins significantly on staleness, and it is cheaper on all three.

## 9. Where the hypothesis stands

| Claim | Status |
|---|---|
| Contradiction invalidation reduces stale answers | Supported on 2 of 3 benchmarks at p < 0.01; direction holds on the third |
| It does so without costing accuracy | Supported on all 3 |
| It reduces cost | Supported on all 3 (12 to 17 percent fewer tokens) |
| The result does not depend on the retrieval weights | Supported: tuning and test both flat in the gold-support region; RRF agrees |
| The result does not depend on the grace period | Supported end to end, both benchmarks |
| It generalizes to natural dialogue | Partially: staleness effect replicates, but contradiction detection has low precision there |
| It does not depend on the judge | Supported on MQuAKE-T; FactConsolidation pending a clean regrade |

## 10. Fixes made during this analysis

- `scripts/compact_results.py`: crashed on `search_summary.json` (a list, not a
  cell). It now skips non-cell JSON. `make compact` will work.
- `src/drift/runner.py`: every cell now records `prompt_fingerprint`, a hash of
  the answer and judge prompts the running process actually used. Mixed-prompt
  matrices can now be detected. Current value: `27e40cc808c2`. 119 tests pass.
- `configs/regrade_factconsolidation.json`: inserted `openrouter:z-ai/glm-5.2`
  third in the extraction list, after the two dead NVIDIA routes. Cached calls
  still hit first; cache misses (P4 consolidation) now go to the same model family
  instead of falling through to gpt-oss or Llama, which is what broke P4 in
  section 6.

## 11. What to run next

1. `make compact` (now fixed).
2. `python -m drift.runner --config configs/regrade_factconsolidation.json`.
   Despite the name, this produces the clean FactConsolidation matrix under the
   current prompt with the pinned Opus judge. 11 cells remain, about 1,100 answer
   calls and 1,100 judge calls. This is the single most important run left.
3. Point `make compare` at `factconsolidation_regraded` and `mquake_t_regraded`
   (plus `convomem`) to regenerate the cross-dataset table and Spearman on clean data.
4. Rerun the missing `mquake_t_regraded` P4 GLM cell, and note in the thesis that
   regraded P4 and P5 differ from the originals because of the consolidator change.
5. Optional: `make weights-search-convomem` and `grace-search-convomem`. Given the
   0.23 recall floor, expect ties; they are lower priority than step 2.
6. Measurement fix, no API cost: have `download_convomem.py` store the short
   current value so the sensitivity proxy can compute gold support.
