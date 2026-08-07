"""Offline tests for the MQuAKE-T -> DRIFT converter.

These cover the two properties the generalization experiment silently depends
on, both of which fail invisibly if broken:

  * every edited pair states its OLD value in a strictly earlier session than
    its NEW one -- if that ordering breaks, P2 has no supersession to detect and
    the run reports a null result that looks like a policy finding;
  * `stale_answer` never collides with the gold answer -- `staleness_hit()` is a
    substring test, so a colliding annotation would fire on correct answers and
    manufacture staleness.

No network: the converter's pure functions are exercised against a small
hand-built fixture shaped like real MQuAKE-T rows.
"""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "download_mquake.py"
_spec = importlib.util.spec_from_file_location("mquake_convert", SCRIPT)
mq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mq)


def _row(subject, relation, old, new, question, hop_cloze, hop_answer):
    """One MQuAKE-T-shaped instance."""
    prompt = {"P6": "The name of the current head of the {} government is"}.get(
        relation, "The %s of {} is" % relation)
    return {
        "case_id": abs(hash(subject)) % 10_000,
        "requested_rewrite": [{
            "prompt": prompt,
            "relation_id": relation,
            "target_new": {"str": new, "id": "Q1"},
            "target_true": {"str": old, "id": "Q2"},
            "subject": subject,
            "question": question,
        }],
        "questions": [f"multi-hop about {subject}"],
        "answer": old,
        "new_answer": new,
        "single_hops": [
            {"question": "support", "cloze": hop_cloze, "answer": hop_answer},
            {"question": question, "cloze": prompt.format(subject), "answer": old},
        ],
    }


@pytest.fixture
def raw():
    return [
        _row("New York City", "P6", "Bill de Blasio", "Eric Adams",
             "What is the name of the current head of the New York City government?",
             "The headquarters of TV Land is located in the city of", "New York City"),
        _row("New Zealand", "P6", "Jacinda Ardern", "Chris Hipkins",
             "What is the name of the current head of the New Zealand government?",
             "Lorde is a citizen of", "New Zealand"),
        _row("Twitter", "P169", "Jack Dorsey", "Elon Musk",
             "Who is the chief executive officer of Twitter?",
             "Twitter was created in the country of", "United States of America"),
    ]


# --------------------------------------------------------------------------- #
# stale_answer safety
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("stale,gold", [
    ("New York", "New York City"),   # stale is a substring of gold
    ("New York City", "New York"),   # gold is a substring of stale
    ("Eric Adams", "Eric Adams"),    # identical
    ("yes", "Eric Adams"),           # ambiguous token
    ("", "Eric Adams"),              # empty
    ("Eric Adams", ""),              # no gold
])
def test_usable_stale_rejects_unsafe(stale, gold):
    assert mq.usable_stale(stale, gold) is None


def test_usable_stale_accepts_distinct_values():
    assert mq.usable_stale("Bill de Blasio", "Eric Adams") == "Bill de Blasio"


# --------------------------------------------------------------------------- #
# statement phrasing
# --------------------------------------------------------------------------- #

def test_flat_phrasing_uses_relation_template():
    info = {"relation": "P6", "subject": "New York City",
            "cloze": "The name of the current head of the New York City government is"}
    assert mq.edit_statement(info, "Eric Adams") == \
        "The head of government of New York City is Eric Adams."


def test_cloze_phrasing_preserves_source_wording():
    info = {"relation": "P6", "subject": "New York City",
            "cloze": "The name of the current head of the New York City government is"}
    out = mq.edit_statement(info, "Eric Adams", phrasing="cloze")
    assert out.startswith("The name of the current head of")
    assert out.endswith("Eric Adams.")


def test_unmapped_relation_falls_back_to_cloze():
    info = {"relation": "P9999", "subject": "X", "cloze": "The widget of X is"}
    assert mq.edit_statement(info, "Y") == "The widget of X is Y."


# --------------------------------------------------------------------------- #
# session construction -- the ordering guarantee
# --------------------------------------------------------------------------- #

def test_old_value_always_precedes_new_value(raw):
    edits, support, _ = mq.collect(raw)
    for seed in range(20):  # placement is randomized; the invariant must hold for any seed
        sessions = mq.build_sessions(edits, support, n_sessions=8,
                                     support_lines=5, seed=seed, day_step=1.0)
        flat = [(i, ln) for i, s in enumerate(sessions) for ln in s["lines"]]
        for info in edits.values():
            old_line = "user: " + mq.edit_statement(info, info["old"])
            new_line = "user: " + mq.edit_statement(info, info["new"])
            old_at = [i for i, ln in flat if ln == old_line]
            new_at = [i for i, ln in flat if ln == new_line]
            assert old_at and new_at, f"missing statement for {info['subject']}"
            assert min(old_at) < min(new_at), (
                f"seed {seed}: {info['subject']} new value not after old")


def test_sessions_have_increasing_timestamps(raw):
    edits, support, _ = mq.collect(raw)
    sessions = mq.build_sessions(edits, support, 8, 5, seed=1, day_step=1.0)
    times = [s["time"] for s in sessions]
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_every_edit_contributes_two_lines(raw):
    edits, support, _ = mq.collect(raw)
    sessions = mq.build_sessions(edits, support, 8, support_lines=0,
                                 seed=3, day_step=1.0)
    total = sum(len(s["lines"]) for s in sessions)
    assert total == 2 * len(edits)


# --------------------------------------------------------------------------- #
# question construction
# --------------------------------------------------------------------------- #

def test_collect_dedupes_edits_by_subject_relation(raw):
    edits, _, _ = mq.collect(raw + raw)  # same instances twice
    assert len(edits) == 3


def test_single_hop_questions_are_annotated(raw):
    edits, _, instances = mq.collect(raw)
    qs = mq.build_questions("sh", edits, instances, None, seed=0)
    assert len(qs) == len(edits)
    for q in qs:
        assert q["category"] == "knowledge_update"
        assert q["stale_answer"], f"unannotated: {q['question']}"
        assert q["stale_answer"].lower() not in q["answer"].lower()


def test_multi_hop_questions_use_entailed_answers(raw):
    edits, _, instances = mq.collect(raw)
    qs = mq.build_questions("mh", edits, instances, None, seed=0)
    assert qs and all(q["category"] == "knowledge_update_multihop" for q in qs)
    assert all(q["answer"] for q in qs)


def test_max_questions_caps_output(raw):
    edits, _, instances = mq.collect(raw)
    assert len(mq.build_questions("sh", edits, instances, 2, seed=0)) == 2


# --------------------------------------------------------------------------- #
# schema conformance -- runner.load_dataset must be able to consume this
# --------------------------------------------------------------------------- #

def test_output_matches_drift_dataset_schema(raw):
    edits, support, instances = mq.collect(raw)
    conv = {
        "id": "mquake_t_sh",
        "sessions": mq.build_sessions(edits, support, 8, 5, 42, 1.0),
        "questions": mq.build_questions("sh", edits, instances, None, 42),
    }
    assert set(conv) == {"id", "sessions", "questions"}
    for s in conv["sessions"]:
        assert set(s) == {"time", "lines"}
        assert isinstance(s["time"], float)
        assert all(ln.startswith("user: ") for ln in s["lines"])
    for q in conv["questions"]:
        assert set(q) == {"question", "answer", "category", "stale_answer"}
