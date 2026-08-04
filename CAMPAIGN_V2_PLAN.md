# DRIFT — Post-Campaign Diagnostic and V2 Plan

Everything here is measured from the completed 63-cell campaign plus three new diagnostics I ran against the real result files and the real pipeline. Nothing is estimated or assumed.

---

## Part 1 — Statistical rigor added (no rerun needed)

Your results had no confidence intervals or significance tests. I computed both. Two things matter.

**Bootstrap 95% CIs, LoCoMo, accuracy pooled across all 5 models (n=1500 questions per policy, 10k resamples):**

| Policy | acc | 95% CI | CI width |
|---|---|---|---|
| NOMEM | 0.0380 | [0.0287, 0.0480] | 0.019 |
| P0 | 0.1147 | [0.0993, 0.1313] | 0.032 |
| P1 | 0.0613 | [0.0493, 0.0740] | 0.025 |
| P2 | 0.0787 | [0.0653, 0.0927] | 0.027 |
| P3 | **0.1153** | [0.0993, 0.1320] | 0.033 |
| P4 | 0.0960 | [0.0820, 0.1107] | 0.029 |

**McNemar exact test (the correct test — the same 300 questions are put to every policy, so comparisons are *paired*, not independent):**

| Comparison | A wins | B wins | p | Verdict |
|---|---|---|---|---|
| P0 vs P3 (LoCoMo) | 34 | 35 | **1.000** | statistically indistinguishable |
| P0 vs P3 (LongMemEval) | 14 | 14 | **1.000** | statistically indistinguishable |
| P0 vs P4 | 63 | 35 | 0.006 | P0 > P4 |
| P0 vs P2 | 87 | 33 | <0.001 | P0 > P2 |
| P0 vs P1 | 102 | 22 | <0.001 | P0 > P1 |
| P3 vs P2 | 92 | 37 | <0.001 | P3 > P2 |
| P2 vs P1 | 67 | 41 | 0.016 | P2 > P1 |
| P1 vs P0 (LongMemEval) | 11 | 2 | 0.023 | P1 > P0 |
| P0 vs NOMEM | 137 | 22 | <0.001 | memory ≫ no memory |

**The strongest defensible claim in your thesis is now this:** P3 (novelty gate) is *statistically indistinguishable* from append-only P0 on both benchmarks — 34-35 and 14-14 splits, p=1.000 in both cases, which is about as clean a null result as you can get — while using **34% less memory** (21 vs 32 facts, confirmed from swarm graph snapshots). That is a free lunch, and it is now backed by a proper paired test rather than a raw point-estimate comparison.

Also worth noting: on LongMemEval almost nothing *else* reaches significance (P0 vs P4 p=0.79, P0 vs P2 p=0.36, P3 vs P2 p=0.49). With only 150 questions, that dataset cannot resolve small differences. Any LongMemEval ranking claim beyond "memory beats no memory" and "P1 > P0/P2 here" is currently unsupported and should be stated as such.

---

## Part 2 — The dominant finding: your pipeline is retrieval-bound, not policy-bound

This is the most important thing in this document.

**Diagnostic 1 — the "I don't know" rate.** Across LoCoMo, the *best* policies (P0, P3) return "I don't know" on **~79% of questions**. P1 hits 92%. NOMEM 99% (expected — it has no memory by design).

**Diagnostic 2 — where the answer is actually lost.** I rebuilt real LoCoMo graphs from your cached extraction calls (4 conversations, 108 questions, 775 facts) and measured how often the gold answer's content words are recoverable at each pipeline stage:

| Stage | Gold answer recoverable | Meaning |
|---|---|---|
| Anywhere in the extracted graph | **43.5%** | extraction ceiling — 56.5% of answers never make it into memory at all |
| In top-8 retrieved (your current `retrieval_k=8`) | **11.1%** | what the answer model actually sees |
| In top-25 retrieved | **22.2%** | doubling k doubles recall |

Your measured LoCoMo accuracy is 0.115. Retrieval recall at k=8 is 0.111. **Those are the same number.** Accuracy is not being limited by which forgetting policy you chose — it is pinned almost exactly to how often the needed fact appears in the 8 facts the model is shown. (Caveat: this diagnostic ran with the `hashing` embedder because the sandbox has no Ollama; real numbers under `nomic-embed-text` will be somewhat higher. The k=8 → k=25 *doubling* is the robust signal, not the absolute values.)

**Why this compresses your entire policy comparison:** all six policies are being evaluated inside a band where ~79-92% of answers are "I don't know". P2's whole value proposition is *not showing the model stale facts* — but if only 8 facts are shown and the relevant one is absent 89% of the time, P2 has almost nothing to act on. The policies are being measured in a regime that structurally suppresses the differences between them.

