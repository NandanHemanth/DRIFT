"""Download LoCoMo and convert it into DRIFT's dataset schema.

LoCoMo: Maharana et al., "Evaluating Very Long-Term Conversational Memory of
LLM Agents" (ACL 2024). Data: https://github.com/snap-research/locomo

Usage:
    python scripts/download_locomo.py            # downloads + converts
    python scripts/download_locomo.py --in locomo10.json   # convert local copy
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

LOCOMO_URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"

# LoCoMo QA categories: 1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop, 5 adversarial
CATEGORY_MAP = {1: "multi_hop", 2: "temporal", 3: "open_domain", 4: "single_hop", 5: "adversarial"}


def parse_session_time(ts: str) -> float:
    """LoCoMo session timestamps look like '1:56 pm on 8 May, 2023'."""
    try:
        part = ts.split(" on ", 1)[-1].strip()
        return datetime.strptime(part, "%d %B, %Y").timestamp()
    except (ValueError, IndexError):
        return time.time()


def convert(raw: list[dict], max_conversations: int | None = None) -> dict:
    conversations = []
    for sample in raw[: max_conversations or len(raw)]:
        convo = sample.get("conversation", {})
        sessions = []
        idx = 1
        while f"session_{idx}" in convo:
            turns = convo[f"session_{idx}"]
            ts = parse_session_time(convo.get(f"session_{idx}_date_time", ""))
            lines = [f"{t['speaker']}: {t['text']}" for t in turns if t.get("text")]
            if lines:
                sessions.append({"time": ts, "lines": lines})
            idx += 1
        questions = []
        for qa in sample.get("qa", []):
            answer = qa.get("answer") or qa.get("adversarial_answer") or ""
            questions.append({
                "question": qa["question"],
                "answer": str(answer),
                "category": CATEGORY_MAP.get(qa.get("category", 4), "single_hop"),
                "stale_answer": None,
            })
        conversations.append({
            "id": sample.get("sample_id", f"locomo_{len(conversations)}"),
            "sessions": sessions,
            "questions": questions,
        })
    return {"name": "locomo", "conversations": conversations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", default=None, help="local locomo10.json (skips download)")
    parser.add_argument("--out", default="data/locomo_drift.json")
    parser.add_argument("--max-conversations", type=int, default=None)
    args = parser.parse_args()

    if args.infile:
        raw = json.loads(Path(args.infile).read_text())
    else:
        print(f"Downloading {LOCOMO_URL} ...")
        with urllib.request.urlopen(LOCOMO_URL, timeout=120) as resp:
            raw = json.loads(resp.read())

    dataset = convert(raw, args.max_conversations)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset))
    n_q = sum(len(c["questions"]) for c in dataset["conversations"])
    print(f"Wrote {out}: {len(dataset['conversations'])} conversations, {n_q} questions")


if __name__ == "__main__":
    main()
