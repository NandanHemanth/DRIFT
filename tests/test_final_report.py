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


def test_abstention_is_graded_incorrect_without_the_judge():
    from drift.pipeline import is_abstention, judge_answer

    class Boom:
        def complete(self, *a, **k):
            raise AssertionError("judge must not be called")

    assert is_abstention("I don't know.", "Pius XII")
    assert not is_abstention("I don't know, but memory says Pius XII", "Pius XII")
    assert not is_abstention("Munich", "Säbener Straße")
    assert judge_answer("q", "8", "I don't know.", Boom())["correct"] is False


def test_staleness_needs_the_old_value_without_the_new_one():
    from drift.runner import staleness_hit
    assert staleness_hit("Giuseppe Conte.", "Giuseppe Conte", "Giorgia Meloni")
    assert not staleness_hit("Giorgia Meloni, who replaced Giuseppe Conte.", "Giuseppe Conte", "Giorgia Meloni")
    assert staleness_hit("Giuseppe Conte", "Giuseppe Conte")          # no current value: old rule
    assert not staleness_hit("Giorgia Meloni", "Giuseppe Conte", "Giorgia Meloni")