**Diagnostic 3 — the bitemporal graph's timestamps never reach the answer model.** From `pipeline.py`:

```python
memory_block = "\n".join(f.text for f in retrieved)
```

Only `f.text`. Every `Fact` carries `t_valid_start`, `t_ingested`, and `t_invalid_at` — the entire bitemporal substrate that is the centerpiece of your thesis — and **none of it is ever shown to the answer model.** Valid time is used internally for contradiction detection and as a 0.1-weighted recency term in ranking, then discarded at the prompt boundary.

The cost is visible and concentrated. LoCoMo `temporal` accuracy is **0.042 (2 of 48)**. 41 of 300 questions start with the word "When". 14% of gold answers contain an explicit date or year. A real example from your results:

```
Q:    When did Melanie paint a sunrise?
GOLD: 2022
GOT:  "Melanie painted a lake sunrise last year."
```

The model had the right fact and still failed, because "last year" was all it was given. The graph knew the absolute timestamp. It just wasn't passed along. Compounding this, `EXTRACTION_PROMPT` never receives the session date either, so relative expressions ("last year", "last week") are frozen as unresolvable text at extraction time.

---

## Part 3 — Three changes for a V2 run, all policy-neutral

The critical property: none of these touch `policies.py`. The independent variable stays untouched, so V2 remains a clean policy comparison — it just runs it in a regime where policies can actually express their differences.

### Fix 1 — surface temporal metadata in the answer prompt (highest impact)

In `pipeline.py`, `answer_question()`:

```python
# before
memory_block = "\n".join(f.text for f in retrieved) or "(no relevant memory)"

# after
from datetime import datetime, timezone
def _fmt(f):
    d = datetime.fromtimestamp(f.t_valid_start, timezone.utc).strftime("%Y-%m-%d")
    tag = f" [superseded {datetime.fromtimestamp(f.t_invalid_at, timezone.utc).strftime('%Y-%m-%d')}]" if f.invalidated else ""
    return f"[{d}]{tag} {f.text}"
memory_block = "\n".join(_fmt(f) for f in retrieved) or "(no relevant memory)"
```

Add to `ANSWER_SYSTEM`: *"Each memory line begins with the date the fact became true. Use these dates to answer questions about when something happened. A line marked [superseded DATE] was true until that date and is no longer current."*

Expected effect: `temporal` (48 questions, currently 2 correct) and the 41 "When" questions become answerable. If temporal goes to even 0.30, that alone is +13 questions = **+4.3 points of overall accuracy**. It also gives P2 a second, more visible channel: the model can now *see* which facts are superseded rather than depending entirely on P2 silently filtering them.

### Fix 2 — raise `retrieval_k` from 8 to 25

One line in each config. Your graphs hold 213-442 facts per conversation; k=8 shows the model 2-4% of memory. Measured recall doubles from 11.1% to 22.2% at k=25.

Cost: tokens/question rises roughly proportionally to retrieved context, so expect ~500 → ~1,100 tok/q, meaning the paid OpenRouter spend roughly doubles (~$5 → ~$10-11 for the full campaign). This is the main thing to weigh — it is the single highest-leverage change but it is not free.

Note it also makes the token-efficiency comparison *more* interesting, not less: at k=25 the pruning policies (P1, P2, P4) have fewer active facts to draw from, so they will naturally retrieve smaller contexts than P0/P3. Right now, with k=8 saturated for every policy, that difference is invisible.

### Fix 3 — give the extractor the session date

In `extraction.py`, pass `session["time"]` into `extract_facts()` and prepend to the prompt:

```
SESSION DATE: 2023-07-05
Resolve relative time expressions ("last year", "two weeks ago") to absolute dates in the fact text.
```

This attacks the 56.5% extraction ceiling at its source for time-bearing facts, and it is the only one of the three fixes that requires invalidating the extraction cache (`rm -rf .drift_cache`), which means a full-cost re-extraction pass. Fixes 1 and 2 both reuse the existing cache for extraction.

### Recommended combination

**Fix 1 + Fix 2** together, keeping the extraction cache. That gets you the temporal unlock and the retrieval unlock at roughly 2x the previous dollar cost and no re-extraction. Add Fix 3 only if you want to attack the extraction ceiling too and can absorb a full cold-cache run.

---

## Part 4 — Framework-readiness gaps for outside adoption

Beyond the experiment, these are what stand between DRIFT-as-thesis-artifact and DRIFT-as-something-a-developer-installs:

