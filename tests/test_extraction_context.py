"""Zep-style extraction context: earlier lines are shown, never extracted."""
from drift.embeddings import HashingEmbedder
from drift.memory import extraction
from drift.memory.extraction import build_prompt, extract_facts, EXTRACTION_PROMPT
from drift.memory.graph import BitemporalGraph
from drift.pipeline import ingest_session
from drift.policies import make_policy
from drift.providers import MockProvider


class Recorder:
    """Records prompts and returns no facts."""
    name = "rec"

    def __init__(self):
        self.prompts = []

    def complete(self, prompt, system="", temperature=0.0, max_tokens=1024):
        from drift.providers import Completion
        self.prompts.append(prompt)
        return Completion("[]", 1, 1)


def test_no_context_prompt_is_unchanged():
    lines = ["user: I live in Paris."]
    assert build_prompt(lines) == EXTRACTION_PROMPT.format(text=lines[0])
    assert build_prompt(lines, []) == EXTRACTION_PROMPT.format(text=lines[0])


def test_context_is_shown_before_text():
    p = build_prompt(["user: Saturday instead."], ["user: Lunch is on Friday."])
    assert "PREVIOUS_MESSAGES:\nuser: Lunch is on Friday.\nTEXT:\nuser: Saturday instead." in p


def test_mock_extracts_from_text_only():
    mock = MockProvider()
    facts = extract_facts(mock, ["user: I live in Berlin."], ["user: I moved to Paris."])
    objs = {f["object"].lower() for f in facts}
    assert "paris" not in objs
    assert "berlin" in objs


def test_ingest_passes_last_n_lines_per_graph():
    rec = Recorder()
    old = extraction.CONTEXT_LINES
    extraction.CONTEXT_LINES = 2
    try:
        g = BitemporalGraph(HashingEmbedder())
        pol = make_policy("P0")
        ingest_session({"time": 1.0, "lines": ["a: one", "a: two", "a: three"]}, g, pol, rec)
        ingest_session({"time": 2.0, "lines": ["a: four"]}, g, pol, rec)
        assert "PREVIOUS_MESSAGES" not in rec.prompts[0]          # nothing earlier yet
        assert "PREVIOUS_MESSAGES:\na: two\na: three\nTEXT:\na: four" in rec.prompts[1]
        g2 = BitemporalGraph(HashingEmbedder())                    # new conversation: reset
        ingest_session({"time": 3.0, "lines": ["b: five"]}, g2, pol, rec)
        assert "PREVIOUS_MESSAGES" not in rec.prompts[2]
    finally:
        extraction.CONTEXT_LINES = old


def test_context_off_by_default():
    rec = Recorder()
    g = BitemporalGraph(HashingEmbedder())
    pol = make_policy("P0")
    ingest_session({"time": 1.0, "lines": ["a: one"]}, g, pol, rec)
    ingest_session({"time": 2.0, "lines": ["a: two"]}, g, pol, rec)
    assert all("PREVIOUS_MESSAGES" not in p for p in rec.prompts)
