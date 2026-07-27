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
import random
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


def stratified_sample(dataset: dict, sample_size: int, seed: int = 42) -> dict:
    """Cap total questions while keeping every conversation's full session
    history intact (long-horizon dynamics are the point of LoCoMo; only the
    QUESTION volume drives judge-call cost, so that is what we cap).

    Sampling is proportional to each question category's share of the full
    dataset and seeded for reproducibility. Conversations with zero sampled
    questions are dropped from the output (nothing to ingest-and-answer for),
    but every kept conversation retains ALL of its original sessions.
    """
    rng = random.Random(seed)
    all_q = [(ci, qi, q) for ci, c in enumerate(dataset["conversations"])
             for qi, q in enumerate(c["questions"])]
    by_cat: dict[str, list] = {}
    for item in all_q:
        by_cat.setdefault(item[2]["category"], []).append(item)

    total = len(all_q)
    keep_keys: set[tuple[int, int]] = set()
    for cat, items in by_cat.items():
        target = max(1, round(sample_size * len(items) / total))
        rng.shuffle(items)
        for ci, qi, _ in items[:target]:
            keep_keys.add((ci, qi))

    sampled_conversations = []
    for ci, convo in enumerate(dataset["conversations"]):
        kept_qs = [q for qi, q in enumerate(convo["questions"]) if (ci, qi) in keep_keys]
        if kept_qs:
            sampled_conversations.append({**convo, "questions": kept_qs})
    return {**dataset, "name": dataset.get("name", "locomo") + "_sample",
            "conversations": sampled_conversations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", default=None,
                        help="local locomo10.json (raw) OR an already-converted "
                             "DRIFT-schema file (e.g. data/locomo_drift.json) to "
                             "re-sample without re-downloading/re-converting")
    parser.add_argument("--out", default="data/locomo_drift.json")
    parser.add_argument("--max-conversations", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=None,
                        help="cap total questions (stratified across categories, "
                             "full session histories kept) to fit free-tier judge "
                             "quotas; e.g. --sample-size 300")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.infile:
        raw = json.loads(Path(args.infile).read_text())
    else:
        print(f"Downloading {LOCOMO_URL} ...")
        with urllib.request.urlopen(LOCOMO_URL, timeout=120) as resp:
            raw = json.loads(resp.read())

    if isinstance(raw, dict) and "conversations" in raw:
        dataset = raw  # already DRIFT-schema (e.g. re-sampling data/locomo_drift.json)
    else:
        dataset = convert(raw, args.max_conversations)
    if args.sample_size:
        dataset = stratified_sample(dataset, args.sample_size, args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset))
    n_q = sum(len(c["questions"]) for c in dataset["conversations"])
    cats: dict[str, int] = {}
    for c in dataset["conversations"]:
        for q in c["questions"]:
            cats[q["category"]] = cats.get(q["category"], 0) + 1
    print(f"Wrote {out}: {len(dataset['conversations'])} conversations, {n_q} questions; "
          f"categories: {cats}")


if __name__ == "__main__":
    main()
