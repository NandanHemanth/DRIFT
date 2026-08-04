# DRIFT Real-Data Campaign — Complete Analysis

**Scope:** all 63 cells of `make real-all` (30 LoCoMo + 12 LongMemEval + 21 swarm), read directly from `results/*/*.json` on 2026-07-29. Every number below is pulled from the actual result files, not reconstructed from terminal output.

---

## 1. Architecture recap — what actually ran

**The single-agent pipeline (LoCoMo, LongMemEval, via `drift/runner.py`).** For each `(policy, model)` cell: raw session text → `extract_facts()` (LLM call, policy-independent) → the policy's `on_write()` gate → `BitemporalGraph.add_fact()` (which auto-closes the valid-time window of any contradicted functional-predicate fact, unconditionally) → the policy's `after_session()` maintenance → for each question, hybrid retrieval (0.6·cosine + 0.3·lexical + 0.1·recency) → the policy's `on_retrieve()` filter → answer LLM → judge LLM (always local `gpt-oss:20b`, so it never varies with the cell) + token-F1. 30 cells = 6 policies × 5 models; 12 cells = 6 policies × 2 models (LongMemEval only exercises glm-5.2 and minimax-m3 to keep judge-quota cost down).

**The swarm extension (`drift/swarm.py`), three topologies over the same synthetic 58-day, 10-session, 14-question dataset:**
- **`shared`** — 5 writer agents round-robin-ingest one interleaved global timeline into a single shared graph, each fact tagged with its writer (`provenance`). Isolates whether a policy's contradiction-handling survives *multi-writer contention* — does invalidation still work correctly when the contradicting fact came from a different agent than the one that wrote the original?
- **`independent`** — 5 agents, each with a private graph, each observing a random ~80%-coverage subset of sessions (seeded). Reports mean±std accuracy across agents — isolates *robustness under partial observation* rather than a single deterministic read.
- **`orchestrator`** — one shared graph, a router LLM assigns each question to one of 5 specialist workers by category. Isolates the *production coordinator/worker* read pattern rather than a single reader.

All three hold the memory substrate, extraction, retrieval, and judge fixed — only the *usage pattern* changes, exactly the same "everything constant except one variable" discipline as the main policy comparison, just with topology as the second axis instead of model.

---

## 2. Full results

### 2.1 LoCoMo (30/30 cells, 300 questions/cell)

| Policy | glm-5.2 | minimax-m3 | gemini-3.1-flash-lite | nemotron-3-ultra | tencent/hy3 | **avg acc** | avg f1 | avg tok/q |
|---|---|---|---|---|---|---|---|---|
| NOMEM | 0.043 | 0.037 | 0.037 | 0.037 | 0.037 | **0.038** | 0.000 | 157 |
| P0 (no forgetting) | 0.140 | 0.130 | 0.107 | 0.097 | 0.100 | **0.115** | 0.067 | 509 |
| P1 (TTL 35d) | 0.067 | 0.057 | 0.057 | 0.060 | 0.067 | **0.061** | 0.027 | 436 |
| P2 (contradiction) | 0.073 | 0.093 | 0.077 | 0.080 | 0.070 | **0.079** | 0.036 | 462 |
| P3 (novelty gate) | 0.127 | 0.130 | 0.110 | 0.100 | 0.110 | **0.115** | 0.072 | 522 |
| P4 (LLM consolidation) | 0.103 | 0.107 | 0.083 | 0.100 | 0.087 | **0.096** | 0.050 | 500 |

Ranking: **P0 ≈ P3 > P4 > P2 > P1 ≫ NOMEM.**

### 2.2 LongMemEval (12/12 cells, 150 questions/cell, glm-5.2 + minimax-m3 only)

| Policy | glm-5.2 | minimax-m3 | **avg acc** | avg f1 | avg tok/q |
|---|---|---|---|---|---|
| NOMEM | 0.053 | 0.073 | **0.063** | 0.009 | 219 |
| P0 | 0.193 | 0.220 | **0.207** | 0.099 | 792 |
| P1 (TTL 35d) | 0.227 | 0.247 | **0.237** | 0.102 | 772 |
| P2 | 0.167 | 0.213 | **0.190** | 0.090 | 616 |
| P3 | 0.233 | 0.180 | **0.207** | 0.103 | 785 |
| P4 | 0.193 | 0.207 | **0.200** | 0.097 | 757 |

Ranking: **P1 > P0 ≈ P3 > P4 > P2 ≫ NOMEM.**

**This is the opposite order from LoCoMo — P1 flips from worst to best.** Section 3 explains why, with category-level evidence, not just an observation.

### 2.3 Swarm (21/21 cells, `ttl_days=14` for P1 here — different from the 35d used above)

