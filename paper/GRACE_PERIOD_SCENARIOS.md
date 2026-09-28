# Choosing P2's grace period: what the trade-off means for real deployments

The sweeps established what the grace period does mechanically. This section
answers the question that follows, which is what a practitioner should actually
set it to, and why the answer is not the same for every deployment.

## 1. What the parameter controls, restated precisely

When a new fact contradicts an older one on a functional predicate, P2 closes the
older fact's validity window. It does not delete it. Retrieval then excludes any
fact whose window is closed, every time, regardless of how old that closure is.

The grace period governs one thing only: how long a closed fact remains in
storage before it is physically pruned. Because retrieval already filters on
validity rather than on age, the grace period cannot decide whether a superseded
value reaches the model. It decides how long that dead fact keeps occupying one
of the k retrieval slots, and how long the historical record survives.

That gives a clean statement of the trade-off. Shorter grace buys retrieval
efficiency and a smaller footprint. Longer grace buys history.

## 2. The measured trade-off

On MQuAKE-T every correctness metric is identical at 0, 1, 3, 7, 14 and 30 days.
Only cost moves:

| grace | wasted slots | live facts in context | active facts | storage saved vs P0 |
|---|---|---|---|---|
| 1 day | 2.62 | 22.4 | 340 | 11.0% |
| 3 days | 2.78 | 22.2 | 345 | 9.7% |
| 7 days | 3.51 | 21.5 | 357 | 6.5% |
| 14 days | 4.46 | 20.5 | 370 | 3.1% |
| 30 days | 4.80 | 20.2 | 382 | 0.0% |

Two things are worth pulling out of that table. The storage advantage P2 holds
over append-only memory is entirely a function of this parameter: 11 percent at
one day, and exactly zero at thirty, where P2's footprint equals P0's. And on
FactConsolidation the correctness columns are not perfectly flat, moving 0.030 on
clean retrieval across the range, which sits exactly at the judge noise floor and
is explained by context narrowing rather than by invalidation.

## 3. Why the efficiency argument alone gives the wrong answer

Every metric currently measured improves as the grace period shortens. Taken at
face value that argues for zero. Zero is the wrong recommendation, and the reason
is worth stating because it is the same reason the thesis exists.

Pruning is the only destructive operation in the system. Contradiction closing is
non-destructive by design, and the bitemporal record is what makes it possible to
answer "what did we believe, and when". At grace zero, P2 stops being a
bitemporal policy and becomes delete-on-contradiction. It would still score well
on every metric in this thesis, because no metric here rewards retaining history.
The measurement is one-sided, and a recommendation derived only from it inherits
that bias.

## 4. Deployment archetypes

The right grace period is set by what the deployment needs to be able to answer
later, not by the retrieval curve.

**High-churn personal assistant. Grace of 1 to 3 days.**
Preferences, plans and small logistics that change often and carry no obligation
to remember prior states. A user who reschedules dinner three times does not
expect the assistant to recall the first two times, and the storage and retrieval
savings are real at this end of the range. This is the only archetype where the
efficiency argument is the whole argument.

**General assistant with recall expectations. Grace of 7 to 14 days.**
The default. Users occasionally ask about the recent past ("weren't we meeting on
Tuesday before?"), so a superseded fact is worth keeping for about as long as a
person would plausibly refer back to it. Two weeks covers most conversational
callbacks while still pruning meaningfully. The published value of 7 sits at the
efficient end of this band.

**Regulated domains: finance, healthcare, insurance, legal. Grace of 90 days or
longer, or no pruning at all.**
Here the historical record is the product. A clinician needs to know what the
chart said at the time a decision was made; an auditor needs the state of a file
on a given date. In these settings the correct configuration is often to disable
pruning entirely and accept the footprint, using P2 purely as a retrieval filter
while the closed windows remain queryable. The thesis supports this: retrieval
hygiene comes from the validity check, not from pruning, so you keep all of P2's
correctness benefit and give up only the storage saving.

**Right-to-be-forgotten and deletion requests. Grace is the wrong instrument.**
Erasure obligations are event-driven, not age-driven. They need targeted deletion
on request, which is a different operation from time-based pruning. The bitemporal
record helps by making it possible to prove what was deleted and when, but the
grace period should not be used as a compliance mechanism.

**Incident response and debugging. Grace of 30 days or longer.**
When an agent produces a wrong answer, the investigation needs the memory state
as it stood at that moment. A short grace destroys the evidence before anyone
looks for it. The replay tooling in this framework depends on `t_pruned`
timestamps surviving long enough to be replayed.

## 5. The caveat that matters most in practice

The grace period is measured in valid time, not in sessions. MQuAKE-T runs one
session per day, so seven days and seven sessions coincide there. A production
assistant handling fifty sessions a day would traverse the same seven days in
three and a half hours, pruning far more aggressively in session terms than these
numbers suggest. A batch system ingesting monthly would barely prune at all.

Anyone porting this setting should convert it to their own cadence rather than
copying the number. The defensible general rule is to set the grace period to
roughly the window over which a user or auditor might still refer back to a
superseded value, expressed in wall-clock time, and then check what that implies
in sessions for the expected traffic.

## 6. What to say if asked to name one number

For the thesis, 7 days, unchanged, because it was fixed before results were
collected and the sweep shows the conclusions do not depend on it.

For a deployment, the honest answer is that this is the one parameter in the
framework that should not be inherited from the paper. Everything else was held
constant because it could not bias the comparison. This one encodes a policy
decision about how much history the application owes its users, and that decision
belongs to the application rather than to the retrieval curve.
