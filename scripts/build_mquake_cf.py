"""Convert the complete MQuAKE-CF-3k-v2 multi-hop set into DRIFT's schema.

MQuAKE: Zhong et al., "MQuAKE: Assessing Knowledge Editing in Language Models via
Multi-Hop Questions" (EMNLP 2023), arXiv:2305.14795. MIT licensed.

What this builds
----------------
All 3,000 instances of MQuAKE-CF-3k-v2 (1,135 two-hop, 1,136 three-hop, 729
four-hop; 37 relation types; 2,764 distinct counterfactual edits; edits can sit
at any hop). v2 is the release in which edits never conflict with each other or
with any unedited fact, which this script checks before writing anything.

One memory cannot hold all of it: the whole edited world is about 7,600 fact
lines, twenty times the single-hop benchmarks, and retrieval of 25 facts from it
would measure retrieval, not forgetting. So instances are dealt, hop-stratified,
into memories of 75 instances (40 memories, about 360 fact lines each, close to
MQuAKE-T's 382 and FactConsolidation's 380), and each memory is one DRIFT
conversation:

  * 38 sessions one day apart, as in the other benchmarks;
  * every edit in the memory: the old value in session i, the new value in a
    later session j > i, placed at random (no "old half / new half" boundary);
  * every unedited chain fact the memory's questions depend on, before and after
    the edit, in a random session;
  * one question per instance (its first paraphrase), gold = MQuAKE's post-edit
    chain answer, stale_answer = the pre-edit chain answer (when it passes the
    same substring-safety rules as the other benchmarks).

The 40 memories are written as shards (default 4 files of 10 memories), so a
run can be spread over several terminals.

Usage:
    python scripts/build_mquake_cf.py --from-file MQuAKE-CF-3k-v2.json
    python scripts/build_mquake_cf.py                 # fetches from GitHub
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_mquake import RAW_URL, statement, usable_stale  # noqa: E402

DAY = 86400.0


def edit_cloze(rw: dict) -> str:
    return rw["prompt"].format(rw["subject"]).strip()


def check_consistent(raw: list[dict]) -> dict[str, tuple[str, str]]:
    """Edited cloze -> (old, new); stops if any two facts disagree."""
    edits: dict[str, tuple[str, str]] = {}
    for item in raw:
        for rw in item["requested_rewrite"]:
            c, pair = edit_cloze(rw), (rw["target_true"]["str"], rw["target_new"]["str"])
            if edits.setdefault(c, pair) != pair:
                raise SystemExit(f"conflicting edits for {c!r}")
    unedited: dict[str, str] = {}
    for item in raw:
        for hop in item["single_hops"] + item["new_single_hops"]:
            c = hop["cloze"].strip()
            if c in edits:
                if hop["answer"] not in edits[c]:
                    raise SystemExit(f"chain fact disagrees with an edit: {c!r}")
            elif unedited.setdefault(c, hop["answer"]) != hop["answer"]:
                raise SystemExit(f"two values for the unedited fact {c!r}")
    return edits


def deal(raw: list[dict], group_size: int, seed: int) -> list[list[dict]]:
    """Hop-stratified groups: each memory gets the same mix of 2-, 3-, 4-hop."""
    rng = random.Random(seed)
    by_hop: dict[int, list[dict]] = defaultdict(list)
    for item in raw:
        by_hop[len(item["single_hops"])].append(item)
    for h in sorted(by_hop):
        rng.shuffle(by_hop[h])
    n_groups = -(-len(raw) // group_size)
    groups: list[list[dict]] = [[] for _ in range(n_groups)]
    i = 0
    for h in sorted(by_hop):
        for item in by_hop[h]:
            groups[i % n_groups].append(item)
            i += 1
    return groups


def build_memory(group: list[dict], gid: int, edits_all: dict, sessions: int,
                 seed: int) -> dict:
    rng = random.Random(seed * 1000 + gid)
    edits: dict[str, tuple[str, str]] = {}
    facts: dict[str, str] = {}
    for item in group:
        for rw in item["requested_rewrite"]:
            edits[edit_cloze(rw)] = edits_all[edit_cloze(rw)]
    for item in group:
        for hop in item["single_hops"] + item["new_single_hops"]:
            c = hop["cloze"].strip()
            if c not in edits:
                facts.setdefault(c, hop["answer"])

    buckets: list[list[str]] = [[] for _ in range(sessions)]
    for c, (old, new) in sorted(edits.items()):
        i = rng.randrange(0, sessions - 1)
        j = rng.randrange(i + 1, sessions)
        buckets[i].append(statement(c, old))
        buckets[j].append(statement(c, new))
    for c, v in sorted(facts.items()):
        buckets[rng.randrange(0, sessions)].append(statement(c, v))

    base = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    sess = []
    for idx, lines in enumerate(buckets):
        if lines:
            rng.shuffle(lines)
            sess.append({"time": base + idx * DAY, "lines": [f"user: {ln}" for ln in lines]})

    questions = []
    for item in group:
        edited = {edit_cloze(rw) for rw in item["requested_rewrite"]}
        pos = [i for i, h in enumerate(item["single_hops"]) if h["cloze"].strip() in edited]
        questions.append({
            "question": item["questions"][0],
            "answer": item["new_answer"],
            "current_answer": item["new_answer"],
            "category": "knowledge_update_multihop",
            "stale_answer": usable_stale(item["answer"], item["new_answer"]),
            "hops": len(item["single_hops"]),
            "edit_position": min(pos) if pos else -1,
            "n_edits": len(item["requested_rewrite"]),
            "case_id": item.get("case_id"),
            # MQuAKE's accepted aliases, for alias-aware EM / SubEM / staleness offline
            "answer_alias": item.get("new_answer_alias", []),
            "stale_alias": item.get("answer_alias", []),
        })
    return {"id": f"mquake_cf_g{gid:02d}", "sessions": sess, "questions": questions}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", default=None, help="local MQuAKE-CF-3k-v2.json")
    ap.add_argument("--group-size", type=int, default=75, help="instances per memory")
    ap.add_argument("--sessions", type=int, default=38)
    ap.add_argument("--shards", type=int, default=4, help="output files")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-prefix", default="data/mquake_cf_mh")
    args = ap.parse_args()

    if args.from_file:
        raw = json.loads(Path(args.from_file).read_text())
    else:
        print("Fetching MQuAKE-CF-3k-v2 ...")
        with urllib.request.urlopen(RAW_URL.format(name="MQuAKE-CF-3k-v2"), timeout=300) as r:
            raw = json.loads(r.read())
    edits_all = check_consistent(raw)
    groups = deal(raw, args.group_size, args.seed)
    convos = [build_memory(g, i, edits_all, args.sessions, args.seed) for i, g in enumerate(groups)]

    per = -(-len(convos) // args.shards)
    for s in range(args.shards):
        part = convos[s * per:(s + 1) * per]
        out = Path(f"{args.out_prefix}_s{s + 1}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"name": out.stem, "conversations": part}))
        print(f"Wrote {out}: {len(part)} memories, {sum(len(c['questions']) for c in part)} questions")

    qs = [q for c in convos for q in c["questions"]]
    lines = [sum(len(s["lines"]) for s in c["sessions"]) for c in convos]
    print(f"{len(raw)} instances, {len(edits_all)} distinct edits, {len(convos)} memories")
    print(f"  fact lines per memory: mean {sum(lines) / len(lines):.0f}, min {min(lines)}, max {max(lines)}")
    print(f"  hops {dict(sorted(Counter(q['hops'] for q in qs).items()))}")
    print(f"  first edited hop {dict(sorted(Counter(q['edit_position'] for q in qs).items()))}")
    print(f"  with stale_answer {sum(1 for q in qs if q['stale_answer'])} of {len(qs)}")


if __name__ == "__main__":
    main()
