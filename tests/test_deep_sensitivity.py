"""The deep sensitivity sweep must reproduce the runner's prompts exactly.

If the batched retrieval in analysis.deep_sensitivity drifted from
BitemporalGraph.search by even one tie-break, every end-to-end number in the
sweep would describe a pipeline that was never run. These tests pin it.
"""
import json
from pathlib import Path

import numpy as np

from analysis.deep_sensitivity import (anova3, build_graph, contexts_for_question, direction,
                                       full_grid, gold_needle)
from drift.embeddings import make_embedder
from drift.pipeline import ANSWER_PROMPT, answer_question, render_fact
from drift.providers import Completion, MockProvider

ROOT = Path(__file__).resolve().parents[1]


class Capture:
    name, model = "capture", "capture"

    def __init__(self):
        self.prompts = []

    def complete(self, prompt, system="", temperature=0.0, max_tokens=1024):
        self.prompts.append(prompt)
        return Completion("x", 1, 1)


def test_batched_contexts_match_runner_prompts():
    data = json.loads((ROOT / "data/synthetic_smoke.json").read_text())
    emb = make_embedder("hashing")
    grid = full_grid([0.1, 0.3, 0.6, 1.0])
    for pol in ("P0", "P2"):
        for convo in data["conversations"]:
            graph, policy, t_last = build_graph(convo, pol, {}, emb, MockProvider())
            for q in convo["questions"]:
                ctxs = contexts_for_question(graph, policy, q["question"], t_last, 8, grid)
                for w, (_, post) in zip(grid, ctxs):
                    block = "\n".join(render_fact(f) for f in post) or "(no relevant memory)"
                    ours = ANSWER_PROMPT.format(memory=block, question=q["question"])
                    graph.weights = w
                    cap = Capture()
                    answer_question(q["question"], graph, policy, cap, k=8, now=t_last)
                    assert cap.prompts[0] == ours, (pol, w, q["question"])


def test_scale_invariance_identity():
    assert direction((0.2, 0.2, 0.2)) == direction((0.5, 0.5, 0.5))
    assert direction((0.6, 0.3, 0.1)) != direction((0.3, 0.6, 0.1))
    grid = full_grid([i / 10 for i in range(1, 11)])
    assert len(grid) == 1000
    assert len({direction(w) for w in grid}) == 841


def test_anova_recovers_pure_main_effect():
    v = np.arange(10, dtype=float)
    Y = v[:, None, None] + np.zeros((10, 10, 10))
    fr = anova3(Y)
    assert abs(fr["semantic"] - 1.0) < 1e-9
    assert all(abs(fr[k]) < 1e-9 for k in fr if k != "semantic")


def test_anova_detects_interaction():
    v = np.arange(10, dtype=float) - 4.5
    Y = v[:, None, None] * v[None, :, None] + np.zeros((10, 10, 10))
    fr = anova3(Y)
    assert fr["semantic x lexical"] > 0.99


def test_gold_needle_recovers_short_value_from_sentence():
    q = {"answer": "The call is scheduled for 10 AM, as confirmed.", "stale_answer": "3 PM"}
    assert gold_needle(q) == "10 AM"
    assert gold_needle({"answer": "Seattle"}) == "Seattle"


def test_rule_grader_only_decides_clear_cases():
    from analysis.deep_sensitivity import rule_grade
    assert rule_grade("I don't know.", "Seattle", "Boston") is False
    assert rule_grade("Seattle", "Seattle", "Boston") is True
    # mentions the superseded value too: ambiguous, goes to the judge
    assert rule_grade("Boston, then Seattle", "Seattle", "Boston") is None
    # long answer reciting history: ambiguous
    long = "The city has changed multiple times over the years; it was once Seattle " * 2
    assert rule_grade(long, "Seattle", "Boston") is None
    # no gold value and not a refusal: ambiguous (could be a paraphrase)
    assert rule_grade("Hochul", "Kathy Hochul", "Andrew Cuomo") is None


def test_date_order_makes_prompt_depend_only_on_the_set():
    from analysis.deep_sensitivity import order_context

    class F:
        def __init__(self, fid, t):
            self.id, self.t_valid_start = fid, t
    a, b, c = F("a", 3.0), F("b", 1.0), F("c", 1.0)
    pos = {"a": 0, "b": 1, "c": 2}
    one = order_context([a, c, b], "date", pos)
    two = order_context([b, a, c], "date", pos)
    assert [f.id for f in one] == [f.id for f in two] == ["b", "c", "a"]
    assert [f.id for f in order_context([a, c, b], "rank", pos)] == ["a", "c", "b"]


def test_strip_thinking():
    from analysis.deep_sensitivity import strip_thinking
    assert strip_thinking("<think>\nhmm, maybe Boston\n</think>\n\nSeattle") == "Seattle"
    assert strip_thinking("Seattle") == "Seattle"


def test_extra_body_changes_cache_key_and_request(tmp_path, monkeypatch):
    """Pinning an upstream host must not share cache entries with an unpinned call."""
    import json as _json
    from drift import providers as P
    monkeypatch.setenv("OLLAMA_API_KEY", "x")
    seen = []

    class Resp:
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return _json.dumps({"choices": [{"message": {"content": "", "reasoning": "thinking..."}}],
                                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()

    def fake_urlopen(req, timeout=None):
        seen.append(_json.loads(req.data))
        return Resp(req.data)

    monkeypatch.setattr(P.urllib.request, "urlopen", fake_urlopen)
    p = P.make_provider("ollama:m", str(tmp_path))
    p.reasoning_fallback = False
    a = p.complete("q")
    assert a.text == ""                      # no thought trace passed off as the answer
    p.extra_body = {"provider": {"order": ["X"]}}
    p.complete("q")                          # different key -> second real request
    assert len(seen) == 2 and seen[1]["provider"] == {"order": ["X"]}
    p.complete("q")                          # now cached
    assert len(seen) == 2


def test_rule_grader_accepts_one_plain_sentence():
    from analysis.deep_sensitivity import rule_grade
    assert rule_grade("The current head of the Italy government is Giorgia Meloni.",
                      "Giorgia Meloni", "Mario Draghi") is True
    long = ("Rishi Sunak (as of 2024-01-22) and Charles, Prince of Wales (as of 2024-02-07), "
            "according to the memory entries provided.")
    assert rule_grade(long, "Rishi Sunak", "Boris Johnson") is None
