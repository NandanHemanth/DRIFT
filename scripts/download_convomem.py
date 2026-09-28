"""Convert ConvoMem's changing-facts split into DRIFT's dataset schema.

Why this benchmark
------------------
Threat 1 in Chapter 6 is that both real-data benchmarks are fact corpora rather
than natural conversation, so the extraction step is never a bottleneck for
contradiction detection. ConvoMem (Salesforce, arXiv:2511.10523, Apache 2.0) is
natural multi-turn dialogue in which the evidence is embedded inside ordinary
conversation, which is exactly the regime that threat describes.

Its `changing_evidence` split is built as supersession chains: a value is stated,
then revised, and the question asks for the current value. Each item ships the
ordered evidence messages, so the superseded value is recoverable from the data
itself rather than from an annotator.

How the superseded value is recovered
-------------------------------------
No LLM is used. An earlier attempt in this thesis to recover superseded values
with a language-model annotator on LongMemEval produced 1 usable annotation out
of 78, so this converter is deliberately deterministic:

  1. Take the first and last evidence message of an item, which bracket the
     change.
  2. Extract typed values from each (money, percentage, time, weekday, date,
     plain number) using fixed patterns.
  3. Keep a pair only when both messages contain the same value *type*, the two
     values differ, and the gold answer contains the new value while never
     containing the old one.

That last condition is the important one. It rejects items whose gold answer
narrates the change ("you initially set it for Tuesday, but it moved to Friday"),
because a substring-based staleness metric cannot distinguish that from a stale
answer. Roughly 14 percent of items survive, which is reported at the end of the
run in the same spirit as the benchmark audit in Chapter 4.

The filter biases the resulting set toward changes in dates, times and amounts,
and away from changes in names or entities. That is a real limitation and is
stated rather than hidden.

Usage:
    python scripts/download_convomem.py --questions 100
    python scripts/download_convomem.py --questions 100 --group-size 10
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

HF_API = "https://huggingface.co/api/datasets/Salesforce/ConvoMem"
HF_RAW = "https://huggingface.co/datasets/Salesforce/ConvoMem/resolve/main/"
SPLIT_PREFIX = "core_benchmark/evidence_questions/changing_evidence/"
DAY = 86400.0

# Typed value patterns, ordered most specific first. Only these types are
# considered recoverable; anything else is skipped rather than guessed at.
VALUE_PATTERNS = [
    ("money", r"\$\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?\b"),
    ("percent", r"\b\d+(?:\.\d+)?\s?%"),
    ("time", r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)\b"),
    ("weekday", r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"),
    ("date", r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b"),
    ("number", r"\b\d[\d,]*(?:\.\d+)?\b"),
]


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "drift-thesis"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def typed_values(text: str) -> list[tuple[str, str]]:
    out = []
    for name, pattern in VALUE_PATTERNS:
        for m in re.finditer(pattern, text):
            out.append((name, m.group(0).strip()))
    return out


def recover_supersession(item: dict) -> tuple[str, str] | None:
    """Return (stale_value, current_value) if it can be recovered cleanly."""
    evidence = item.get("message_evidences") or []
    if len(evidence) < 2:
        return None
    gold = (item.get("answer") or "").lower()
    if not gold:
        return None
    old_vals = typed_values(evidence[0].get("text", ""))
    new_vals = typed_values(evidence[-1].get("text", ""))
    for kind_a, old in old_vals:
        for kind_b, new in new_vals:
            if kind_a != kind_b or old.lower() == new.lower():
                continue
            # the gold answer must assert the new value and never mention the old
            if new.lower() in gold and old.lower() not in gold:
                return old, new
    return None


def item_sessions(item: dict, start: float) -> list[dict]:
    """One DRIFT session per ConvoMem conversation, spaced one day apart."""
    sessions = []
    for i, conv in enumerate(item.get("conversations", [])):
        lines = [f"{m.get('speaker', 'User')}: {m.get('text', '')}".strip()
                 for m in conv.get("messages", []) if m.get("text")]
        if lines:
            sessions.append({"time": start + i * DAY, "lines": lines})
    return sessions


def build(questions_wanted: int, group_size: int, verbose: bool) -> tuple[dict, dict]:
    listing = json.loads(fetch(HF_API))
    paths = sorted(s["rfilename"] for s in listing.get("siblings", [])
                   if s["rfilename"].startswith(SPLIT_PREFIX))
    if verbose:
        print(f"{len(paths)} files in the changing-facts split")

    stats = {"files_read": 0, "items_seen": 0, "chained": 0, "recovered": 0}
    usable: list[tuple[dict, tuple[str, str]]] = []

    for path in paths:
        if len(usable) >= questions_wanted:
            break
        try:
            payload = json.loads(fetch(HF_RAW + path))
        except Exception as exc:                      # network or malformed file
            if verbose:
                print(f"  skip {path}: {exc}")
            continue
        stats["files_read"] += 1
        for item in payload.get("evidence_items", []):
            stats["items_seen"] += 1
            if len(item.get("message_evidences") or []) >= 2:
                stats["chained"] += 1
            pair = recover_supersession(item)
            if pair and item.get("conversations"):
                stats["recovered"] += 1
                usable.append((item, pair))
                if len(usable) >= questions_wanted:
                    break
        if verbose and stats["files_read"] % 5 == 0:
            print(f"  read {stats['files_read']} files, {len(usable)} usable so far")

    # Group several items into one DRIFT conversation so the resulting memory
    # graph is comparable in size to MQuAKE-T (382 facts) rather than being a
    # handful of facts per question, which would make retrieval trivial.
    conversations = []
    for gi in range(0, len(usable), group_size):
        chunk = usable[gi:gi + group_size]
        sessions, questions, clock = [], [], 0.0
        for item, (stale, current) in chunk:
            new_sessions = item_sessions(item, clock)
            if not new_sessions:
                continue
            sessions.extend(new_sessions)
            clock = new_sessions[-1]["time"] + DAY
            questions.append({
                "question": item["question"],
                "answer": item["answer"],
                "stale_answer": stale,
                "category": "changing_fact",
            })
        if sessions and questions:
            conversations.append({
                "id": f"convomem_{gi // group_size:03d}",
                "sessions": sessions,
                "questions": questions,
            })

    return {"conversations": conversations}, stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert ConvoMem changing-facts to DRIFT schema")
    ap.add_argument("--questions", type=int, default=100,
                    help="target number of usable questions (default 100)")
    ap.add_argument("--group-size", type=int, default=10,
                    help="evidence items per DRIFT conversation (default 10)")
    ap.add_argument("--out", default="data/convomem_changing.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    dataset, stats = build(args.questions, args.group_size, not args.quiet)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset, indent=1))

    n_conv = len(dataset["conversations"])
    n_sess = sum(len(c["sessions"]) for c in dataset["conversations"])
    n_lines = sum(len(s["lines"]) for c in dataset["conversations"] for s in c["sessions"])
    n_q = sum(len(c["questions"]) for c in dataset["conversations"])
    yield_pct = 100.0 * stats["recovered"] / max(1, stats["items_seen"])

    print(f"\nWrote {out}")
    print(f"  conversations      {n_conv}")
    print(f"  sessions           {n_sess}")
    print(f"  dialogue lines     {n_lines}")
    print(f"  questions          {n_q}")
    print(f"  stale_answer cover 100% (recovered deterministically, by construction)")
    print("\nRecovery audit, reported in the spirit of the Chapter 4 benchmark audit:")
    print(f"  files read              {stats['files_read']}")
    print(f"  evidence items seen     {stats['items_seen']}")
    print(f"  with a supersession chain {stats['chained']}")
    print(f"  cleanly recoverable     {stats['recovered']}  ({yield_pct:.0f}% of items seen)")
    print("  the remainder are rejected because the value is not machine-extractable,")
    print("  or because the gold answer narrates the change and would defeat a")
    print("  substring-based staleness metric.")


if __name__ == "__main__":
    main()
