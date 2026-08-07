"""Download LongMemEval and convert it into DRIFT's dataset schema.

LongMemEval: Wu et al., "LongMemEval: Benchmarking Chat Assistants on Long-Term
Interactive Memory" (ICLR 2025). https://github.com/xiaowu0162/LongMemEval

Why this dataset for DRIFT: its question types include *knowledge-update*
(the user's state changes across sessions - exactly the staleness setting)
and *temporal-reasoning*, giving cross-dataset validity beyond LoCoMo.

The 'oracle' variant contains only evidence sessions per question (small,
budget-friendly); 'longmemeval_s' adds ~40 distractor sessions per question
(the realistic retrieval stress test).

Usage:
    python scripts/download_longmemeval.py                       # oracle variant
    python scripts/download_longmemeval.py --variant s           # full small variant
    python scripts/download_longmemeval.py --in local_file.json  # convert local copy
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime
from pathlib import Path

HF_URL = "https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_{variant}"

# question_type -> DRIFT category. knowledge-update is the staleness-critical one.
CATEGORY_MAP = {
    "single-session-user": "single_hop",
    "single-session-assistant": "single_hop",
    "single-session-preference": "preference",
    "multi-session": "multi_hop",
    "knowledge-update": "knowledge_update",
    "temporal-reasoning": "temporal",
}


def parse_date(d: str) -> float:
    for fmt in ("%Y/%m/%d (%a) %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(d.strip(), fmt).timestamp()
        except ValueError:
            continue
    return 0.0


def convert(raw: list[dict], max_questions: int | None = None) -> dict:
    """One DRIFT 'conversation' per LongMemEval question: its haystack sessions
    (time-ordered) plus the single question. Abstention questions (id suffix
    '_abs') keep their gold answer so the judge can check refusal."""
    conversations = []
    for item in raw[: max_questions or len(raw)]:
        dates = item.get("haystack_dates", [])
        sess_raw = item.get("haystack_sessions", [])
        sessions = []
        for i, sess in enumerate(sess_raw):
            lines = []
            for turn in sess:
                role = turn.get("role", "user")
                text = (turn.get("content") or "").strip()
                if text:
                    lines.append(f"{role}: {text}")
            if lines:
                t = parse_date(dates[i]) if i < len(dates) else float(i * 86400)
                sessions.append({"time": t, "lines": lines})
        sessions.sort(key=lambda s: s["time"])
        qtype = item.get("question_type", "single-session-user")
        conversations.append({
            "id": str(item.get("question_id", f"lme_{len(conversations)}")),
            "sessions": sessions,
            "questions": [{
                "question": item["question"],
                "answer": str(item.get("answer", "")),
                "category": CATEGORY_MAP.get(qtype, "single_hop"),
                "stale_answer": None,
            }],
        })
    return {"name": "longmemeval", "conversations": conversations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="oracle", choices=["oracle", "s"],
                        help="oracle = evidence-only (budget-friendly); s = +distractors")
    parser.add_argument("--in", dest="infile", default=None)
    parser.add_argument("--out", default="data/longmemeval_drift.json")
    parser.add_argument("--max-questions", type=int, default=None,
                        help="cap for budget-limited runs (e.g. 100)")
    args = parser.parse_args()

    if args.infile:
        raw = json.loads(Path(args.infile).read_text())
    else:
        url = HF_URL.format(variant=args.variant)
        print(f"Downloading {url} ...")
        with urllib.request.urlopen(url, timeout=300) as resp:
            raw = json.loads(resp.read())

    dataset = convert(raw, args.max_questions)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset))
    cats: dict[str, int] = {}
    for c in dataset["conversations"]:
        for q in c["questions"]:
            cats[q["category"]] = cats.get(q["category"], 0) + 1
    print(f"Wrote {out}: {len(dataset['conversations'])} questions; categories: {cats}")


if __name__ == "__main__":
    main()
