"""Convert MQuAKE-T into DRIFT's schema -- the generalization test for FactConsolidation.

MQuAKE: Zhong et al., "MQuAKE: Assessing Knowledge Editing in Language Models via
Multi-Hop Questions" (EMNLP 2023), arXiv:2305.14795. MIT licensed.
https://github.com/princeton-nlp/MQuAKE

Why this dataset, given we already have FactConsolidation
---------------------------------------------------------
FactConsolidation answered RQ1-RQ3, but on a single benchmark whose properties
are unusually kind to P2 (bitemporal contradiction):

  * its supersessions are *injected* -- the gold answers are counterfactual
    ("rugby union was created in India"), so parametric knowledge is useless and
    the memory-vs-no-memory gap is maximal by construction (NOMEM scored 0.000);
  * every predicate in it is single-valued, which is why the run needed
    `functional_predicates: "*"`. That flag was chosen *on this dataset*.

Neither property is guaranteed elsewhere, so "P2 is free" currently rests on one
corpus in one regime. MQuAKE-T is the cleanest available second point because it
breaks the first property while holding the task form fixed:

  * its updates are **real**. MQuAKE-T is built by diffing Wikidata snapshots
    from April 2021 against April 2023 and keeping relations where a change is a
    genuine real-world update (Bill de Blasio -> Eric Adams as head of the New
    York City government, and so on). Nothing is fabricated, so the answers are
    not adversarial to the model's priors the way FactConsolidation's are.
  * `answer` (pre-edit) and `new_answer` (post-edit) ship with every instance, so
    `stale_answer` is recovered **deterministically**. This matters: the
    LongMemEval-KU build had to ask an LLM to name the superseded value and got
    1 usable annotation out of 78. Here there is no annotator to fail.
  * it carries multi-hop questions over the same edits, giving a second axis
    (`--hop mh`) at no extra conversion cost.

What it does *not* test: extraction noise. Like FactConsolidation, facts arrive
as clean atomic statements. The conversational regime (LoCoMo, LongMemEval-KU)
remains the missing third point, and the write-up should say so.

Honest limitation to report: the edited relations are narrow. Of 1,868
instances, 1,157 edit P6 (head of government) and 651 edit P35 (head of state) --
96 unique (subject, relation) supersessions in total. That is enough for a
~96-question single-hop benchmark that lines up cell-for-cell with
FactConsolidation's 100, but it is a head-of-office corpus, not a broad one.

Design of the conversion
------------------------
Sessions are built so that for every edited pair the *old* value is stated in a
strictly earlier session than the *new* one -- without that, valid-time windows
(P2) and TTL decay (P1) have nothing to act on.

Placement is randomized per pair (old in session i, new in some session j > i)
rather than blocked into an "old half" and a "new half". A clean boundary would
be trivially exploitable: any policy could learn "later session wins" without
using bitemporal structure at all, which is precisely the confound the P2-vs-P5
ablation exists to rule out.

Unedited single-hop facts from the same instances are mixed in as haystack, so
the fact-to-question density (~3.8 facts per question) matches
FactConsolidation's and the two runs face comparable retrieval pressure.

Usage:
    python scripts/download_mquake.py                    # single-hop, ~96 questions
    python scripts/download_mquake.py --hop mh --max-questions 100
    python scripts/download_mquake.py --dataset MQuAKE-CF-3k-v2   # counterfactual sibling
"""
from __future__ import annotations

import argparse
import json
import random
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAW_URL = "https://raw.githubusercontent.com/princeton-nlp/MQuAKE/main/datasets/{name}.json"

# `staleness_hit()` in drift/runner.py is a substring test
# (`stale_answer.lower() in answer.lower()`), so a stale value that is a common
# word -- or a substring of the gold answer -- would fire against almost any
# prose answer and manufacture false staleness. Such pairs are dropped rather
# than annotated; a smaller precise annotation set beats a larger noisy one.
AMBIGUOUS = {
    "yes", "no", "none", "true", "false", "one", "two", "it", "them",
    "there", "here", "same", "other", "another", "unknown", "n a",
}


