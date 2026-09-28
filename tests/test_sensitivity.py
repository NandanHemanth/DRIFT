"""Offline tests for the hyperparameter sensitivity harness.

These run with the hashing embedder and no network, like the rest of the suite.
The point of them is that a sensitivity result is only worth citing in a thesis
if the machinery producing it is itself pinned by tests.
"""
from __future__ import annotations

from analysis.sensitivity import (
    MemoEmbedder,
    measure,
    rank_stability,
    simplex_grid,
)
from drift.embeddings import HashingEmbedder
from drift.memory.graph import DEFAULT_RETRIEVAL_WEIGHTS, BitemporalGraph
from drift.policies import make_policy

DAY = 86400.0


def build_graph(policy_spec="P0"):
    """Alice moves Boston -> Seattle; Bob's job never changes."""
    graph = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
    policy = make_policy(policy_spec)
    graph.add_fact("alice", "lives_in", "Boston", "alice lives in Boston", t_event=0.0)
    graph.add_fact("bob", "works_at", "Acme", "bob works at Acme", t_event=0.0)
    graph.add_fact("alice", "lives_in", "Seattle", "alice lives in Seattle", t_event=40 * DAY)
    return graph, policy


QUESTIONS = [{"question": "where does alice live", "answer": "Seattle", "stale_answer": "Boston"}]


def test_default_weights_unchanged():
    """The published weighting is a fixed constant; changing it silently would
    invalidate every number in the thesis."""
    assert DEFAULT_RETRIEVAL_WEIGHTS == (0.6, 0.3, 0.1)
    assert BitemporalGraph(HashingEmbedder()).weights == (0.6, 0.3, 0.1)


def test_search_weights_override_does_not_mutate_graph():
    graph, _ = build_graph()
    graph.search("where does alice live", k=3, weights=(0.0, 0.0, 1.0))
    assert graph.weights == DEFAULT_RETRIEVAL_WEIGHTS


def test_simplex_grid_is_a_simplex():
    grid = simplex_grid(0.1)
    assert len(grid) == 66
    assert all(abs(sum(w) - 1.0) < 1e-9 for w in grid)
    assert DEFAULT_RETRIEVAL_WEIGHTS in grid


def test_memo_embedder_calls_inner_once_per_string():
    class Counting:
        name = "counting"

        def __init__(self):
            self.calls = 0

        def embed(self, text):
            self.calls += 1
            return [1.0, 0.0]

    inner = Counting()
    memo = MemoEmbedder(inner)
    for _ in range(5):
        memo.embed("same text")
    assert inner.calls == 1


def test_measure_separates_gold_support_from_stale_exposure():
    """P0 keeps the superseded fact, so it is exposed; P2 excludes it."""
    graph_p0, policy_p0 = build_graph("P0")
    graph_p2, policy_p2 = build_graph("P2")
    now = 40 * DAY
    m0 = measure(graph_p0, policy_p0, QUESTIONS, k=5, weights=DEFAULT_RETRIEVAL_WEIGHTS, now=now)
    m2 = measure(graph_p2, policy_p2, QUESTIONS, k=5, weights=DEFAULT_RETRIEVAL_WEIGHTS, now=now)
    assert m0["gold_support"] == 1.0 and m2["gold_support"] == 1.0
    assert m0["stale_exposure"] == 1.0
    assert m2["stale_exposure"] == 0.0
    assert m2["clean"] == 1.0 and m0["clean"] == 0.0


