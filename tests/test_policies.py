from drift.embeddings import HashingEmbedder
from drift.memory.graph import BitemporalGraph
from drift.policies import (
    P1TTLDecay, P2ContradictionInvalidation, P3NoveltyGate, P4LLMConsolidation, make_policy,
)
from drift.providers import MockProvider

DAY = 86400.0


def make_graph():
    return BitemporalGraph(HashingEmbedder())


def test_p1_ttl_prunes_old_facts():
    g = make_graph()
    g.add_fact("Alice", "stated", "old", "Alice: something from long ago.", t_event=0)
    g.add_fact("Alice", "stated", "new", "Alice: something from yesterday.", t_event=40 * DAY)
    P1TTLDecay(ttl_days=30).after_session(g, MockProvider(), now=40 * DAY)
    stats = g.stats()
    assert stats["active_facts"] == 1 and stats["pruned"] == 1


def test_p2_filters_invalidated_at_retrieval_and_prunes_after_grace():
    g = make_graph()
    old = g.add_fact("Alice", "lives_in", "Boston", "Alice: I live in Boston.", t_event=0)
    g.add_fact("Alice", "lives_in", "Seattle", "Alice: I moved to Seattle.", t_event=10 * DAY)
    p2 = P2ContradictionInvalidation(grace_days=7)
    retrieved = p2.on_retrieve(g.search("Where does Alice live?", k=5), now=10 * DAY)
    assert all(not f.invalidated for f in retrieved)
    p2.after_session(g, MockProvider(), now=20 * DAY)  # 10 days past invalidation > 7-day grace
    assert not g.facts[old.id].active


def test_p3_novelty_gate_rejects_duplicates():
    g = make_graph()
    p3 = P3NoveltyGate(tau=0.9)
    fact = {"subject": "Bob", "predicate": "stated", "object": "guitar",
            "text": "Bob: I play guitar in a local band."}
    assert p3.on_write(fact, g)
    g.add_fact(fact["subject"], fact["predicate"], fact["object"], fact["text"], t_event=0)
    assert not p3.on_write(dict(fact), g)  # exact duplicate rejected
    assert g.write_rejections == 1
    novel = {"subject": "Bob", "predicate": "stated", "object": "cooking",
             "text": "Bob: I started a sourdough baking project."}
    assert p3.on_write(novel, g)


def test_p4_consolidation_merges_near_duplicates():
    g = make_graph()
    g.add_fact("A", "stated", "x", "Alice: my favorite hobby is painting landscapes.", t_event=0)
    g.add_fact("A", "stated", "x", "Alice: my favorite hobby is painting landscapes.", t_event=DAY)
    g.add_fact("B", "stated", "y", "Bob: I am studying biology at Harvard.", t_event=DAY)
    p4 = P4LLMConsolidation(every_n=1)
    p4.after_session(g, MockProvider(), now=DAY)
    assert g.stats()["active_facts"] == 2  # duplicate merged, distinct fact kept


def test_make_policy_parses_kwargs():
    p = make_policy("P1:ttl_days=14")
    assert isinstance(p, P1TTLDecay) and abs(p.ttl - 14 * DAY) < 1


def test_nomem_baseline_retrieves_nothing():
    """NOMEM: floor baseline - memory exists but retrieval is disabled."""
    from drift.policies import make_policy
    from drift.memory.graph import BitemporalGraph
    from drift.embeddings import make_embedder
    g = BitemporalGraph(make_embedder("hashing"))
    g.add_fact("Alice", "lives_in", "Boston", "Alice lives in Boston", t_event=0)
    p = make_policy("NOMEM")
    assert p.on_write({"text": "anything"}, g) is True          # writes still land
    assert p.on_retrieve(g.search("Where does Alice live?"), now=0.0) == []


def test_p5_topology_consolidation_is_time_blind():
    """P5 resolves contradictions by structural support, never by time.

    With equal support it keeps ONE fact per (subject, predicate) - but unlike
    P2 it cannot know which is current. This is the designed ablation gap.
    """
    from drift.policies import make_policy
    from drift.memory.graph import BitemporalGraph
    from drift.embeddings import make_embedder
    g = BitemporalGraph(make_embedder("hashing"))
    g.add_fact("Alice", "lives_in", "Boston", "Alice lives in Boston", t_event=0)
    g.add_fact("Alice", "lives_in", "Seattle", "Alice lives in Seattle", t_event=100)
    # corroborate the STALE fact -> structural support favors Boston
    g.add_fact("Alice", "stated", "Boston museums", "Alice loves Boston museums", t_event=50)
    g.add_fact("Alice", "stated", "Boston walks", "Alice walks around Boston", t_event=60)
    p = make_policy("P5:min_keep=1")
    p.after_session(g, provider=None, now=200.0)
    lives = [f for f in g.facts.values() if f.active and f.predicate == "lives_in"]
    assert len(lives) == 1                      # consolidated to one fact
    assert lives[0].object == "Boston"          # ...but kept the STALE one (time-blind)


def test_p5_registry_and_spec():
    from drift.policies import make_policy
    assert make_policy("P5").name == "P5_topology_consolidation"
    assert make_policy("P5:min_keep=3").min_keep == 3


def test_p4_survives_unparseable_llm_response():
    """Regression test: a malformed/truncated consolidation response must not
    crash after_session (previously: UnboundLocalError on `decision`)."""
    from drift.policies import make_policy
    from drift.memory.graph import BitemporalGraph
    from drift.embeddings import make_embedder
    from drift.providers import Completion

    class GarbageProvider:
        def complete(self, *a, **k):
            return Completion(text="not json at all, no braces here", prompt_tokens=1, completion_tokens=1)

    g = BitemporalGraph(make_embedder("hashing"))
    g.add_fact("Alice", "stated", "loves tea", "Alice loves tea", t_event=0)
    p = make_policy("P4:every_n=1")
    p.after_session(g, GarbageProvider(), now=1.0)  # must not raise
    assert sum(1 for f in g.facts.values() if f.active) == 1  # nothing dropped