def fetch(name: str, timeout: int = 300) -> list[dict]:
    url = RAW_URL.format(name=name)
    print(f"Fetching {url} ...")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def usable_stale(stale: str, gold: str) -> str | None:
    """Return `stale` if it is a safe superseded-value annotation, else None."""
    s = (stale or "").strip()
    g = (gold or "").strip()
    if not s or not g:
        return None
    ls, lg = s.lower(), g.lower()
    if ls == lg or ls in lg or lg in ls:
        return None  # substring collision would make staleness fire on the gold
    bare = re.sub(r"[^a-z0-9 ]", " ", ls).strip()
    bare = re.sub(r"\s+", " ", bare)
    if bare in AMBIGUOUS or len(bare) < 3:
        return None
    return s


# Contradiction detection keys on (subject, predicate) as produced by the LLM
# extractor, so the *phrasing* of an ingested fact decides whether P2 can see a
# supersession at all. MQuAKE's own cloze for P6 is "The name of the current
# head of the {} government is", which invites an extractor to key the subject
# on the whole noun phrase ("the name of the current head of ...") rather than
# on the entity. Both the old and the new statement share that phrasing, so the
# key would still *match* -- but the wordier the frame, the more extraction
# variance there is, and an extraction miss here is silent and looks exactly
# like a null policy result.
#
# These templates restate the same triple in the flat subject-predicate-object
# form FactConsolidation uses ("goaltender is associated with the sport of X"),
# which that run confirmed the extractors handle cleanly (133 invalidations).
# Semantics and gold answers are untouched; only surface form changes, and every
# converter in this repo already reformats its source into session lines.
# Unmapped relations (the CF variants carry many) fall back to MQuAKE's cloze.
RELATION_TEMPLATES = {
    "P6":    "The head of government of {subject} is {object}",
    "P35":   "The head of state of {subject} is {object}",
    "P1037": "The director of {subject} is {object}",
    "P159":  "The headquarters of {subject} is located in the city of {object}",
    "P169":  "The chief executive officer of {subject} is {object}",
    "P108":  "{subject} is employed by {object}",
    "P286":  "The head coach of {subject} is {object}",
}


def statement(cloze: str, value: str) -> str:
    """Cloze + filler -> a complete declarative sentence."""
    c = cloze.strip().rstrip(".").rstrip()
    return f"{c} {value.strip()}."


def edit_statement(info: dict, value: str, phrasing: str = "flat") -> str:
    """Statement for an edited fact.

    `flat` uses RELATION_TEMPLATES (better extraction, the default). `cloze`
    keeps MQuAKE's original wording, which mirrors the question text almost
    verbatim and so scores higher on the lexical third of hybrid retrieval --
    at the cost of a wordier subject for the extractor to key on. Exposed as a
    knob rather than decided silently, because the two phrasings trade
    extraction fidelity against retrieval score and the right answer is an
    empirical question on any given corpus.
    """
    tpl = RELATION_TEMPLATES.get(info["relation"])
    if phrasing == "flat" and tpl:
        return tpl.format(subject=info["subject"], object=value.strip()) + "."
    return statement(info["cloze"], value)


def collect(raw: list[dict]) -> tuple[dict, dict, list[dict]]:
    """-> (edits, support, instances)

    edits:    (subject, relation_id) -> {cloze, old, new, question}
              deduped; 1,868 MQuAKE-T instances collapse to 96 distinct edits.
    support:  cloze -> value, for every *unedited* single hop (haystack).
    instances: the raw items, kept for building multi-hop questions.
    """
    edits: dict[tuple[str, str], dict] = {}
    support: dict[str, str] = {}

    for item in raw:
        rw = item["requested_rewrite"][0]
        key = (rw["subject"], rw["relation_id"])
        cloze = rw["prompt"].format(rw["subject"]).strip()
        if key not in edits:
            edits[key] = {
                "cloze": cloze,
                "subject": rw["subject"],
                "old": rw["target_true"]["str"],
                "new": rw["target_new"]["str"],
                "question": rw["question"],
                "relation": rw["relation_id"],
            }
        for hop in item.get("single_hops", []):
            hc = hop["cloze"].strip()
            if hc != cloze and hc not in support:
                support[hc] = hop["answer"]

    return edits, support, raw


