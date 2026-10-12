"""Relation normalisation for contradiction detection.

Why this exists
---------------
P2 notices that a new fact supersedes an old one only when both are stored
under the same (subject, relation). With one extraction model that holds, because
one model names things consistently. It fails in two measured cases:

1. Several writers (RQ4 pilot). Five extraction models wrote the same relation
   as `head_of_government` (28 times), `is_head_of_government_of` (9) and
   `head_of_government_of` (7). P2 recorded zero invalidations.
2. Natural dialogue (ConvoMem). Lists such as meetings or deliverables were
   treated as single-valued under functional_predicates = "*", so each new
   meeting "superseded" the last: about 10 of 17 audited invalidations were wrong.

This module gives contradiction detection a normalised key instead of the raw
strings, and a guard for relations that hold several values at once. It is
deliberately simple and deterministic (token rules, plus an optional embedding
check for relation names) so its behaviour can be stated exactly in the thesis.
Exact matching remains the default; normalisation is switched on by config, so
both can be reported and compared.
"""
from __future__ import annotations

import re
from functools import lru_cache

# Words that carry no relation meaning: copulas, articles, prepositions.
_RELATION_STOP = {
    "is", "are", "was", "were", "be", "been", "has", "have", "had", "the", "a", "an",
    "of", "in", "at", "to", "for", "on", "by", "with", "as", "current", "currently",
    "now", "new", "official", "officially",
}
_ENTITY_STOP = {"the", "a", "an"}

# Relations that normally hold several values at once. A new value adds to the
# list instead of replacing it, so they must not trigger contradiction even when
# every predicate is declared functional ("*"). "appointment" is deliberately
# absent: the one real update in the ConvoMem audit was a rescheduled appointment.
MULTI_VALUED_HINTS = {
    "meeting", "meetings", "deliverable", "deliverables", "reminder", "reminders",
    "task", "tasks", "event", "events", "friend", "friends", "member", "members",
    "likes", "enjoys", "hobby", "hobbies", "manages", "attends", "attended",
    "visited", "skill", "skills", "colleague", "colleagues",
}

_SUFFIXES = ("ship", "hood", "ness")


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower().replace("_", " ").replace("-", " "))


def _stem(tok: str) -> str:
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            return tok[: -len(suf)]
    if tok.endswith("s") and not tok.endswith("ss") and len(tok) > 4:
        return tok[:-1]
    return tok


@lru_cache(maxsize=65536)
def relation_key(predicate: str) -> str:
    """'is_head_of_government_of' and 'head_of_government' -> 'government head'."""
    toks = [_stem(t) for t in _tokens(predicate) if t not in _RELATION_STOP]
    return " ".join(sorted(set(toks))) or predicate.strip().lower()


@lru_cache(maxsize=65536)
def entity_key(subject: str) -> str:
    """'The_Apex Digital' and 'apex digital' -> 'apex digital'."""
    toks = [t for t in _tokens(subject) if t not in _ENTITY_STOP]
    return " ".join(toks) or subject.strip().lower()


def is_multi_valued(predicate: str, hints: set[str] | None = None) -> bool:
    hints = MULTI_VALUED_HINTS if hints is None else hints
    return any(t in hints for t in _tokens(predicate))


# ---------------------------------------------------------------- LLM judge
#
# Name rules cannot fix the multi-writer case completely, because writers also
# flip direction: one stores `Italy | head_of_government | Giuseppe Conte`,
# another `Giorgia Meloni | head_of_government | Italy`. Whether Italy or the
# person is the side with one value at a time is world knowledge, not syntax.
# The "llm" mode therefore shows a fixed model the new fact and the few stored
# facts that mention the same entities, and asks which ones the new fact makes
# no longer true. This is the approach Zep/Graphiti takes for edge invalidation.

CONTRADICT_PROMPT = """TASK:CONTRADICT
A memory stores facts. A NEW fact has just been learned. Decide which EXISTING
facts the new fact makes no longer true (it replaces them: a new holder of the
same single-valued role, a changed date, time, place or number for the same
thing). Facts that can be true at the same time (lists, several meetings,
several citizens of a country) are NOT replaced.

NEW: {new}

EXISTING:
{existing}

Answer with the numbers of the replaced facts separated by commas, or NONE."""


def make_llm_judge(provider, max_candidates: int = 8):
    """Return judge(new_fact, candidates) -> list of candidate facts to close."""

    def judge(new, candidates):
        if not candidates:
            return []
        cands = candidates[:max_candidates]
        listing = "\n".join(f"[{i + 1}] {c.text}  ({c.subject} | {c.predicate} | {c.object})"
                            for i, c in enumerate(cands))
        prompt = CONTRADICT_PROMPT.format(
            new=f"{new.text}  ({new.subject} | {new.predicate} | {new.object})", existing=listing)
        try:
            out = provider.complete(prompt, max_tokens=64).text
        except Exception:  # noqa: BLE001 - a failed judgement means "close nothing"
            return []
        if "none" in out.lower()[:20]:
            return []
        picked = {int(n) for n in re.findall(r"\d+", out)}
        return [c for i, c in enumerate(cands, 1) if i in picked]

    return judge
