"""BM25 lexical signal: range, rarity weighting, and the default is unchanged."""
import pytest

from drift.embeddings import HashingEmbedder
from drift.memory.graph import BitemporalGraph, bm25_scores


def test_scores_in_unit_range_top_is_one():
    docs = {"a": ["head", "government", "new", "zealand"], "b": ["head", "government", "japan"], "c": ["cat"]}
    s = bm25_scores({"new", "zealand", "head"}, docs)
    assert max(s.values()) == pytest.approx(1.0)
    assert all(0.0 <= v <= 1.0 for v in s.values())
    assert s["c"] == 0.0


def test_rare_word_outweighs_common_word():
    docs = {f"common{i}": ["the", "head"] for i in range(20)}
    docs["rare"] = ["the", "zealand"]
    s = bm25_scores({"the", "head", "zealand"}, docs)
    # one rare match beats one common match plus a very common word
    assert s["rare"] > s["common0"]


def test_no_match_gives_zero_everywhere():
    s = bm25_scores({"zzz"}, {"a": ["x"], "b": ["y"]})
    assert set(s.values()) == {0.0}


def _graph(lexical):
    g = BitemporalGraph(HashingEmbedder(), functional_predicates="*", lexical=lexical)
    g.add_fact("New Zealand", "head_of_government", "Chris Hipkins",
               "The head of government of New Zealand is Chris Hipkins.", t_event=2.0)
    g.add_fact("Japan", "head_of_government", "Fumio Kishida",
               "The head of government of Japan is Fumio Kishida.", t_event=1.0)
    return g


def test_default_is_overlap_and_bm25_ranks_subject_first():
    assert _graph(None).lexical == "overlap"
    q = "Who is the current head of the New Zealand government?"
    top = _graph("bm25").search(q, k=1)[0]
    assert "New Zealand" in top.text


def test_unknown_lexical_rejected():
    with pytest.raises(ValueError):
        BitemporalGraph(HashingEmbedder(), lexical="tfidf")


def test_snapshot_keeps_lexical():
    g = _graph("bm25")
    assert g.snapshot().lexical == "bm25"
