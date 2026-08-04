"""Build the LongMemEval knowledge-update (KU) staleness benchmark for DRIFT.

Why this dataset exists
-----------------------
DRIFT's headline metric -- *staleness*, the fraction of answers that repeat a
superseded fact -- can only fire on questions annotated with `stale_answer`
(see `drift/runner.py:staleness_hit`). Neither of the converted real benchmarks
carried that annotation:

    LoCoMo                 0 / 300 questions with stale_answer
    LongMemEval (oracle)   0 / 150 questions with stale_answer

so staleness read exactly 0.000 across all 42 single-agent cells of the first
real campaign -- a metric that structurally could not fire, not a finding.

LongMemEval *does* contain the ground truth, though. Its `knowledge-update`
question type is built from a user fact that changes across sessions, and the
raw items mark the relevant turns with `has_answer: True`. Ordering those turns
by session date gives the transition directly:

    [2023/05/25] "...personal best time in a charity 5K run with a time of 27:12"   <- old
    [2023/05/27] "...hoping to beat my personal best time of 25:50 this time"       <- new (gold)

The old value is exactly `stale_answer`. 70 of the 78 KU items have evidence
spanning two or more distinct dates, so the transition is recoverable.

We build from the `s` variant (~50 haystack sessions per question) rather than
`oracle` (~2.6). The oracle variant is evidence-only, which leaves a forgetting
policy nothing to forget -- on the first campaign P0 and P1 scored *identically*
on LongMemEval's multi_hop and temporal categories because the policy never
fired. The `s` variant puts the same questions under realistic retrieval load.

Usage:
    python scripts/build_longmemeval_ku.py                     # default: s variant
    python scripts/build_longmemeval_ku.py --variant oracle    # cheap ablation
    python scripts/build_longmemeval_ku.py --review-csv out.csv  # dump for hand-check
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from any cwd

from drift.providers import make_provider  # noqa: E402

HF_URL = "https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_{variant}"

STALE_SYSTEM = (
    "You extract the OLD value of a fact that later changed. "
    "Reply with ONLY the old value as a short literal string (a number, amount, "
    "time, place, or short noun phrase) exactly as it would appear in an answer. "
    "If the earlier message does not state a clearly different old value, reply NONE."
)

STALE_PROMPT = """TASK:STALE
A user fact changed over time. Below is the QUESTION, the CURRENT (new) answer,
and the EARLIER message that stated the previous value.

QUESTION:
{question}
CURRENT ANSWER (new value):
{answer}
EARLIER MESSAGE:
{earlier}

