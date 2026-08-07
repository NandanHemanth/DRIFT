"""Tests for the `Memory` integration facade.

The facade's contract is that it makes exactly the same decisions as the
experimental harness running the same policy. If those two drift apart, the
published results stop describing what a user of the library actually gets, so
the equivalence is pinned here rather than assumed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from drift import Memory, make_policy  # noqa: E402
from drift.embeddings import HashingEmbedder  # noqa: E402
from drift.memory.graph import BitemporalGraph  # noqa: E402
from drift.pipeline import ingest_session  # noqa: E402
from drift.providers import MockProvider  # noqa: E402

DAY = 86400.0
T0 = 1704067200.0

SESSIONS = [
    ["user: I live in Boston.", "user: I work at Acme."],
    ["user: I moved to Seattle."],
    ["user: I joined Globex."],
]


def build(policy="P2", **kw):
    return Memory(policy=policy, provider="mock", embedder="hashing",
                  functional_predicates="*", **kw)


def test_observe_reports_extraction_and_writes():
    mem = build()
    out = mem.observe(SESSIONS[0], when=T0)
    assert out["extracted"] >= 1
    assert out["written"] == out["extracted"]  # P2 gates nothing on write


def test_facade_matches_the_harness_fact_for_fact():
    """Same policy, same input, same memory. This is the equivalence that lets
    the measured results be read as advice about the library."""
    mem = build()
    for i, lines in enumerate(SESSIONS):
        mem.observe(lines, when=T0 + i * DAY)

    graph = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
    policy = make_policy("P2")
    provider = MockProvider()
    for i, lines in enumerate(SESSIONS):
        ingest_session({"time": T0 + i * DAY, "lines": lines}, graph, policy, provider)

    assert mem.stats() == graph.stats()
    assert sorted(f.text for f in mem.facts()) == \
           sorted(f.text for f in graph.facts.values() if f.active)


def test_recall_returns_facts_and_respects_k():
    mem = build()
    for i, lines in enumerate(SESSIONS):
        mem.observe(lines, when=T0 + i * DAY)
    assert len(mem.recall("Where do I live?", k=2)) <= 2


def test_nomem_recalls_nothing():
    mem = build(policy="NOMEM")
    mem.observe(SESSIONS[0], when=T0)
    assert mem.recall("Where do I live?") == []
    assert mem.context("Where do I live?") == "(no relevant memory)"


def test_novelty_gate_rejects_writes_and_reports_it():
    mem = build(policy="P3")
    mem.observe(SESSIONS[0], when=T0)
    mem.observe(SESSIONS[0], when=T0 + DAY)  # identical content
    assert mem.stats()["write_rejections"] > 0


def test_remember_writes_a_structured_fact_directly():
    mem = build()
    f = mem.remember("user", "lives_in", "Seattle", when=T0)
    assert f is not None and f.object == "Seattle"
    assert any(x.object == "Seattle" for x in mem.facts())


def test_remember_returns_none_when_the_policy_rejects_the_write():
    mem = build(policy="P3")
    mem.remember("user", "lives_in", "Seattle", when=T0, text="user lives in Seattle")
    again = mem.remember("user", "lives_in", "Seattle", when=T0 + DAY,
                         text="user lives in Seattle")
    assert again is None


def test_contradiction_closes_the_old_window_under_p2():
    mem = build()
    mem.remember("user", "lives_in", "Boston", when=T0)
    mem.remember("user", "lives_in", "Seattle", when=T0 + DAY)
    boston = [f for f in mem.facts(include_pruned=True) if f.object == "Boston"][0]
    assert boston.invalidated
    assert boston not in mem.recall("Where do I live?", now=T0 + DAY)


def test_p0_keeps_showing_the_superseded_fact():
    """The failure mode the framework measures: append-only memory retrieves a
    value whose valid-time window has closed."""
    mem = build(policy="P0")
    mem.remember("user", "lives_in", "Boston", when=T0)
    mem.remember("user", "lives_in", "Seattle", when=T0 + DAY)
    recalled = mem.recall("Where do I live?", now=T0 + DAY, k=8)
    assert any(f.object == "Boston" and f.invalidated for f in recalled)


def test_context_renders_dated_lines_for_a_prompt():
    mem = build()
    mem.remember("user", "lives_in", "Seattle", when=T0, text="user lives in Seattle")
    block = mem.context("Where do I live?")
    assert "2024-01-01" in block and "Seattle" in block


def test_snapshot_is_a_replayable_event_log():
    mem = build()
    mem.remember("user", "lives_in", "Boston", when=T0)
    mem.remember("user", "lives_in", "Seattle", when=T0 + DAY)
    snap = mem.snapshot()
    assert len(snap) == 2
    for key in ("t_ingested", "t_invalid_at", "t_pruned", "active"):
        assert all(key in f for f in snap)


def test_functional_predicates_default_leaves_domain_predicates_alone():
    """Without declaring them, a domain outside personal chat records zero
    invalidations. This is the configuration trap the ablation quantified."""
    mem = Memory(policy="P2", provider="mock", embedder="hashing")
    mem.remember("South Korea", "head_of_state", "Moon Jae-in", when=T0)
    mem.remember("South Korea", "head_of_state", "Yoon Suk-yeol", when=T0 + DAY)
    assert mem.stats()["invalidated_active"] == 0
