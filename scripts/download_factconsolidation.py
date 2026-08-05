"""Convert MemoryAgentBench's FactConsolidation split into DRIFT's schema.

MemoryAgentBench: Hu et al., "Evaluating Memory in LLM Agents via Incremental
Multi-Turn Interactions" (ICLR 2026), arXiv:2507.05257. MIT licensed.
https://huggingface.co/datasets/ai-hyz/MemoryAgentBench

Why this dataset
----------------
DRIFT's staleness metric needs questions annotated with the *superseded* answer
(`stale_answer`), and neither LoCoMo (0/300) nor LongMemEval (0/150) carries one.
FactConsolidation is built for exactly this: its context is a numbered fact list
in which later facts overwrite earlier ones on the same (subject, predicate), and
the gold answer is always the *latest* value. Verified on the 6k single-hop split:

    223. goaltender is associated with the sport of ice hockey.     <- superseded
    310. goaltender is associated with the sport of pesäpallo.      <- gold
    Q: Which sport is goaltender associated with?   A: pesäpallo

That makes `stale_answer` recoverable without an LLM annotator: it is the
previous value of whichever (subject, predicate) resolves to the gold answer.
122 of the 455 facts in the 6k split carry such a conflict.

Two further properties make it a better fit than the conversational benchmarks:

  * facts are already atomic `subject <relation> object` statements, so the
    contradiction DRIFT is designed to detect is present in the data rather than
    dependent on extractor luck;
  * the split ships four context lengths (6k / 32k / 64k / 262k tokens) over the
    same task, giving a built-in retrieval-pressure ablation.

Facts are grouped into synthetic sessions so they arrive incrementally with
advancing timestamps -- without that, every fact would share one valid-time and
neither TTL decay (P1) nor contradiction windows (P2) would have anything to act
on.

Usage:
    python scripts/download_factconsolidation.py                 # 6k, single-hop
    python scripts/download_factconsolidation.py --context 32k
    python scripts/download_factconsolidation.py --hop mh        # multi-hop
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Read rows over the HF datasets-server JSON API rather than the parquet file.
# DRIFT's core is stdlib-only (pyproject.toml: dependencies = []), and pulling in
# pyarrow just to read eight rows would break that for every user of the repo.
ROWS_API = "https://datasets-server.huggingface.co/rows"
HF_DATASET = "ai-hyz/MemoryAgentBench"
HF_SPLIT = "Conflict_Resolution"


def fetch_row(offset: int, timeout: int = 180) -> dict | None:
    """One row of the Conflict_Resolution split, or None past the end."""
    q = urllib.parse.urlencode({"dataset": HF_DATASET, "config": "default",
                                "split": HF_SPLIT, "offset": offset, "length": 1})
    with urllib.request.urlopen(f"{ROWS_API}?{q}", timeout=timeout) as resp:
        payload = json.loads(resp.read())
    rows = payload.get("rows") or []
    if not rows:
        return None
    if rows[0].get("truncated_cells"):
        raise SystemExit(
            f"row {offset} came back truncated ({rows[0]['truncated_cells']}). "
            "The API caps very large cells; use a smaller --context.")
    return rows[0]["row"]


def split_name(row: dict) -> str:
    ids = (row.get("metadata") or {}).get("qa_pair_ids") or [""]
    return str(ids[0]).rsplit("_no", 1)[0]


def find_split(want: str, max_rows: int = 16) -> dict:
    """Scan rows for the requested split, fetching one at a time so the huge
    262k-token rows are never downloaded unless they are the one asked for."""
    seen = []
    for offset in range(max_rows):
        row = fetch_row(offset)
        if row is None:
            break
        name = split_name(row)
        seen.append(name)
        if name == want:
            return row
    raise SystemExit(f"no split matching {want!r}. available: {sorted(set(seen))}")

# Connectors that separate subject from object in FactConsolidation statements.
# Ordered longest-first so "is located in the continent of" wins over " is ".
CONNECTORS = [
    " is associated with the sport of ",
    " is located in the continent of ",
    " was created in the country of ",
    " plays the position of ",
    " was born in the city of ",
    " died in the city of ",
    " is a citizen of ",
    " is married to ",
    " worked in the city of ",
    " is famous for ",
    " is ",
]

FACT_RE = re.compile(r"^\s*(\d+)\.\s+(.*?)\.?\s*$")


def split_fact(body: str) -> tuple[str, str, str] | None:
    """'Rogério Ceni plays the position of goalkeeper' -> (subj, pred, obj)."""
    for conn in CONNECTORS:
        if conn in body:
            subj, obj = body.split(conn, 1)
            return subj.strip(), conn.strip(), obj.strip()
    return None


def parse_context(context: str) -> list[tuple[int, str, str, str, str]]:
    """-> [(index, subject, predicate, object, surface_text)] in stated order."""
    out = []
    for line in context.splitlines():
        m = FACT_RE.match(line)
        if not m:
            continue
        idx, body = int(m.group(1)), m.group(2).strip()
        parts = split_fact(body)
        if parts:
            out.append((idx, parts[0], parts[1], parts[2], body))
    return out


def build_stale_map(facts: list[tuple[int, str, str, str, str]]) -> dict[str, str]:
    """Map a *superseding* object value -> the value it replaced.

    Keyed on the winning value (lowercased) because that is what the gold answer
    contains; the question text itself never has to be parsed.
    """
    history: dict[tuple[str, str], list[str]] = defaultdict(list)
    for _, subj, pred, obj, _ in facts:
        history[(subj.lower(), pred.lower())].append(obj)
    stale: dict[str, str] = {}
    for values in history.values():
        for prev, cur in zip(values, values[1:]):
            if prev.strip().lower() != cur.strip().lower():
                stale[cur.strip().lower()] = prev.strip()
    return stale


def convert(row: dict, facts_per_session: int, day_step: float) -> dict:
    facts = parse_context(row["context"])
    stale_map = build_stale_map(facts)

    base = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    sessions = []
    for i in range(0, len(facts), facts_per_session):
        chunk = facts[i:i + facts_per_session]
        sessions.append({
            "time": base + (i // facts_per_session) * day_step * 86400,
            "lines": [f"user: {text}." for _, _, _, _, text in chunk],
        })

    questions = []
    for q, a in zip(row["questions"], row["answers"]):
        gold = a[0] if isinstance(a, (list, tuple)) and a else str(a)
        questions.append({
            "question": q,
            "answer": str(gold),
            "category": "knowledge_update",
            "stale_answer": stale_map.get(str(gold).strip().lower()),
        })

    return {"id": str((row.get("metadata") or {}).get("qa_pair_ids", ["fc"])[0]).rsplit("_no", 1)[0],
            "sessions": sessions, "questions": questions}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", default="6k", choices=["6k", "32k", "64k", "262k"],
                    help="haystack size -- the built-in retrieval-pressure ablation")
    ap.add_argument("--hop", default="sh", choices=["sh", "mh"],
                    help="sh = single-hop (direct lookup), mh = multi-hop")
    ap.add_argument("--facts-per-session", type=int, default=10)
    ap.add_argument("--day-step", type=float, default=1.0,
                    help="simulated days between sessions (sets the valid-time spacing "
                         "that P1's TTL and P2's grace window operate over)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = Path(args.out or f"data/factconsolidation_{args.hop}_{args.context}.json")

    want = f"factconsolidation_{args.hop}_{args.context}"
    print(f"Fetching {HF_DATASET} [{HF_SPLIT}] -> {want} ...")
    row = find_split(want)

    convo = convert(row, args.facts_per_session, args.day_step)
    dataset = {"name": want, "conversations": [convo]}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset))

    qs = convo["questions"]
    n_stale = sum(1 for q in qs if q["stale_answer"])
    print(f"Wrote {out}: {len(convo['sessions'])} sessions, {len(qs)} questions, "
          f"{n_stale} with stale_answer ({n_stale / max(1, len(qs)) * 100:.0f}%)")
    for q in [q for q in qs if q["stale_answer"]][:5]:
        print(f"   gold={q['answer'][:34]:<34} stale={q['stale_answer']}")


if __name__ == "__main__":
    main()
