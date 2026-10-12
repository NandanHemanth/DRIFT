"""Relation normalisation for contradiction detection (P2)."""
from drift.embeddings import make_embedder
from drift.memory.graph import BitemporalGraph
from drift.memory.normalize import entity_key, is_multi_valued, relation_key

EMB = make_embedder("hashing")


def test_relation_variants_share_a_key():
    k = relation_key("head_of_government")
    assert relation_key("is_head_of_government_of") == k
    assert relation_key("head_of_government_of") == k
    assert relation_key("citizenship") == relation_key("citizen_of") == relation_key("is_citizen_of")
    assert relation_key("head_of_state") != k


def test_entity_key():
    assert entity_key("The_Apex Digital") == entity_key("apex digital")


def test_multi_valued_guard():
    assert is_multi_valued("has_meeting") and is_multi_valued("deliverable")
    assert not is_multi_valued("has_appointment") and not is_multi_valued("head_of_government")


def _graph(mode, **kw):
    return BitemporalGraph(EMB, functional_predicates="*", relation_matching=mode, **kw)


def test_exact_mode_is_unchanged_and_misses_variants():
    g = _graph("exact")
    a = g.add_fact("Italy", "head_of_government", "Mario Draghi", "Italy head is Draghi", 1.0)
    g.add_fact("Italy", "is_head_of_government_of", "Giorgia Meloni", "Italy head is Meloni", 2.0)
    assert a.t_invalid_at is None


def test_normalized_mode_catches_variants():
    g = _graph("normalized")
    a = g.add_fact("Italy", "head_of_government", "Mario Draghi", "Italy head is Draghi", 1.0)
    g.add_fact("italy", "is_head_of_government_of", "Giorgia Meloni", "Italy head is Meloni", 2.0)
    assert a.t_invalid_at == 2.0


def test_normalized_mode_keeps_lists():
    g = _graph("normalized")
    a = g.add_fact("Sarah", "has_meeting", "9 AM sync", "Sarah has a 9 AM sync", 1.0)
    g.add_fact("Sarah", "has_meeting", "3 PM debrief", "Sarah has a 3 PM debrief", 1.0)
    assert a.t_invalid_at is None
    b = g.add_fact("User", "has_appointment", "dentist Tuesday", "dentist on Tuesday", 1.0)
    g.add_fact("User", "has_appointment", "dentist Friday", "dentist on Friday", 2.0)
    assert b.t_invalid_at == 2.0


def test_normalized_same_value_is_not_a_contradiction():
    g = _graph("normalized")
    a = g.add_fact("NYC", "head_of_government", "Eric_Adams", "NYC head is Eric Adams", 1.0)
    g.add_fact("NYC", "head_of_government", "Eric Adams", "NYC head is Eric Adams", 2.0)
    assert a.t_invalid_at is None


def test_llm_mode_handles_flipped_direction():
    calls = []

    def judge(new, cands):
        calls.append((new.text, [c.text for c in cands]))
        return [c for c in cands if "Conte" in c.text]

    g = _graph("llm", contradiction_judge=judge)
    a = g.add_fact("Italy", "head_of_government", "Giuseppe Conte", "Italy is led by Conte", 1.0)
    g.add_fact("Giorgia Meloni", "head_of_government", "Italy", "Meloni leads Italy", 2.0)
    assert a.t_invalid_at == 2.0
    assert calls and "Italy is led by Conte" in calls[0][1]


def test_llm_mode_requires_a_judge():
    import pytest
    with pytest.raises(ValueError):
        _graph("llm")


def test_normalized_catches_reversed_direction():
    g = _graph("normalized")
    old = g.add_fact("Jacinda Ardern", "head_of_government_of", "New Zealand",
                     "Jacinda Ardern is head of government of New Zealand.", t_event=1.0)
    g.add_fact("New Zealand", "head_of_government", "Chris Hipkins",
               "The head of government of New Zealand is Chris Hipkins.", t_event=2.0)
    assert old.invalidated


def test_reversed_restatement_is_not_a_contradiction():
    g = _graph("normalized")
    old = g.add_fact("New Zealand", "head_of_government", "Chris Hipkins", "a", t_event=1.0)
    g.add_fact("Chris Hipkins", "head_of_government_of", "New Zealand", "b", t_event=2.0)
    assert not old.invalidated


def test_shared_object_alone_is_not_a_contradiction():
    g = _graph("normalized")
    old = g.add_fact("Dom Mintoff", "citizen_of", "Malta", "a", t_event=1.0)
    g.add_fact("Joseph Muscat", "citizen_of", "Malta", "b", t_event=2.0)
    assert not old.invalidated


def test_exact_mode_ignores_reversed_direction():
    g = _graph("exact")
    old = g.add_fact("Jacinda Ardern", "head_of_government_of", "New Zealand", "a", t_event=1.0)
    g.add_fact("New Zealand", "head_of_government", "Chris Hipkins", "b", t_event=2.0)
    assert not old.invalidated
