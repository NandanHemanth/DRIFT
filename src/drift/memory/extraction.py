"""Fact extraction from conversation turns.

LLM path: structured triple extraction with predicate normalization.
The MockProvider implements the same contract offline (see providers.py).
"""
from __future__ import annotations

import json
import re

EXTRACTION_SYSTEM = (
    "You extract atomic facts from conversation turns as JSON. "
    "Use snake_case predicates. For facts about a person's current state "
    "(home city, employer, job, relationship_status, pets, studies), use these exact predicates: "
    "lives_in, works_at, job, relationship_status, owns_pet, studies. "
    "Return ONLY a JSON list of {subject, predicate, object, text} objects."
)

EXTRACTION_PROMPT = """TASK:EXTRACT
Extract atomic facts from the conversation snippet below.
TEXT:
{text}
"""

PREDICATE_HINTS = [
    (re.compile(r"\b(?:i|he|she|they)\s+(?:just\s+)?moved to\s+(?P<obj>[A-Z][\w\s]+?)(?:[.,!]|$)", re.I), "lives_in"),
    (re.compile(r"\blives? in\s+(?P<obj>[A-Z][\w\s]+?)(?:[.,!]|$)", re.I), "lives_in"),
    (re.compile(r"\b(?:work(?:s|ing)? (?:at|for)|joined)\s+(?P<obj>[A-Z][\w\s]+?)(?:\s+as\b|[.,!]|$)", re.I), "works_at"),
    (re.compile(r"\badopted a\s+(?P<obj>\w+)", re.I), "owns_pet"),
    (re.compile(r"\bstudy(?:ing)?\s+(?P<obj>[\w\s]+?)(?:\s+at\b|[.,!]|$)", re.I), "studies"),
]


def _heuristic_upgrade(speaker: str, line: str) -> list[dict]:
    """Regex pass that recovers functional predicates from a raw utterance.

    Applied on top of any extractor so that contradiction detection
    (same subject+predicate, new object) has structured predicates to work with.
    """
    out = []
    for pattern, predicate in PREDICATE_HINTS:
        m = pattern.search(line)
        if m:
            out.append({
                "subject": speaker, "predicate": predicate,
                "object": m.group("obj").strip(), "text": f"{speaker}: {line}",
            })
    return out


# Token budget for a second extraction attempt when the first reply contains no
# parseable fact list. None keeps the published behaviour (no retry). Reasoning
# models given the default 1,024 tokens sometimes spend all of it thinking and
# return a truncated thought instead of JSON; on ConvoMem that silently emptied
# about a fifth of the sessions. The runner sets this from the config key
# "extract_retry_tokens". Sessions that parsed the first time are untouched, so
# their cached extraction is reused exactly.
RETRY_MAX_TOKENS: int | None = None
FAILED_PARSES = {"first": 0, "after_retry": 0}


def _parse_list(text: str):
    """The JSON fact list in a reply, or None if there is none to be had."""
    try:
        raw = json.loads(text)
        if isinstance(raw, list):
            return raw
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, list) else None


def extract_facts(provider, session_lines: list[str]) -> list[dict]:
    """Extract facts from a list of 'Speaker: utterance' lines."""
    text = "\n".join(session_lines)
    prompt = EXTRACTION_PROMPT.format(text=text)
    completion = provider.complete(prompt, system=EXTRACTION_SYSTEM)
    raw = _parse_list(completion.text)
    if raw is None:
        FAILED_PARSES["first"] += 1
        if RETRY_MAX_TOKENS:
            retry = provider.complete(prompt, system=EXTRACTION_SYSTEM, max_tokens=RETRY_MAX_TOKENS)
            raw = _parse_list(retry.text)
            if raw is None:
                FAILED_PARSES["after_retry"] += 1
    # Still malformed: treat as "no facts this session" rather than crash the run.
    raw = raw or []

    facts: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or "object" not in item:
            continue
        facts.append({
            "subject": str(item.get("subject", "unknown")),
            "predicate": str(item.get("predicate", "stated")).strip().lower().replace(" ", "_"),
            "object": str(item["object"]),
            "text": str(item.get("text", item["object"])),
        })

    # Regex upgrade pass: add structured functional facts the extractor missed.
    seen = {(f["subject"].lower(), f["predicate"], f["object"].lower()) for f in facts}
    for line in session_lines:
        if ":" not in line:
            continue
        speaker, utterance = (s.strip() for s in line.split(":", 1))
        for f in _heuristic_upgrade(speaker, utterance):
            key = (f["subject"].lower(), f["predicate"], f["object"].lower())
            if key not in seen:
                facts.append(f)
                seen.add(key)

    # If a line yielded a structured functional fact, drop the generic 'stated'
    # duplicate of the same line so contradiction handling governs that content.
    functional_texts = {f["text"] for f in facts if f["predicate"] != "stated"}
    facts = [f for f in facts if not (f["predicate"] == "stated" and f["text"] in functional_texts)]
    return facts
