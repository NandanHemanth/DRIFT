# Front matter draft: abstract, dedication, acknowledgments

These three pieces live inside `titlepg.sty`, in the `\thesisabstract`, `\thesisdedicationpage`, and `\thesisacknowledgments` commands, which is the file you said you would edit yourself. This note gives you the content to paste in; it does not touch `titlepg.sty` directly.

## Abstract (345 words, under the 350-word limit)

Paste this in place of the sample paragraphs inside `\thesisabstract`, above the `Author / Advisor / Date / Department / Degree` block that must stay at the end.

```
Long-lived language model agents accumulate memories that go stale. A fact true
when written is later superseded, but retrieval keeps surfacing the old value,
and the agent answers from a fact that no longer holds. Research on agent
memory has concentrated on storage and retrieval; the rule deciding what
memory discards has been treated as an implementation detail rather than as an
object of study.

This thesis isolates that rule. DRIFT holds a bitemporal knowledge graph
substrate, the fact extraction step, the retrieval function, the answer model,
and the evaluation judge fixed, and varies only the forgetting policy across
seven conditions spanning a no-memory floor, an append-only baseline, and five
forgetting strategies drawn from current systems. The framework is evaluated
on two public benchmarks that annotate the superseded answer, an annotation
the staleness metric requires and that the two most widely used agent-memory
benchmarks do not provide.

Four findings replicate across both benchmarks. Append-only memory measurably
surfaces superseded facts, with staleness confidence intervals excluding zero.
Bitemporal contradiction invalidation is statistically equivalent to the
accuracy ceiling, bounded within roughly two to two and a half points on both
benchmarks, while spending twelve percent fewer tokens per question and
storing six and a half to fifteen percent fewer facts. Novelty-gated writing,
a popular efficiency technique, increases staleness by eleven to thirteen
points, because a correction is textually near-identical to the fact it
corrects and is rejected as a duplicate, so it never enters memory.
Structure-aware but time-blind consolidation performs significantly worse
than bitemporal consolidation on real-world knowledge updates, attributing
the advantage to bitemporal semantics specifically rather than to graph
structure in general.

Two methodological results accompany these findings: a configuration
ablation quantifying how much of the reported efficiency depends on
correctly declaring a domain's functional predicates, and a
judge-reliability audit identifying a twelve-and-a-half-point accuracy
artifact produced by a rotating judge pool on byte-identical answers.

The framework is released as a dependency-free, offline-verifiable Python
package with a five-line integration surface, so the central question, which
forgetting policy suits a given workload, can be answered empirically rather
than assumed.
```

If your program requires a different framing (for example, more emphasis on the practitioner recommendation, or a stronger opening sentence naming DRIFT immediately), trim from the fourth paragraph first: the two methodological results are the most compressible without losing a claim, since both are described again in full in Chapter 5.

## Dedication (optional, personal, your call)

The template's sample text is a placeholder ("This thesis is dedicated to all Stevens students"). A dedication is optional and belongs to you rather than to the content of the thesis, so no draft is offered here beyond a plain, neutral fallback if you would rather not write one:

```
To my family.
```

If you would rather omit the dedication page entirely, delete the `\thesisdedicationpage` call and its `\addcontentsline` line from `stevensDissertation.tex`, in the front-matter block right after `\thesisabstract`.

## Acknowledgments (draft, adjust freely)

```
I am grateful to my advisor, Professor Hao Wang, for guidance throughout this
research and for his continued involvement as a co-author on the resulting
paper. I thank the Department of Computer Science at Stevens Institute of
Technology for the resources that made this work possible. [Add any lab,
funding source, or personal acknowledgment you want included here.]
```

Replace the bracketed sentence, or remove it, as appropriate. This section is read by almost nobody in a formal capacity, so there is no length limit and no wrong way to write it beyond keeping it sincere.
