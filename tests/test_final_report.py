from analysis.final_report import holm, kendalls_w, mcnemar, restated_stale, spearman


def test_mcnemar_counts_and_p():
    a = [True] * 10 + [False] * 0
    b = [False] * 5 + [True] * 5
    x, y, p = mcnemar(a, b)
    assert (x, y) == (5, 0)
    assert abs(p - 0.0625) < 1e-9


def test_holm_is_monotone_and_capped():
    adj = holm([0.01, 0.04, 0.03])
    assert adj[0] == 0.03 and max(adj) <= 1.0
    assert adj[2] >= adj[0]


def test_rank_agreement():
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-9
    assert abs(kendalls_w([[1, 2, 3], [1, 2, 3], [1, 2, 3]]) - 1) < 1e-9


def test_mquake_restated_questions_are_found():
    flagged = restated_stale("data/mquake_t_sh.json")
    assert "What is the name of the current head of the New York City government?" in flagged