def test_grace_period_only_affects_wasted_slots_not_correctness():
    """The defensible claim about grace_days: it controls how many retrieval
    slots a superseded fact keeps occupying, never whether one is served."""
    now = 40 * DAY
    results = {}
    for grace in (0.0, 30.0):
        graph = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
        policy = make_policy(f"P2:grace_days={grace}")
        graph.add_fact("alice", "lives_in", "Boston", "alice lives in Boston", t_event=0.0)
        graph.add_fact("alice", "lives_in", "Seattle", "alice lives in Seattle", t_event=10 * DAY)
        policy.after_session(graph, None, now=now)
        results[grace] = measure(graph, policy, QUESTIONS, k=5,
                                 weights=DEFAULT_RETRIEVAL_WEIGHTS, now=now)
    assert results[0.0]["stale_exposure"] == results[30.0]["stale_exposure"] == 0.0
    assert results[0.0]["clean"] == results[30.0]["clean"] == 1.0
    # Short grace prunes the superseded fact, so it stops consuming a slot.
    assert results[0.0]["wasted_slots"] < results[30.0]["wasted_slots"]


def test_rank_stability_reports_reference_order_and_reversals():
    rows = [
        {"policy": "P2", "k": 25, "w_sem": 0.6, "w_lex": 0.3, "w_rec": 0.1, "clean": 0.9},
        {"policy": "P5", "k": 25, "w_sem": 0.6, "w_lex": 0.3, "w_rec": 0.1, "clean": 0.5},
        {"policy": "P2", "k": 25, "w_sem": 0.0, "w_lex": 0.0, "w_rec": 1.0, "clean": 0.4},
        {"policy": "P5", "k": 25, "w_sem": 0.0, "w_lex": 0.0, "w_rec": 1.0, "clean": 0.6},
    ]
    stab = rank_stability(rows, published=(0.6, 0.3, 0.1))
    assert stab["reference_order"] == ["P2", "P5"]
    assert stab["settings"] == 2
    assert stab["pairwise"]["P2 > P5"]["held"] == 1
    assert stab["pairwise"]["P2 > P5"]["reversed"] == 1


# --------------------------------------------------------------- fusion methods

def test_default_fusion_is_the_published_weighted_combination():
    g = BitemporalGraph(HashingEmbedder())
    assert g.fusion == "weighted"


def test_rrf_ignores_weights_entirely():
    """The point of rank fusion is that there is no weighting to get wrong."""
    graph, _ = build_graph()
    a = [f.id for f in graph.search("where does alice live", k=3, fusion="rrf")]
    b = [f.id for f in graph.search("where does alice live", k=3, fusion="rrf",
                                    weights=(0.0, 0.0, 1.0))]
    assert a == b


def test_rrf_and_weighted_can_disagree():
    """If they always agreed the comparison would not be worth running."""
    graph, _ = build_graph()
    q = "where does alice live"
    weighted = [f.id for f in graph.search(q, k=4, fusion="weighted")]
    rrf = [f.id for f in graph.search(q, k=4, fusion="rrf")]
    assert set(weighted) == set(rrf)          # same candidates at full depth
    assert weighted != rrf                    # different order


def test_unknown_fusion_is_rejected():
    graph, _ = build_graph()
    try:
        graph.search("anything", fusion="banana")
    except ValueError as e:
        assert "banana" in str(e)
    else:
        raise AssertionError("expected ValueError for an unknown fusion mode")


def test_snapshot_preserves_fusion():
    g = BitemporalGraph(HashingEmbedder(), None, None, "rrf")
    assert g.snapshot().fusion == "rrf"


# ------------------------------------------------------- response surface

from analysis.retrieval_surface import (  # noqa: E402
    fit_mixture,
    invariance_check,
    pareto_front,
)


def _surface_rows():
    """A grid where gold rises with semantic weight and falls with recency."""
    rows = []
    for i in range(11):
        for j in range(11 - i):
            k = 10 - i - j
            w = (i / 10, j / 10, k / 10)
            rows.append({
                "policy": "P2", "w_sem": w[0], "w_lex": w[1], "w_rec": w[2],
                "gold_support": 1.0 * w[0] + 0.9 * w[1] + 0.2 * w[2],
                "stale_exposure": 0.4 * w[0] + 0.4 * w[1] + 0.0 * w[2],
                "est_ctx_tokens": 350 * w[0] + 360 * w[1] + 420 * w[2],
                "active_facts": 357, "pruned": 25, "invalidated_active": 34,
            })
    return rows