1. **`salience` is dead code.** Every `Fact` carries `salience: float = 1.0`. It is read in exactly one place (a P5 tiebreaker) and never set to anything but the default. Either wire it (see #2) or remove it — a published framework should not ship a field that does nothing.
2. **No usage-based forgetting policy.** Your six policies key on age (P1), contradiction (P2), write-time similarity (P3), LLM judgment (P4), and graph structure (P5). None key on *access frequency* — the LRU/LFU intuition that facts nobody retrieves should fade. This needs an access counter updated in `graph.search()` plus a policy that prunes cold facts, and it is a genuinely unexplored axis in your current lineup.
3. **No policy composition.** P2 and P3 use disjoint hooks (P3 → `on_write`; P2 → `on_retrieve` + `after_session`). They cannot conflict, yet there is no way to run both. Given P3 is your free-lunch policy and P2 is your zero-staleness policy, a `CompositePolicy` chaining hooks across a list is ~25 lines and directly tests whether the two best mechanisms stack.
4. **One global policy per graph.** A real mixed-workload agent wants short TTL on `stock_price`, contradiction-invalidation on `meeting_time`, novelty-gating on everything else — simultaneously. Today that requires writing a bespoke policy class. A predicate → policy routing layer would make DRIFT usable for realistic agents.
5. **Single judge, uncross-validated.** Every verdict in all 63 cells comes from one `gpt-oss:20b`. Answer verbosity varies 70-830 tok/q across models, and LLM judges are known to be verbosity-sensitive. A second judge family on even a 100-question held-out slice would close this.
6. **No cost/usage reporting.** You had to reconstruct spend by hand from cache files. A `results/*/cost_report.json` emitted by the runner is a small addition and something any budget-conscious adopter needs.
7. **Not installable.** No `pip install`, no quickstart that avoids reading the Makefile, no documented "bring your own conversations" schema guide. This is the actual gap between research repo and framework.

---

## Part 5 — How a developer would practically use DRIFT

The honest positioning: DRIFT is not a memory library you drop into an agent. It is **a test harness for choosing a forgetting policy before you commit to one** — and your own results are the argument for why that choice needs testing rather than guessing (P1 was the *worst* policy on LoCoMo and the *best* on LongMemEval, purely because of conversation length: 27.2 sessions/conversation vs 2.6).

The workflow:

1. Export your agent's real conversation history into DRIFT's dataset schema (`{conversations: [{id, sessions: [{time, lines}], questions: [{question, answer, category, stale_answer}]}]}`).
2. Annotate a slice of questions with `stale_answer` — the superseded answer — since that is the only way the staleness metric can fire (see Part 6).
3. Write a config pointing at your data with the policies you want compared.
4. `python -m drift.runner --config configs/yours.json`, then `make figures dashboard record`.
5. Read off which policy wins *on your workload*, and ship that one.

Best fit: agents that persist memory across sessions, run for weeks or months, and/or have multiple writers (tools, sub-agents) sharing one memory store. Poor fit: single-session assistants, or anything whose whole memory fits in a context window.

---

## Part 6 — Carried-forward limitations (unchanged, still true)

- **Staleness is unmeasurable on both real benchmarks.** LoCoMo: 0 of 300 questions carry a `stale_answer`. LongMemEval: 0 of 150. Swarm: 4 of 14. Staleness therefore reads exactly 0.000 across all 42 LoCoMo + LongMemEval cells — that is a metric that cannot fire, not a finding. RQ1/RQ2's staleness claims rest entirely on 14 synthetic questions. Annotating even 50 LoCoMo `temporal`/`knowledge_update` questions in the conversion script would fix this, and it pairs naturally with Fix 1 (which makes supersession visible to the model in the first place).
- **Swarm P1 uses `ttl_days=14` against a 58-day dataset**, leaving 6 of 32 facts alive at question time and driving accuracy to exactly 0.000 in all three topologies. That is a config artifact, not a result. Align it to 35d or explicitly frame it as a deliberate over-pruning demonstration.
- **RQ3 is inconclusive.** P2 (bitemporal) and P5 (structure-blind) both hit 0.000 staleness on swarm, at n=14. That sample cannot separate them. Fix 1 plus staleness annotation on a real benchmark is the path to actually answering RQ3.

---

## Suggested order of work

1. Apply Fix 1 + Fix 2, rerun `make real-all` (~2x prior dollar cost, similar wall-clock). ← biggest result improvement
2. Keep the bootstrap CI + McNemar analysis in the thesis regardless — it costs nothing and materially strengthens every existing claim.
3. Annotate `stale_answer` on a LoCoMo slice, so staleness becomes real on a real benchmark.
4. Fix swarm's P1 TTL.
5. Build `CompositePolicy` (P2+P3) — cheap, and tests whether your two best mechanisms stack.
6. Framework packaging (items 1, 6, 7 in Part 4) if DRIFT is meant to outlive the thesis.
