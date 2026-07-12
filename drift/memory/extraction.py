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


def extract_facts(provider, session_lines: list[str]) -> list[dict]:
    """Extract facts from a list of 'Speaker: utterance' lines."""
    text = "\n".join(session_lines)
    completion = provider.complete(EXTRACTION_PROMPT.format(text=text), system=EXTRACTION_SYSTEM)
    try:
        raw = json.loads(completion.text)
        assert isinstance(raw, list)
    except (json.JSONDecodeError, AssertionError):
        m = re.search(r"\[.*\]", completion.text, re.S)
        raw = json.loads(m.group(0)) if m else []

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
