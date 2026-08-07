"""Offline tests for the bitemporal replay viewer and the live monitor.

The replay's whole correctness claim is that a fact's colour at session t is a
pure function of the timestamps the fact already carries -- no simulation. These
tests pin that function, plus the two properties that make the feature safe to
ship: the live writer never raises, and it never serialises embeddings.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "analysis"))

import timeline as tl  # noqa: E402

from drift import live  # noqa: E402
from drift.embeddings import HashingEmbedder  # noqa: E402
from drift.memory.graph import BitemporalGraph, Fact  # noqa: E402

DAY = 86400.0
T0 = 1704067200.0


def fact(**kw):
    base = dict(subject="s", predicate="p", object="o", text="t",
                t_valid_start=T0, t_ingested=T0)
    base.update(kw)
    return base


def cell(facts, policy="P2"):
    return {"summary": {"policy": policy, "model": "m", "accuracy": 1.0,
                        "staleness_rate": 0.0},
            "graph_snapshot": facts, "memory_curves": []}


# --------------------------------------------------------------------------- #
# session indexing
# --------------------------------------------------------------------------- #

def test_session_times_are_the_union_across_panels():
    """Comparison mode must share one axis: a policy that rejects writes has
    fewer distinct ingestion times, and indexing per panel would desync them."""
    a = cell([fact(t_ingested=T0), fact(t_ingested=T0 + 2 * DAY)])
    b = cell([fact(t_ingested=T0 + DAY)], policy="P3")
    assert tl._session_times([a, b]) == [T0, T0 + DAY, T0 + 2 * DAY]


def test_index_of_maps_timestamps_to_sessions():
    times = [T0, T0 + DAY, T0 + 2 * DAY]
    assert tl._index_of(T0, times) == 0
    assert tl._index_of(T0 + 2 * DAY, times) == 2
    assert tl._index_of(None, times) is None


def test_index_of_rounds_forward_to_next_session():
    """A prune stamped between sessions belongs to the session that observes it,
    not the one before -- otherwise a fact disappears before its cause."""
    times = [T0, T0 + DAY, T0 + 2 * DAY]
    assert tl._index_of(T0 + 0.5 * DAY, times) == 1


# --------------------------------------------------------------------------- #
# the lifecycle function -- this is what the colours mean
# --------------------------------------------------------------------------- #

def state(edge, t):
    """Mirror of the viewer's state() in JS. Kept in sync by these tests."""
    if edge["in"] is None or edge["in"] > t:
        return None
    if edge["pr"] is not None and edge["pr"] <= t:
        return "pru"
    if edge["inv"] is not None and edge["inv"] <= t:
        return "inv"
    return "act"


@pytest.fixture
def lifecycle():
    facts = [fact(t_ingested=T0, t_invalid_at=T0 + 2 * DAY,
                  t_pruned=T0 + 3 * DAY, active=False, text="superseded then pruned"),
             fact(t_ingested=T0 + 2 * DAY, text="the correction")]
    times = [T0 + i * DAY for i in range(4)]
    return tl.build_panel(cell(facts), times, "P2")


def test_fact_is_invisible_before_ingestion(lifecycle):
    assert state(lifecycle["edges"][1], 0) is None
    assert state(lifecycle["edges"][1], 1) is None


def test_fact_is_active_between_ingestion_and_supersession(lifecycle):
    e = lifecycle["edges"][0]
    assert state(e, 0) == "act"
    assert state(e, 1) == "act"


def test_fact_is_superseded_at_the_session_its_window_closes(lifecycle):
    assert state(lifecycle["edges"][0], 2) == "inv"


def test_pruning_takes_precedence_over_supersession(lifecycle):
    """A pruned fact is gone from memory; it must not still read as merely
    superseded, which is the state P0 keeps showing the answer model."""
    assert state(lifecycle["edges"][0], 3) == "pru"


def test_correction_becomes_active_exactly_when_the_old_fact_turns_red(lifecycle):
    old, new = lifecycle["edges"]
    assert state(old, 2) == "inv" and state(new, 2) == "act"


# --------------------------------------------------------------------------- #
# legacy snapshots
# --------------------------------------------------------------------------- #

def test_legacy_pruned_facts_are_flagged_and_placed_at_the_end():
    """Runs predating t_pruned record that a fact was dropped but not when.
    Guessing a session would put an event at a time it did not happen."""
    times = [T0 + i * DAY for i in range(4)]
    panel = tl.build_panel(cell([fact(active=False)]), times, "P1")
    e = panel["edges"][0]
    assert e["lg"] is True
    assert e["pr"] == len(times) - 1


def test_current_snapshots_are_not_flagged_legacy():
    times = [T0 + i * DAY for i in range(4)]
    panel = tl.build_panel(cell([fact(active=False, t_pruned=T0 + DAY)]), times, "P1")
    assert panel["edges"][0]["lg"] is False
    assert panel["edges"][0]["pr"] == 1


# --------------------------------------------------------------------------- #
# build()
# --------------------------------------------------------------------------- #

def test_build_collects_supersession_sessions_for_the_jump_button():
    times_facts = [fact(t_ingested=T0, t_invalid_at=T0 + DAY),
                   fact(t_ingested=T0, t_invalid_at=T0 + 3 * DAY),
                   fact(t_ingested=T0 + DAY), fact(t_ingested=T0 + 2 * DAY),
                   fact(t_ingested=T0 + 3 * DAY)]
    out = tl.build([cell(times_facts)], ["P2"])
    assert out["events"] == [1, 3]


def test_build_rejects_snapshotless_results():
    with pytest.raises(SystemExit):
        tl.build([{"summary": {}, "graph_snapshot": []}], ["P0"])


def test_html_has_no_external_requests():
    """The viewer must open from file:// with no network -- it is an examiner
    artifact, not a hosted page."""
    for token in ("http://", "https://", "cdn", "<script src"):
        assert token not in tl.HTML.lower()


# --------------------------------------------------------------------------- #
# live monitor
# --------------------------------------------------------------------------- #

def test_live_strips_embeddings():
    f = Fact(subject="a", predicate="p", object="b", text="t",
             t_valid_start=T0, t_ingested=T0, embedding=[0.1] * 768)
    assert "embedding" not in live.slim([f])[0]


def test_live_write_produces_atomic_readable_json(tmp_path):
    g = BitemporalGraph(HashingEmbedder())
    g.add_fact("a", "lives_in", "b", "a lives in b", t_event=T0)
    live.write(tmp_path, policy="P2", model="m", conversation="c",
               session=0, n_sessions=1, graph=g, curves=[])
    payload = json.loads((tmp_path / "live.json").read_text())
    assert payload["policy"] == "P2" and len(payload["facts"]) == 1
    assert (tmp_path / "live.html").exists()
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"


def test_live_write_never_raises_on_a_broken_graph(tmp_path):
    """Monitoring must not be able to kill a six-hour campaign."""
    class Exploding:
        facts: dict = {}

        def stats(self):
            raise RuntimeError("boom")

    live.write(tmp_path, policy="P2", model="m", conversation="c",
               session=0, n_sessions=1, graph=Exploding(), curves=[])
    assert not (tmp_path / "live.json").exists()


def test_live_write_never_raises_on_an_unwritable_path():
    live.write("/proc/nonexistent/nope", policy="P2", model="m", conversation="c",
               session=0, n_sessions=1, graph=BitemporalGraph(HashingEmbedder()),
               curves=[])
