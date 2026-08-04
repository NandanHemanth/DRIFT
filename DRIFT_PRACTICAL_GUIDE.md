# DRIFT in Plain Terms — Hypothesis, Benchmarks, and a JARVIS Walkthrough

## 1. The hypothesis, in simple terms

Every AI agent that remembers things across conversations eventually faces the same problem: memory fills up with facts that used to be true and no longer are. "I live in Boston" is still sitting in memory after you've told the agent three times you moved to Seattle. Most existing memory systems (Mem0, Letta/MemGPT, Zep) never really solve this — they focus on storing and finding facts, and treat *deleting or updating* facts as an afterthought.

Your hypothesis: **the rule that decides what to forget is not a minor detail — it's the single biggest lever for whether an agent's memory helps or actively hurts it.** So you built one fixed memory substrate (the bitemporal graph) and swapped out only that one rule — the "forgetting policy" — six different ways (NOMEM, P0, P1-P5), to see which rule actually produces accurate, non-confused answers over time.

## 2. How the swarm results specifically support this

The single-agent tests (LoCoMo, LongMemEval) already show the policy matters — accuracy roughly doubles or triples just from having memory at all, and the *best* policy changes depending on conversation shape. But swarm adds a harder, more realistic test: **what if memory isn't written by one tidy conversation, but by several agents at once, each seeing only part of the picture** — which is how real production agent systems actually work (a calendar module, an email module, a finance module, all writing into one shared memory).

Two swarm results directly support the core hypothesis:

- **P2 (bitemporal contradiction handling) hit exactly 0.000 staleness in every one of the three multi-agent topologies** — shared writers, private partial-observation agents, and a router/worker setup. P3 (novelty gate), by contrast, still let stale answers through 5.7-7.1% of the time in the same settings. Same substrate, same models, same everything — the only thing that changed was the forgetting rule, and that alone was the difference between an agent that never surfaces outdated info and one that sometimes does.
- **Cross-writer invalidation held up under contention.** When agent B's fact contradicted agent A's earlier fact, the substrate correctly closed agent A's fact's validity window regardless of who wrote what — 9 of 15 invalidations in the shared topology were genuinely cross-writer. This is the concrete version of "does the memory-management logic survive when multiple agents share it," and the answer is yes, without needing anything policy-specific to make it work — it's substrate behavior your bitemporal design gets for free.

In short: swarm shows the policy differences aren't just an artifact of one conversation's structure — they persist even when memory is being hit from multiple directions at once, which is the scenario that actually matters for anyone deploying this beyond a single chatbot.

## 3. The benchmarks, side by side

**Accuracy — DRIFT's policies vs. "normal" agent memory.** Think of `NOMEM` as a stateless chatbot (no persistent memory at all) and `P0` as what most current production memory systems effectively do (append-only, nothing ever removed — this is the Mem0/Letta/Zep default). Everything from `P1` onward is DRIFT's actual contribution — a real forgetting rule layered on top.

| | NOMEM (no memory) | P0 (typical "normal" memory today) | Best DRIFT policy |
|---|---|---|---|
| LoCoMo avg accuracy | 0.038 | 0.115 | 0.115 (P3, tied with P0, at lower memory cost) |
| LongMemEval avg accuracy | 0.063 | 0.207 | 0.237 (P1, on this dataset specifically) |
| Swarm (shared) accuracy | 0.000 | 0.571 | 0.500 (P4) — none beat P0 outright here |