Reply with only the OLD value (short literal string), or NONE.
"""


def parse_date(d: str) -> float:
    for fmt in ("%Y/%m/%d (%a) %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(d.strip(), fmt).timestamp()
        except ValueError:
            continue
    return 0.0


def evidence_turns(item: dict) -> list[tuple[str, str]]:
    """(session_date, turn_text) for every turn flagged has_answer, date-ordered."""
    out = []
    ids = item.get("haystack_session_ids", [])
    for sid in item.get("answer_session_ids", []):
        if sid not in ids:
            continue
        idx = ids.index(sid)
        date = item["haystack_dates"][idx] if idx < len(item["haystack_dates"]) else ""
        for turn in item["haystack_sessions"][idx]:
            if turn.get("has_answer") and (turn.get("content") or "").strip():
                out.append((date, turn["content"].strip()))
    out.sort(key=lambda x: parse_date(x[0]))
    return out


# staleness_hit() is a substring test (`stale_answer.lower() in answer.lower()`),
# so a stale_answer that is a common word or a bare polarity token would fire on
# almost any prose answer and inflate the staleness rate. Those items are dropped
# rather than annotated: a smaller, precise annotation set is worth more than a
# larger one that silently manufactures false positives.
AMBIGUOUS = {
    "yes", "no", "none", "n a", "true", "false", "one", "two", "some", "many",
    "more", "less", "it", "them", "there", "here", "same", "other", "another",
}


def clean_stale(raw: str, gold: str) -> str | None:
    """Normalize the model's reply into a usable stale_answer, or None.

    Rejects: NONE replies, empty strings, over-long sentences (the metric is a
    substring check, so a whole sentence would essentially never match), values
    that are just the gold answer restated, and short/ambiguous tokens that
    would false-positive against ordinary prose.
    """
    s = (raw or "").strip().strip('"').strip("'").strip()
    s = s.split("\n")[0].strip()
    if not s or s.upper().startswith("NONE"):
        return None
    if len(s) > 60 or len(s.split()) > 8:
        return None
    g = re.sub(r"[^a-z0-9]", "", gold.lower())
    c = re.sub(r"[^a-z0-9]", "", s.lower())
    if not c or c == g or (len(c) > 3 and c in g):
        return None  # not actually a *different* value
    bare = re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()
    bare = re.sub(r"\s+", " ", bare)
    if bare in AMBIGUOUS or len(bare) < 3:
        return None
    return s


def build(raw: list[dict], provider, variant: str, limit: int | None) -> tuple[dict, list[dict]]:
    ku = [x for x in raw if x.get("question_type") == "knowledge-update"]
    if limit:
        ku = ku[:limit]
    conversations, review = [], []
    derived = skipped = 0

    for item in ku:
        ev = evidence_turns(item)
        gold = str(item.get("answer", ""))
        stale = None
        if len(ev) >= 2 and len({d for d, _ in ev}) >= 2:
            earlier = ev[0][1]
            try:
                reply = provider.complete(
                    STALE_PROMPT.format(question=item["question"], answer=gold,
                                        earlier=earlier[:1500]),
                    system=STALE_SYSTEM, max_tokens=32).text
                stale = clean_stale(reply, gold)
            except Exception as e:  # noqa: BLE001 - one bad item must not kill the build
                print(f"  ! {item.get('question_id')}: {str(e)[:80]}")
                stale = None
        derived += stale is not None
        skipped += stale is None

        sessions = []
        dates = item.get("haystack_dates", [])
        for i, sess in enumerate(item.get("haystack_sessions", [])):
            lines = [f"{t.get('role','user')}: {(t.get('content') or '').strip()}"
                     for t in sess if (t.get("content") or "").strip()]
            if lines:
                sessions.append({"time": parse_date(dates[i]) if i < len(dates) else float(i * 86400),
                                 "lines": lines})
        sessions.sort(key=lambda s: s["time"])

        conversations.append({
            "id": str(item.get("question_id", f"ku_{len(conversations)}")),
            "sessions": sessions,
            "questions": [{
                "question": item["question"],
                "answer": gold,
                "category": "knowledge_update",
                "stale_answer": stale,
            }],
        })
        review.append({
            "question_id": item.get("question_id", ""),
            "question": item["question"],
            "gold_answer": gold,
            "stale_answer": stale or "",
            "earliest_evidence": ev[0][1][:300] if ev else "",
            "n_sessions": len(sessions),
        })

    print(f"  stale_answer derived: {derived}/{len(ku)}  (not derivable: {skipped})")
    return {"name": f"longmemeval_ku_{variant}", "conversations": conversations}, review


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="s", choices=["s", "oracle"],
                    help="s = ~50 haystack sessions/question (retrieval pressure); "
                         "oracle = evidence-only (~2.6, cheap ablation)")
    ap.add_argument("--in", dest="infile", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--annotator", default="ollama:gpt-oss:20b",
                    help="provider:model used to extract old values (cached, ~78 calls)")
    ap.add_argument("--review-csv", default="data/longmemeval_ku_review.csv")
    args = ap.parse_args()

    out = Path(args.out or f"data/longmemeval_ku_{args.variant}.json")

    if args.infile:
        raw = json.loads(Path(args.infile).read_text())
    else:
        url = HF_URL.format(variant=args.variant)
        print(f"Downloading {url} ...")
        with urllib.request.urlopen(url, timeout=900) as resp:
            raw = json.loads(resp.read())

    provider = make_provider(args.annotator, ".drift_cache")
    print(f"Annotating stale_answer with {args.annotator} (cached) ...")
    dataset, review = build(raw, provider, args.variant, args.limit)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset))

    n_sess = sum(len(c["sessions"]) for c in dataset["conversations"])
    n_stale = sum(1 for c in dataset["conversations"] for q in c["questions"] if q["stale_answer"])
    print(f"Wrote {out}: {len(dataset['conversations'])} questions, {n_sess} sessions, "
          f"{n_stale} with stale_answer")

    if args.review_csv:
        rp = Path(args.review_csv)
        with rp.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(review[0].keys()))
            w.writeheader()
            w.writerows(review)
        print(f"Review sheet -> {rp}  (hand-check stale_answer before reporting)")


if __name__ == "__main__":
    main()
