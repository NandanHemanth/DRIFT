"""Add a short `current_answer` to every question that has a `stale_answer`.

The staleness metric asks whether an answer asserts the superseded value. A
model that explains itself ("Meloni is the current head; she replaced Conte")
mentions the old value while answering correctly, so a plain "contains the old
string" test counts it as stale. In the pilot that inflated Claude Sonnet 5.5's
staleness on MQuAKE-T from 1 real case to 75. The fix needs the current value in
a short form to check for alongside the old one.

MQuAKE-T and FactConsolidation golds are already short values. ConvoMem golds
are sentences ("The call is scheduled for 10 AM."), so the current value is the
typed value in the gold of the same type as the stale value, recovered with the
same fixed patterns the ConvoMem converter used. No language model is involved.

Usage:
    python scripts/add_current_answer.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["data/mquake_t_sh.json", "data/factconsolidation_sh_6k.json", "data/convomem_changing.json"]
PATTERNS = [
    ("money", r"\$\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?\b"),
    ("percent", r"\b\d+(?:\.\d+)?\s?%"),
    ("time", r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)\b"),
    ("weekday", r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"),
    ("date", r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b"),
    ("number", r"\b\d[\d,]*(?:\.\d+)?\b"),
]


def kind(value: str) -> str | None:
    for name, p in PATTERNS:
        if re.fullmatch(p, value.strip()):
            return name
    return None


def current_value(gold: str, stale: str) -> str | None:
    """The short current value: the gold itself when it is a bare value, else the
    typed value in the gold sentence of the same type as the stale value (for
    numbers, preferring the same number of digits, so a changed phone suffix
    1234 -> 5678 is matched rather than the unchanged area code)."""
    k = kind(stale)
    if not k or len(gold.split()) <= 3:
        return gold
    cands = [m.group(0).strip() for m in re.finditer(dict(PATTERNS)[k], gold)]
    cands = [v for v in cands if v.lower() != stale.lower()]
    if k == "number":
        same = [v for v in cands if len(re.sub(r"\D", "", v)) == len(re.sub(r"\D", "", stale))]
        cands = same or cands
    return cands[0] if cands else None


def main() -> None:
    for f in FILES:
        p = ROOT / f
        data = json.loads(p.read_text())
        n = got = 0
        for c in data["conversations"]:
            for q in c["questions"]:
                if q.get("stale_answer"):
                    n += 1
                    cur = current_value(q.get("answer", ""), q["stale_answer"])
                    if cur:
                        q["current_answer"] = cur
                        got += 1
        p.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        print(f"{f}: current value recovered for {got} of {n} questions with a superseded answer")


if __name__ == "__main__":
    main()