def build_sessions(edits: dict, support: dict, n_sessions: int,
                   support_lines: int, seed: int, day_step: float,
                   phrasing: str = "flat") -> list[dict]:
    """Place old-before-new per edited pair, then fill with haystack facts."""
    rng = random.Random(seed)
    buckets: list[list[str]] = [[] for _ in range(n_sessions)]

    for info in edits.values():
        # old in [0, n-2], new strictly after it -- guarantees the supersession
        # is visible to valid-time reasoning while keeping the boundary diffuse.
        i = rng.randrange(0, n_sessions - 1)
        j = rng.randrange(i + 1, n_sessions)
        buckets[i].append(edit_statement(info, info["old"], phrasing))
        buckets[j].append(edit_statement(info, info["new"], phrasing))

    pool = list(support.items())
    rng.shuffle(pool)
    for cloze, value in pool[:support_lines]:
        buckets[rng.randrange(0, n_sessions)].append(statement(cloze, value))

    base = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    sessions = []
    for idx, lines in enumerate(buckets):
        if not lines:
            continue
        rng.shuffle(lines)
        sessions.append({
            "time": base + idx * day_step * 86400,
            "lines": [f"user: {ln}" for ln in lines],
        })
    return sessions


def build_questions(hop: str, edits: dict, instances: list[dict],
                    max_questions: int | None, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []

    if hop == "sh":
        # One question per distinct supersession. Gold is the *post*-update
        # value; the pre-update value is exactly what a stale memory returns.
        for info in edits.values():
            stale = usable_stale(info["old"], info["new"])
            out.append({
                "question": info["question"],
                "answer": info["new"],
                "category": "knowledge_update",
                "stale_answer": stale,
            })
    else:
        # Multi-hop: the edit propagates through a reasoning chain, so the gold
        # answer changes as an *entailed consequence* rather than by direct
        # lookup. `answer` is the pre-edit chain result, `new_answer` the post.
        seen: set[str] = set()
        for item in instances:
            q = item["questions"][0]
            if q in seen:
                continue
            seen.add(q)
            stale = usable_stale(item["answer"], item["new_answer"])
            out.append({
                "question": q,
                "answer": item["new_answer"],
                "category": "knowledge_update_multihop",
                "stale_answer": stale,
            })
        rng.shuffle(out)

    if max_questions:
        out = out[:max_questions]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="MQuAKE-T",
                    choices=["MQuAKE-T", "MQuAKE-CF-3k-v2", "MQuAKE-CF"],
                    help="MQuAKE-T = real Wikidata drift 2021->2023 (the "
                         "generalization test). CF variants are counterfactual, "
                         "i.e. the same regime as FactConsolidation.")
    ap.add_argument("--hop", default="sh", choices=["sh", "mh"],
                    help="sh = direct lookup of the edited fact (comparable to "
                         "factconsolidation_sh_6k); mh = multi-hop entailment")
    ap.add_argument("--max-questions", type=int, default=None,
                    help="cap question count (mh has 1,868 available)")
    ap.add_argument("--sessions", type=int, default=38,
                    help="matches FactConsolidation's 38 so TTL/grace windows "
                         "operate over the same valid-time span")
    ap.add_argument("--support-lines", type=int, default=190,
                    help="haystack facts to mix in. Default puts total lines "
                         "near FactConsolidation's 380 for comparable pressure.")
    ap.add_argument("--phrasing", default="flat", choices=["flat", "cloze"],
                    help="flat = compact subject-predicate-object statements "
                         "(better extraction, the default); cloze = MQuAKE's "
                         "original wording (mirrors the question, so higher "
                         "lexical retrieval score)")
    ap.add_argument("--day-step", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    raw = fetch(args.dataset)
    edits, support, instances = collect(raw)
    print(f"  {len(raw)} instances -> {len(edits)} distinct supersessions, "
          f"{len(support)} haystack facts available")

    if args.sessions < 2:
        raise SystemExit("--sessions must be at least 2 to place old before new")

    sessions = build_sessions(edits, support, args.sessions,
                              args.support_lines, args.seed, args.day_step,
                              args.phrasing)
    questions = build_questions(args.hop, edits, instances,
                                args.max_questions, args.seed)

    annotated = sum(1 for q in questions if q["stale_answer"])
    total_lines = sum(len(s["lines"]) for s in sessions)

    slug = args.dataset.lower().replace("-", "_")
    out = Path(args.out or f"data/{slug}_{args.hop}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"conversations": [{
        "id": f"{slug}_{args.hop}",
        "sessions": sessions,
        "questions": questions,
    }]}, indent=1))

    print(f"Wrote {out}")
    print(f"  {len(sessions)} sessions, {total_lines} fact lines")
    print(f"  {len(questions)} questions, {annotated} with stale_answer "
          f"({annotated / len(questions):.0%})")
    if annotated / max(len(questions), 1) < 0.5:
        print("  ! low stale_answer coverage -- staleness will be weakly powered")


if __name__ == "__main__":
    main()