| Topology | NOMEM | P0 | P1(14d) | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|---|---|
| shared | 0.000 | 0.571 | **0.000** | 0.286 | 0.357 | 0.500 | 0.143 |
| independent (mean±std) | 0.000±0.00 | 0.529±0.06 | **0.000±0.00** | 0.200±0.09 | 0.129±0.03 | 0.414±0.16 | 0.143±0.07 |
| orchestrator | 0.000 | 0.571 | **0.000** | 0.143 | 0.143 | 0.500 | 0.286 |

Staleness (the metric only this dataset can actually measure — see §4): P3 shows real staleness (0.057–0.071) in every topology; **P2 shows exactly 0.000 staleness in all three**, and so does P5. Cross-writer invalidations (`shared` topology): NOMEM/P0/P2 all record 15 invalidations (9 cross-writer); P1 only 11 (5 cross-writer, because most facts are pruned before they'd even have a chance to be contradicted); P3 only 6, but *all six* are cross-writer (its novelty gate suppresses a writer contradicting itself, but not two different writers disagreeing).

---

## 3. The headline finding: policy rankings are not stable across datasets, and the reversal is mechanistically explainable

Averaged rankings:
- **LoCoMo:** P0 ≈ P3 > P4 > P2 > P1
- **LongMemEval:** P1 > P0 ≈ P3 > P4 > P2

P1 (35-day TTL decay) is LoCoMo's *worst* real policy and LongMemEval's *best*. Category-level breakdowns (glm-5.2, both datasets) explain why:

**LongMemEval, P0 vs P1, by category:**
| Category | P0 acc | P1 acc |
|---|---|---|
| knowledge_update | 0.179 | **0.357** |
| multi_hop | 0.242 | 0.242 |
| temporal | 0.150 | 0.150 |

**LoCoMo, P0 vs P1, by category:**
| Category | P0 acc | P1 acc |
|---|---|---|
| single_hop | 0.181 | 0.087 |
| multi_hop | 0.140 | 0.047 |
| temporal | 0.042 | **0.000** |
| adversarial | 0.149 | 0.090 |
| open_domain | 0.067 | 0.067 |

The mechanism: LongMemEval's 150 conversations average **2.6 sessions each**; LoCoMo's 10 conversations average **27.2 sessions each** (verified directly from the dataset files). A fixed 35-day TTL almost never fires within a 2.6-session conversation — that's exactly why P0 and P1 are *identical* on LongMemEval's `multi_hop` and `temporal` categories (down to three decimal places): the policy is doing effectively nothing there. Its entire measured benefit is concentrated in `knowledge_update` — questions specifically about facts that changed — where removing old competing information (even via blunt time-based pruning rather than smart contradiction-detection) roughly doubles accuracy. On LoCoMo, the same TTL fires constantly across 19–32-session conversations, and it collapses accuracy hardest on exactly the categories that need long-range recall (`temporal` goes to literal zero). This is a stronger, more useful result than "P0 wins" or "P1 wins" — it shows *when* naive time-based forgetting helps (short-lived, single-question conversations with real fact turnover) versus when it actively destroys needed recall (long, multi-session conversations), which is a genuinely thesis-worthy insight about conversation *structure*, not just policy design.

---

## 4. A real, structural limitation: staleness is only measurable on the swarm dataset

Checked directly against the dataset files:

| Dataset | Questions | Carry a `stale_answer` annotation |
|---|---|---|
| LoCoMo | 300 | **0** |
| LongMemEval | 150 | **0** |
| Swarm (synthetic) | 14 | 4 |

`staleness_hit()` can only return `True` against a question that has a `stale_answer` to check against. This means **staleness reads exactly 0.000 for every single policy across all 42 LoCoMo + LongMemEval cells** — not a finding, a metric that structurally cannot fire on those two datasets. The only place your campaign can show real staleness signal is the 14-question swarm set, where it does show something real: P2 and P5 both hit zero staleness, P3 and P0 don't. This is worth being explicit about in the thesis — RQ1/RQ2's staleness claims are empirically supported only by the swarm data, not by the two headline conversational benchmarks, unless the LoCoMo/LongMemEval conversion scripts are extended to annotate `stale_answer` on their `knowledge_update`/`temporal` categories (which do exist in both datasets' category taxonomies — the ground truth for "what was the old answer" just isn't being carried through the conversion).

---

## 5. A likely configuration mismatch worth fixing before any rerun

`configs/swarm_real.json` sets `P1:ttl_days=14`, while `locomo.json`/`longmemeval.json` use `P1:ttl_days=35`. The swarm's synthetic dataset spans **58 days** across 10 sessions (verified: session timestamps at days 0, 0, 10, 12, 25, 30, 40, 45, 55, 58). Questions are answered using the *final* session's timestamp as "now." With a 14-day TTL, by the time any question is asked, only facts from the last ~13 days of that 58-day span are still alive — the actual final-graph stats confirm this directly: **P1 ended with only 6 of 32 facts still active (81% pruned)**, versus P2's 18/32 and P4's 24/32. That's not "TTL decay doesn't work," it's "a 14-day window against a 58-day-spanning dataset, evaluated only at the very end, wipes out almost everything regardless of policy quality" — accuracy reads exactly 0.000 in all three topologies as a direct consequence, not as a meaningful comparison point. Two honest options: (a) treat this as an intentional demonstration of over-aggressive forgetting and frame it that way in the writeup, or (b) re-run just the P1 swarm cells with a TTL closer to what the other two configs use (e.g. 35–45 days) to get a comparison that's actually informative about TTL decay's *design*, not just this specific mismatch. I'd lean toward (b) if you want P1's swarm result to mean anything — it's currently a floor artifact, not a data point.

---

## 6. Memory-footprint confirmation for P3 (the "smaller memory, neutral accuracy" hypothesis)

LoCoMo's config never saves graph snapshots, but swarm's does, and the `shared`-topology final-memory stats confirm P3's hypothesis directly: **P3 ended with 21 total facts (11 write-rejections) versus 32 for every other policy** — a genuinely smaller memory — while its accuracy (0.357) was third-best, comfortably ahead of P2 (0.286) and P5 (0.143). Combined with LoCoMo's accuracy-parity finding (§2.1), P3 is the one policy in this campaign whose result matches its stated hypothesis on both axes (memory size *and* accuracy) with essentially no caveats.

---

## 7. Answering RQ1–RQ4 with what this campaign actually supports

- **RQ1 (staleness growth):** unanswerable on LoCoMo/LongMemEval (§4); on swarm, P0's append-only baseline does show nonzero staleness (0.071 in `shared`) where P2 shows zero — consistent with the hypothesis, but on an n=14 sample.
- **RQ2 (best accuracy–staleness–cost trade-off):** dataset-dependent (§3) rather than a single answer — P3 is the most consistently strong performer across both real conversational benchmarks; P0 is a close second everywhere but carries no forgetting-related engineering value; P4 is respectable but never the best; P1 is highly conversation-structure-sensitive (best on short conversations, worst on long ones); P2's real payoff (staleness reduction) is only visible on swarm.
- **RQ3 (does bitemporal structure specifically beat structure-blind alternatives):** on swarm, P2 (bitemporal) and P5 (structure-blind, time-agnostic) tie at zero staleness — inconclusive at n=14, not a clean win for either side. On LoCoMo/LongMemEval accuracy, P2 is consistently middle-of-pack, never matching P0/P3 — the bitemporal mechanism isn't currently translating into an accuracy advantage on real data, only (unverifiably, per §4) a hypothesized staleness one.
- **RQ4 (do rankings survive multi-agent usage):** yes, directionally — P0 and P4 are the top two performers in all three swarm topologies, matching their strength in the single-agent runs; P1's collapse is a config artifact (§5) rather than a topology effect, since it fails identically across all three topologies.

---

## 8. Practical guidance if DRIFT becomes a framework other developers build on

Based purely on what this campaign measured: **P3 (novelty gate) is the safest default** — it matched or exceeded P0's accuracy on both real benchmarks while genuinely shrinking memory (confirmed on swarm), with a single, cheap, tunable hyperparameter (τ) and no LLM calls of its own. **P2 is the right choice specifically when staleness is a known, verifiable problem in your domain** (e.g. you can annotate or spot-check that facts do get contradicted and old answers do leak through) — its cost is a real accuracy hit on these two datasets that isn't yet shown to buy anything measurable outside swarm. **P4 is viable if you can afford periodic LLM calls** and want consolidation, but it's never the top performer here, and the literature it's built to test (arXiv:2605.12978) warns it can degrade memory over repeated cycles — worth stress-testing over a longer campaign (more than 10 conversations) before trusting it at production scale. **P1 (naive TTL) is not a safe default** for anything with long-running, multi-session context — it's only a good idea when conversations are structurally short-lived, which you'd need to know about your own workload in advance.

---

## 9. Recommended next steps

1. **Rerun just the swarm `P1` cells** with a TTL comparable to the other configs (or explicitly document the 14d choice as an intentional extreme case) — currently a floor artifact, not informative.
2. **Consider annotating `stale_answer` on a subset of LoCoMo/LongMemEval's `temporal`/`knowledge_update` questions** in their conversion scripts if you want the staleness metric to mean anything on your two headline benchmarks — right now RQ1/RQ2's staleness claims rest entirely on 14 synthetic questions.
3. **The category-level P1 reversal (§3) is worth a dedicated subsection in the thesis** — it's a stronger, more specific finding than a flat "policy X wins," and it's fully supported by the data already collected; no rerun needed for this one, just the write-up.
4. Everything else (P0/P2/P3/P4 rankings, P3's memory-footprint confirmation, the RQ3 ablation being inconclusive at swarm's current sample size) is solid as-is; a larger swarm dataset (more than 14 questions) would tighten the RQ3 comparison's confidence, but isn't required to report the current result honestly with its caveats stated.
