"""Checks on the multi-hop datasets used by the v3 multi-hop extension.

Offline: reads the converted files in data/ only.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "data" / name).read_text())["conversations"][0]


def test_mquake_t_mh_questions_have_stale_and_chain_shape():
    c = load("mquake_t_mh.json")
    qs = c["questions"]
    assert len(qs) == 100
    assert all(q["stale_answer"] and q["current_answer"] == q["answer"] for q in qs)
    assert all(q["stale_answer"].lower() not in q["answer"].lower() for q in qs)
    assert {q["hops"] for q in qs} <= {2, 3, 4}
    assert all(q["edit_position"] >= 0 for q in qs)


def test_mquake_t_mh_answers_are_stored_old_before_new():
    c = load("mquake_t_mh.json")
    first = {}
    for s in c["sessions"]:
        for line in s["lines"]:
            first.setdefault(line, s["time"])
    for q in c["questions"]:
        new = [t for line, t in first.items() if q["answer"] in line]
        old = [t for line, t in first.items() if q["stale_answer"] in line]
        assert new, f"current answer never stated: {q['question']}"
        assert old, f"superseded answer never stated: {q['question']}"
        assert min(old) < max(new)


def test_mquake_t_mh_keeps_single_hop_retrieval_pressure():
    mh, sh = load("mquake_t_mh.json"), load("mquake_t_sh.json")
    n = lambda c: sum(len(s["lines"]) for s in c["sessions"])
    assert len(mh["sessions"]) == len(sh["sessions"])
    assert n(mh) == n(sh)


def test_factconsolidation_mh_shares_single_hop_context():
    mh, sh = load("factconsolidation_mh_6k.json"), load("factconsolidation_sh_6k.json")
    assert mh["sessions"] == sh["sessions"]   # same facts, so extraction is shared
    qs = mh["questions"]
    assert len(qs) == 100
    assert all(q["stale_answer"] for q in qs)
    assert all(q["stale_answer"].lower() not in q["answer"].lower() for q in qs)
    assert {q["hops"] for q in qs} <= {2, 3, 4}


def test_mquake_cf_complete_set_in_shards():
    convos = [c for k in range(1, 5)
              for c in json.loads((ROOT / f"data/mquake_cf_mh_s{k}.json").read_text())["conversations"]]
    qs = [q for c in convos for q in c["questions"]]
    assert len(convos) == 40 and len(qs) == 3000
    hops = {}
    for q in qs:
        hops[q["hops"]] = hops.get(q["hops"], 0) + 1
    assert hops == {2: 1135, 3: 1136, 4: 729}
    assert sum(1 for q in qs if q["stale_answer"]) >= 2980
    for c in convos:
        lines = sum(len(s["lines"]) for s in c["sessions"])
        assert 300 <= lines <= 420 and len(c["sessions"]) <= 38