**Reading this honestly:** memory (any memory) is a 2-3x accuracy jump over none. DRIFT's forgetting policies don't reliably beat naive append-only on raw accuracy — what they buy you is the same or comparable accuracy at a real, measurable cost reduction (P3: 21 vs 32 facts, i.e. ~34% smaller memory) and, on the one dataset that can measure it, a genuine staleness elimination (P2: 0.000 vs P0's nonzero). The honest pitch isn't "DRIFT makes your agent smarter," it's "DRIFT gives you the same intelligence for less memory and fewer stale answers" — which matters enormously at scale, less so for a single short-lived chat.

**Token/cost efficiency per question, averaged across models (LoCoMo):**

| Policy | avg tokens/question | relative cost vs P0 |
|---|---|---|
| NOMEM | 157 | −69% (but near-zero accuracy) |
| P1 | 436 | −14% |
| P2 | 462 | −9% |
| P4 | 500 | −2% |
| P0 | 509 | baseline |
| P3 | 522 | +3% |

P2 is the cheapest *useful* policy per question; P3 is slightly more expensive than P0 but pays for it in memory-footprint savings instead of per-query cost.

**Memory footprint (swarm, confirmed via saved graph snapshots):** P0/NOMEM keep all 32 facts ever written. P3 keeps 21 (11 rejected as duplicates before ever being stored). P2 keeps 18 (14 pruned after a grace period). P1 (misconfigured TTL, see the main analysis) keeps only 6. This is the clearest, most literal "DRIFT vs normal memory" comparison you have: normal memory grows without bound; every DRIFT policy except P0 itself visibly caps that growth, with P3 doing so without giving up accuracy.

## 4. How someone else would actually use this framework, and where it helps

DRIFT is not a product — it's a way to *decide which forgetting rule to ship* before you commit to one in a real agent. The practical use is: take your own conversational data (or a representative sample), plug it into DRIFT's dataset schema, run the same six-policy comparison, and read off which policy actually helps *your* workload — because as this campaign showed, the answer depends on your conversation shape (short vs. long, single-writer vs. multi-writer), not on some universal "best" policy.

It's most useful for anyone building an agent that: (a) needs to remember things across sessions, not just within one conversation, (b) will run for weeks or months and accumulate enough memory that append-only becomes expensive or noisy, or (c) has more than one writer touching the same memory (multiple tools, sub-agents, or team members). It's overkill for a single-session assistant with no persistence, or an agent whose entire "memory" fits in one context window anyway.

## 5. Worked example: a JARVIS-style personal desktop agent

**Important framing:** everything below is a reasoned walkthrough grounded in the patterns your real campaign already measured — it is not a new benchmark run, and I'm not going to invent precise numbers as if they were measured on a dataset that doesn't exist. If you want *real* numbers for this exact scenario, the right move (and the one DRIFT is built for) is to build a small synthetic dataset that mimics this agent's information stream — a handful of simulated days of emails, Slack messages, and financial updates, with a few questions annotated with `stale_answer` ground truth — and run it through `drift.runner` exactly like LoCoMo or the swarm smoke set. I can build that dataset and config with you right now if you want the real thing instead of the walkthrough.

**The scenario:** your agent watches email, Slack, financial news, and a calendar, and needs to answer questions like "when is the team meeting," "what's my Q3 deadline," "how's AAPL doing" — weeks or months into continuous operation.

**Simulated week:** Day 1, an email says the team meeting is Thursday 3pm. Day 3, a follow-up email moves it to Thursday 4pm — a direct contradiction on a functional predicate (`meeting_time`), exactly like LoCoMo's `lives_in`/`works_at` cases your substrate already handles automatically. Day 2 and Day 5, financial news pushes AAPL price updates — high-volume, low-retention-value facts that are stale almost by definition within a day. Day 4, Slack has three separate people restating the same reminder about the Q3 deadline — a novelty-gate case, not a contradiction. Day 15, the user asks about the meeting time, the deadline, and AAPL's price.

**How each approach behaves, reasoning from what you actually measured:**

- **No memory (stateless):** can't answer any of it unless re-told in the same session — unusable for a JARVIS-style agent that's supposed to *remember*.
- **Naive append-only (P0-equivalent, what most memory products do today):** technically has the 4pm update, but the 3pm mention is still sitting there too, and by month three you have thousands of AAPL price mentions cluttering retrieval alongside the handful of facts that actually matter. Matches what you measured directly: real accuracy, but the highest token cost (509-792/question) and a memory footprint that only grows.
- **P1 (TTL) applied to everything uniformly:** would correctly clear out stale AAPL prices (good — that's exactly the short-lived, high-turnover case where your LongMemEval category breakdown showed TTL doubling accuracy on `knowledge_update`-style questions). But applied to the *whole* graph, the same short TTL would also silently erase the Q3 deadline or an old but still-relevant conversation, exactly the failure mode that drove LoCoMo's `temporal` category to zero. This is the clearest argument that **DRIFT's current one-policy-per-graph model is too coarse for a real mixed-workload agent** — see the fix below.
- **P2 (contradiction invalidation):** directly fixes the meeting-time bug — the moment the 4pm email is ingested, the 3pm fact's validity window closes and it's excluded from retrieval, with zero reliance on a time window guess. This is the single most directly transferable win from your campaign to this use case, since scheduling/deadline updates are exactly the functional-predicate pattern P2 is built for, and it's the one policy your swarm data actually proved gets staleness to zero.
- **P3 (novelty gate):** stops the three duplicate Slack reminders from ever becoming three separate facts, keeping the graph smaller without touching real information — directly useful given how repetitive a real message/email stream is.
- **P4 (LLM consolidation):** could periodically compress a week of AAPL ticks into one summary fact ("AAPL trended up ~1% this week") — a genuinely good fit for a high-volume, low-individual-value stream, but it costs a real LLM call per consolidation pass and, per your own literature citation (arXiv:2605.12978) and your P4 results never being the top performer, it's the one policy I'd stress-test longer before trusting unattended.
- **P5 (structural consolidation):** less naturally suited here since this is mostly a single-writer setup — it's built for exactly the case your `shared` swarm topology tests, which brings up the most useful structural insight of this whole exercise:

**Your swarm topologies already model a "real" JARVIS-style agent, if it's built the sensible way.** A production JARVIS would almost certainly be several specialist sub-agents (an email agent, a calendar agent, a finance-monitoring agent) all writing into one shared memory, with a router directing "what's my schedule today" to the calendar agent and "how's my portfolio" to the finance agent. That's *exactly* your `shared` and `orchestrator` swarm topologies, not a hypothetical extension — you've already tested the architecture this use case actually needs, just with a different question set.

**What this points to for DRIFT as a framework (concrete, new fixes, not restating the earlier list):**

1. **Support per-predicate or per-source policy assignment, not one global policy per graph.** Right now a `Policy` instance governs the entire `BitemporalGraph` uniformly. A real mixed-workload agent wants `stock_price`-type facts on a short TTL, `meeting_time`/`deadline`-type facts on contradiction-invalidation, and everything else on a novelty gate — simultaneously. That's not possible today without writing one big bespoke policy class per deployment; a small routing layer (map predicate or `provenance` → policy) would make DRIFT usable for realistic mixed-source agents like this one without users having to reinvent that logic themselves.
2. **Composable policies.** Related to #1: there's currently no way to combine two policies' hooks (e.g., P2's contradiction handling *and* P3's novelty gate at the same time) — each is a standalone class. A `CompositePolicy` that chains `on_write`/`after_session`/`on_retrieve` across a list of policies would be a small, mechanical addition given how narrow the interface already is, and it directly matches what this JARVIS scenario actually needs.

## 6. Is there anything left to make DRIFT "perfect"? An honest list

Nothing here blocks the thesis — these are the gaps worth knowing about, roughly in order of how much they'd matter to someone adopting DRIFT for real:

- **Per-predicate/composable policies** (§5) — the biggest real gap for practical adoption beyond a single-policy research comparison.
- **The staleness metric only works on 14 synthetic questions right now** (already flagged) — annotate `stale_answer` on a slice of LoCoMo/LongMemEval's `knowledge_update`/`temporal` categories if you want that half of the RQ1/RQ2 story backed by real conversational data, not just synthetic.
- **The swarm P1 TTL (14 days) is a likely misconfiguration**, not a real data point (already flagged) — worth a small rerun or an explicit reframe.
- **Single judge model, uncross-validated.** Every verdict in every cell comes from one `gpt-oss:20b` judge. Token-F1 is your model-free cross-check, but a second, independent judge family (even just on a small held-out sample) would strengthen the "the judge isn't quietly biased toward or against a particular answer style" claim, especially since some answer models (glm-5.2, minimax-m3) are notably more verbose than others (70-830 tokens/answer) and verbosity can bias LLM judges.
- **No statistical significance testing.** Every accuracy number is a point estimate over 150-300 questions (14 for swarm); nothing in the current pipeline reports confidence intervals or significance tests between policies, so a 0.140 vs 0.130 difference (P0 vs P3, glm-5.2) is currently presented with the same confidence as a 0.140 vs 0.037 difference (P0 vs NOMEM) even though the latter is obviously more robust to noise. Adding a simple bootstrap CI to `analysis/report_tables.py` would materially strengthen every claim in the thesis.
- **No built-in cost/usage tracking.** You now know campaign cost by manually pulling cache files and reasoning about token counts — there's no first-class `results/*/cost_report.json` the framework produces itself, which anyone adopting DRIFT for a real budget-conscious deployment would want out of the box.
- **Packaging/onboarding for outside adoption.** Right now DRIFT is a research repo you run with `make`. If the goal is "other developers or companies use this," it eventually needs a pip-installable package, a quickstart that doesn't require reading the Makefile, and a documented dataset schema for bringing your own conversations — none of that exists yet, and none of it needs to before the thesis is done, but it's the actual gap between "research framework" and "framework other people install."

None of these are corrections to what you've already measured — they're the honest list of what "done" looks like next, if DRIFT's life continues past this thesis.