def test_mixture_coefficients_recover_the_corner_responses():
    """On a perfectly linear surface the Scheffe coefficients are the corners."""
    rows = _surface_rows()
    pts = [(r["w_sem"], r["w_lex"], r["w_rec"]) for r in rows]
    fit = fit_mixture(pts, [r["gold_support"] for r in rows])
    c = fit["coefficients"]
    assert abs(c["semantic"] - 1.0) < 1e-6
    assert abs(c["lexical"] - 0.9) < 1e-6
    assert abs(c["recency"] - 0.2) < 1e-6
    assert fit["r2"] > 0.999


def test_invariance_check_flags_pre_retrieval_quantities():
    inv = invariance_check(_surface_rows())
    assert inv["active_facts"]["invariant"] is True
    assert inv["pruned"]["invariant"] is True


def test_invariance_check_detects_variation():
    rows = _surface_rows()
    rows[0] = {**rows[0], "active_facts": 999}
    assert invariance_check(rows)["active_facts"]["invariant"] is False


def test_pareto_front_excludes_dominated_points():
    rows = [
        {"w_sem": 1.0, "w_lex": 0.0, "w_rec": 0.0,
         "gold_support": 1.0, "stale_exposure": 0.1, "est_ctx_tokens": 300},
        # strictly worse on every axis, so it must be dominated
        {"w_sem": 0.0, "w_lex": 1.0, "w_rec": 0.0,
         "gold_support": 0.8, "stale_exposure": 0.2, "est_ctx_tokens": 400},
        # better on stale, worse on gold: a genuine trade-off, so it survives
        {"w_sem": 0.0, "w_lex": 0.0, "w_rec": 1.0,
         "gold_support": 0.5, "stale_exposure": 0.0, "est_ctx_tokens": 350},
    ]
    front = pareto_front(rows)
    assert len(front) == 2
    assert all(r["gold_support"] != 0.8 for r in front)


from analysis.retrieval_surface import (  # noqa: E402
    cox_direction,
    hypothesis_stability,
)


def test_cox_direction_stays_on_the_simplex():
    """Every point produced must still be a valid mixture."""
    for comp in range(3):
        for _, w in cox_direction((0.6, 0.3, 0.1), comp):
            assert abs(sum(w) - 1.0) < 1e-9
            assert all(v >= -1e-12 for v in w)


def test_cox_direction_holds_the_others_in_proportion():
    """Away from the endpoints, the untouched pair keeps its original ratio."""
    ref = (0.6, 0.3, 0.1)
    for _, w in cox_direction(ref, 0)[1:-1]:
        assert abs(w[1] / w[2] - ref[1] / ref[2]) < 1e-9


def test_cox_direction_spans_the_full_range():
    trace = cox_direction((0.6, 0.3, 0.1), 2)
    assert trace[0][1][2] == 0.0
    assert abs(trace[-1][1][2] - 1.0) < 1e-9


def test_hypothesis_stability_counts_reversals():
    rows = []
    for i, w in enumerate([(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]):
        # P2 wins the first two settings on clean and loses the third
        for pol, clean in (("P2", [0.9, 0.8, 0.1][i]), ("P5", [0.5, 0.5, 0.5][i])):
            rows.append({"policy": pol, "w_sem": w[0], "w_lex": w[1], "w_rec": w[2],
                         "gold_support": 1.0, "stale_exposure": 0.1,
                         "clean": clean, "est_ctx_tokens": 350})
    stab = {r["outcome"]: r for r in hypothesis_stability(rows) if r["comparison"] == "P2 vs P5"}
    assert stab["clean"]["holds"] == 2
    assert stab["clean"]["reversed"] == 1
    assert stab["clean"]["settings"] == 3
    # diagnostics must not appear in a hypothesis comparison
    assert "wasted_slots" not in stab
