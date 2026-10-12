"""Ingestion, answering, and judging pipeline."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from drift.memory.extraction import extract_facts
from drift.memory.graph import BitemporalGraph, Fact
from drift.policies import Policy
from drift.providers import BaseProvider, Completion

# The system prompt states what the date prefix *is* and stops there. It must not
# tell the model how to resolve a conflict between two facts, because resolving
# conflicts is precisely what the forgetting policy under test is supposed to do.
# An earlier version added "prefer the most recent fact when two disagree" and
# explained the [superseded] marker; that handed P2's mechanism to every policy,
# so P0 (never forgets) stopped producing stale answers and the independent
# variable was no longer the policy.
ANSWER_SYSTEM = (
    "You are an assistant with long-term memory. Answer the question using ONLY the "
    "memory facts provided. Answer concisely. If memory does not contain the answer, "
    "say \"I don't know.\"\n"
    "Each memory line begins with [YYYY-MM-DD]: the date that fact became true."
)

ANSWER_PROMPT = """MEMORY:
{memory}
QUESTION:
{question}
"""

JUDGE_SYSTEM = "You grade an answer against a gold reference. Reply with exactly CORRECT or INCORRECT."

JUDGE_PROMPT = """TASK:JUDGE
QUESTION:
{question}
GOLD:
{gold}
ANSWER:
{answer}
"""


def ingest_session(session: dict, graph: BitemporalGraph, policy: Policy,
                   extractor_provider: BaseProvider,
                   maintenance_provider: BaseProvider | None = None) -> dict:
    """Ingest one session: extract facts, apply write gate, add to graph, run maintenance.

    session = {"time": epoch_seconds, "lines": ["Alice: ...", ...],
               "provenance": "conversation" (optional)}
    Returns token accounting for the session.
    """
    facts = extract_facts(extractor_provider, session["lines"])
    written = 0
    for f in facts:
        if policy.on_write(f, graph):
            graph.add_fact(f["subject"], f["predicate"], f["object"], f["text"],
                           t_event=session["time"],
                           provenance=session.get("provenance", "conversation"))
            written += 1
    # Policies that call a model during maintenance (P4 merges facts with an LLM)
    # use maintenance_provider when given. Pinning it keeps the policy identical
    # across answer models; when its provider once changed, P4 went from pruning
    # 8 facts to 172 on the same data.
    policy.after_session(graph, maintenance_provider or extractor_provider, now=session["time"])
    return {"extracted": len(facts), "written": written}


def _fmt_date(ts: float) -> str:
    """Epoch seconds -> YYYY-MM-DD. Returns '' for the sentinel 0 timestamp used
    by synthetic datasets whose sessions carry relative rather than real times."""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return ""


def render_fact(f: Fact, show_supersession: bool = False) -> str:
    """Render one fact for the answer prompt.

    The valid-time start date is included: it is ordinary memory metadata that
    any memory system has, and without it "when did X happen" is unanswerable by
    construction (LoCoMo temporal accuracy was 0.042, 2 of 48).

    The supersession marker is NOT included by default. `t_invalid_at` is the
    output of contradiction detection, and acting on it is exactly what P2 does;
    printing it for every policy gives P0 P2's mechanism for free and collapses
    the comparison. `show_supersession=True` is available so that "tell the model
    which facts are stale" can be run deliberately as its own ablation, rather
    than silently becoming part of the substrate.
    """
    start = _fmt_date(f.t_valid_start)
    head = f"[{start}]" if start else ""
    if show_supersession and f.invalidated:
        end = _fmt_date(f.t_invalid_at or 0.0)
        head += f" [superseded {end}]" if end else " [superseded]"
    return f"{head} {f.text}".strip()


_THINK = re.compile(r"<think>.*?</think>", re.S)


def answer_question(question: str, graph: BitemporalGraph, policy: Policy,
                    provider: BaseProvider, k: int = 8, now: float | None = None,
                    show_supersession: bool = False, max_tokens: int = 1024) -> dict:
    retrieved = graph.search(question, k=k, now=now)
    retrieved = policy.on_retrieve(retrieved, now=now or 0.0)
    memory_block = "\n".join(render_fact(f, show_supersession) for f in retrieved) \
        or "(no relevant memory)"
    completion: Completion = provider.complete(
        ANSWER_PROMPT.format(memory=memory_block, question=question), system=ANSWER_SYSTEM,
        max_tokens=max_tokens,
    )
    return {
        "question": question,
        # a reasoning model's visible <think> block is not part of the answer
        "answer": _THINK.sub("", completion.text).strip(),
        "retrieved_ids": [f.id for f in retrieved],
        "retrieved_invalidated": sum(1 for f in retrieved if f.invalidated),
        "tokens": completion.total_tokens,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
    }


def judge_answer(question: str, gold: str, answer: str, judge_provider: BaseProvider,
                 max_tokens: int = 1024) -> dict:
    completion = judge_provider.complete(
        JUDGE_PROMPT.format(question=question, gold=gold, answer=answer), system=JUDGE_SYSTEM,
        max_tokens=max_tokens,
    )
    verdict = "CORRECT" in completion.text.upper() and "INCORRECT" not in completion.text.upper()
    return {"correct": verdict, "f1": token_f1(gold, answer), "judge_tokens": completion.total_tokens}


def token_f1(gold: str, answer: str) -> float:
    g = re.findall(r"[a-z0-9]+", gold.lower())
    a = re.findall(r"[a-z0-9]+", answer.lower())
    if not g or not a:
        return 0.0
    common = {}
    for t in set(g):
        common[t] = min(g.count(t), a.count(t))
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(a)
    recall = overlap / len(g)
    return 2 * precision * recall / (precision + recall)
