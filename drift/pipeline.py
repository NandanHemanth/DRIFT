"""Ingestion, answering, and judging pipeline."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from drift.memory.extraction import extract_facts
from drift.memory.graph import BitemporalGraph, Fact
from drift.policies import Policy
from drift.providers import BaseProvider, Completion

ANSWER_SYSTEM = (
    "You are an assistant with long-term memory. Answer the question using ONLY the "
    "memory facts provided. Answer concisely. If memory does not contain the answer, "
    "say \"I don't know.\"\n"
    "Each memory line begins with [YYYY-MM-DD]: the date that fact became true. Use those "
    "dates to answer questions about when something happened, and prefer the most recent "
    "fact when two disagree. A line marked [superseded YYYY-MM-DD] was true until that date "
    "and is no longer current."
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
                   extractor_provider: BaseProvider) -> dict:
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
    policy.after_session(graph, extractor_provider, now=session["time"])
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


def render_fact(f: Fact) -> str:
    """Render one fact for the answer prompt, surfacing its bitemporal fields.

    The substrate stores valid-time (t_valid_start / t_invalid_at) on every fact,
    but before this the prompt only carried f.text -- so the answer model could
    never resolve "when did X happen", and could not tell a superseded fact from
    a current one except by whatever the policy had already filtered out. Both
    are the substrate's core signal; they belong in the prompt.
    """
    start = _fmt_date(f.t_valid_start)
    head = f"[{start}]" if start else ""
    if f.invalidated:
        end = _fmt_date(f.t_invalid_at or 0.0)
        head += f" [superseded {end}]" if end else " [superseded]"
    return f"{head} {f.text}".strip()


def answer_question(question: str, graph: BitemporalGraph, policy: Policy,
                    provider: BaseProvider, k: int = 8, now: float | None = None) -> dict:
    retrieved = graph.search(question, k=k, now=now)
    retrieved = policy.on_retrieve(retrieved, now=now or 0.0)
    memory_block = "\n".join(render_fact(f) for f in retrieved) or "(no relevant memory)"
    completion: Completion = provider.complete(
        ANSWER_PROMPT.format(memory=memory_block, question=question), system=ANSWER_SYSTEM
    )
    return {
        "question": question,
        "answer": completion.text.strip(),
        "retrieved_ids": [f.id for f in retrieved],
        "retrieved_invalidated": sum(1 for f in retrieved if f.invalidated),
        "tokens": completion.total_tokens,
    }


def judge_answer(question: str, gold: str, answer: str, judge_provider: BaseProvider) -> dict:
    completion = judge_provider.complete(
        JUDGE_PROMPT.format(question=question, gold=gold, answer=answer), system=JUDGE_SYSTEM
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
