from drift.embeddings import HashingEmbedder, cosine
from drift.memory.graph import BitemporalGraph

DAY = 86400.0


def make_graph():
    return BitemporalGraph(HashingEmbedder())


def test_add_and_search():
    g = make_graph()
    g.add_fact("Alice", "lives_in", "Boston", "Alice: I live in Boston.", t_event=0)
    g.add_fact("Bob", "owns_pet", "puppy Max", "Bob: I adopted a puppy named Max.", t_event=0)
    results = g.search("Where does Alice live?", k=1)
    assert results[0].object == "Boston"


def test_contradiction_closes_valid_window():
    g = make_graph()
    old = g.add_fact("Alice", "lives_in", "Boston", "Alice: I live in Boston.", t_event=0)
    new = g.add_fact("Alice", "lives_in", "Seattle", "Alice: I moved to Seattle.", t_event=10 * DAY)
    assert old.invalidated and old.t_invalid_at == 10 * DAY
    assert not new.invalidated
    assert old.active  # non-lossy: invalidated but not deleted


def test_non_functional_predicates_do_not_contradict():
    g = make_graph()
    a = g.add_fact("Bob", "stated", "likes tea", "Bob: I like tea.", t_event=0)
    g.add_fact("Bob", "stated", "likes coffee", "Bob: I like coffee.", t_event=DAY)
    assert not a.invalidated


def test_prune_and_stats():
    g = make_graph()
    f = g.add_fact("Alice", "stated", "hello", "Alice: hello there friend.", t_event=0)
    g.prune(f.id)
    stats = g.stats()
    assert stats["active_facts"] == 0 and stats["pruned"] == 1
    assert g.search("hello there friend", k=5) == []


def test_snapshot_is_independent():
    g = make_graph()
    f = g.add_fact("Alice", "stated", "x", "Alice: fact one text.", t_event=0)
    snap = g.snapshot()
    g.prune(f.id)
    assert snap.facts[f.id].active


def test_save_load_roundtrip(tmp_path):
    g = make_graph()
    g.add_fact("Alice", "lives_in", "Boston", "Alice: I live in Boston.", t_event=0)
    p = tmp_path / "g.json"
    g.save(p)
    g2 = BitemporalGraph.load(p, HashingEmbedder())
    assert len(g2.facts) == 1
    assert list(g2.facts.values())[0].object == "Boston"


def test_hashing_embedder_similarity_structure():
    e = HashingEmbedder()
    a = e.embed("I live in Boston and love museums")
    b = e.embed("I live in Boston and love museums")
    c = e.embed("quantum entanglement of superconducting qubits")
    assert cosine(a, b) > 0.99
    assert cosine(a, c) < 0.5
