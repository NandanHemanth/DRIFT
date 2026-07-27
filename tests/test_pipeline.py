import json
from pathlib import Path

from drift.embeddings import HashingEmbedder
from drift.memory.extraction import extract_facts
from drift.memory.graph import BitemporalGraph
from drift.pipeline import answer_question, ingest_session, judge_answer, token_f1
from drift.policies import P0NoForgetting, P2ContradictionInvalidation
from drift.providers import BaseProvider, Completion, DiskCache, FallbackProvider, MockProvider

DAY = 86400.0


class GarbageProvider:
    """Always returns text that looks like a JSON list but doesn't parse,
    e.g. a reasoning model that dropped a comma mid-response. Regression
    test for the real crash: an uncaught JSONDecodeError inside extract_facts
    used to kill the entire runner/swarm process instead of just yielding
    no facts for that one session."""

    name = "garbage"

    def complete(self, prompt, system="", temperature=0.0, max_tokens=1024):
        return Completion('[{"subject": "Alice" "predicate": "lives_in"}]', 10, 10)


class AlwaysFailsProvider(BaseProvider):
    name = "always_fails"

    def complete(self, prompt, system="", temperature=0.0, max_tokens=1024):
        raise RuntimeError("simulated quota exhaustion")


class CountingFailProvider(BaseProvider):
    """Fails every call and counts how many times it was actually invoked --
    used to prove the cooldown circuit breaker stops re-trying a provider
    that just failed, instead of paying its retry cost on every call."""

    name = "counting_fail"

    def __init__(self):
        self.calls = 0

    def complete(self, prompt, system="", temperature=0.0, max_tokens=1024):
        self.calls += 1
        raise RuntimeError("simulated quota exhaustion")


def test_extraction_produces_functional_predicates():
    facts = extract_facts(MockProvider(), ["Alice: I live in Boston, the city is great."])
    predicates = {f["predicate"] for f in facts}
    assert "lives_in" in predicates
    lives = next(f for f in facts if f["predicate"] == "lives_in")
    assert lives["object"] == "Boston" and lives["subject"] == "Alice"
    # the generic 'stated' duplicate of the same line is dropped
    assert not any(f["predicate"] == "stated" and f["text"] == lives["text"] for f in facts)


def test_ingest_and_answer_end_to_end():
    g = BitemporalGraph(HashingEmbedder())
    policy = P0NoForgetting()
    provider = MockProvider()
    ingest_session({"time": 0, "lines": ["Alice: I work at Acme Corp, the company makes robotics."]},
                   g, policy, provider)
    result = answer_question("Which company does Alice work at?", g, policy, provider, now=0)
    assert "Acme" in result["answer"]
    assert result["tokens"] > 0


def test_staleness_differentiation_p0_vs_p2():
    """The core thesis mechanism: P0 can answer with superseded facts, P2 cannot."""
    provider = MockProvider()
    sessions = [
        {"time": 0, "lines": ["Alice: I live in Boston, the city is great for museums."]},
        {"time": 25 * DAY, "lines": ["Alice: I moved to Seattle recently and I live downtown."]},
    ]
    answers = {}
    for name, policy in [("P0", P0NoForgetting()), ("P2", P2ContradictionInvalidation())]:
        g = BitemporalGraph(HashingEmbedder())
        for s in sessions:
            ingest_session(s, g, policy, provider)
        answers[name] = answer_question("Which city does Alice live in?", g, policy, provider,
                                        now=25 * DAY)["answer"]
    assert "Boston" in answers["P0"]      # stale answer under append-only memory
    assert "Seattle" in answers["P2"]     # bitemporal filtering fixes it


def test_judge_and_f1():
    provider = MockProvider()
    good = judge_answer("Where does Alice live?", "Seattle", "She lives in Seattle now.", provider)
    bad = judge_answer("Where does Alice live?", "Seattle", "She lives in Boston.", provider)
    assert good["correct"] and not bad["correct"]
    assert token_f1("Seattle", "She lives in Seattle now.") > 0
    assert token_f1("Seattle", "Boston") == 0.0


def test_disk_cache_roundtrip(tmp_path):
    cache = DiskCache(tmp_path)
    key = DiskCache.key("groq", "llama", "hello", 0.0)
    assert cache.get(key) is None
    cache.put(key, {"text": "hi", "pt": 1, "ct": 1})
    assert cache.get(key)["text"] == "hi"


def test_runner_smoke_config_is_valid():
    cfg = json.loads(Path("configs/smoke.json").read_text())
    dataset = json.loads(Path(cfg["dataset"]).read_text())
    assert cfg["policies"] and cfg["models"]
    assert all(c["sessions"] and c["questions"] for c in dataset["conversations"])


def test_extract_facts_survives_malformed_json():
    """A provider whose response can't be parsed as JSON at all (not even via
    the regex-recovered bracket match) must yield an empty LLM-derived fact
    list for that session, not raise -- one bad extraction shouldn't crash a
    whole campaign. Uses a line with no heuristic-matchable pattern (no
    lives_in/works_at/owns_pet/studies phrasing) so the deterministic regex
    upgrade pass -- which runs independently of the LLM's output and should
    still work -- doesn't mask the assertion."""
    facts = extract_facts(GarbageProvider(), ["Alice: My favorite color is blue."])
    assert facts == []


def test_fallback_provider_falls_through_to_working_provider():
    """If the preferred provider is exhausted/dead, FallbackProvider must try
    the next one instead of failing the whole call -- this is the fix for
    every cell dying identically when one free-tier provider's daily quota
    is used up."""
    provider = FallbackProvider([AlwaysFailsProvider(), MockProvider()])
    result = provider.complete("TASK:JUDGE\nQUESTION:\nq\nGOLD:\nSeattle\nANSWER:\nSeattle")
    assert result.text == "CORRECT"


def test_fallback_provider_raises_only_if_all_providers_fail():
    provider = FallbackProvider([AlwaysFailsProvider(), AlwaysFailsProvider()])
    try:
        provider.complete("hi")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "simulated quota exhaustion" in str(e)


def test_fallback_provider_cooldown_skips_a_recently_failed_provider():
    """Regression test for the ~45s-per-call retry tax: once a provider has
    failed once, a *new* FallbackProvider instance built with the same
    provider name must skip it on subsequent calls (within the cooldown
    window) rather than invoking it again and re-paying its retry cost."""
    FallbackProvider._cooldown_until.clear()  # isolate from other tests
    dead = CountingFailProvider()
    dead.name = "test_dead_provider_unique_name"
    good = MockProvider()

    first = FallbackProvider([dead, good], cooldown_seconds=60)
    result = first.complete("TASK:JUDGE\nQUESTION:\nq\nGOLD:\nSeattle\nANSWER:\nSeattle")
    assert result.text == "CORRECT"
    assert dead.calls == 1  # tried once, failed, fell through to the mock

    # A brand-new FallbackProvider wrapping the *same* dead provider object
    # should see it's on cooldown (class-level state) and skip straight to
    # the working one without calling it again.
    second = FallbackProvider([dead, good], cooldown_seconds=60)
    second.complete("TASK:JUDGE\nQUESTION:\nq\nGOLD:\nSeattle\nANSWER:\nSeattle")
    assert dead.calls == 1  # still 1 -- skipped this time, not retried
    FallbackProvider._cooldown_until.clear()


def test_locomo_stratified_sample_keeps_full_sessions_caps_questions():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.download_locomo import stratified_sample

    dataset = {"name": "t", "conversations": [
        {"id": "c0", "sessions": [{"time": 0, "lines": ["a"]}, {"time": 1, "lines": ["b"]}],
         "questions": [{"question": f"q{i}", "answer": "x", "category": cat, "stale_answer": None}
                       for i, cat in enumerate(["single_hop"] * 8 + ["temporal"] * 2)]},
    ]}
    sampled = stratified_sample(dataset, sample_size=5, seed=1)
    assert len(sampled["conversations"][0]["sessions"]) == 2  # full history kept
    nq = sum(len(c["questions"]) for c in sampled["conversations"])
    assert nq <= 6  # capped near the target (rounding may add at most one per category)
    cats = {q["category"] for c in sampled["conversations"] for q in c["questions"]}
    assert "temporal" in cats  # minority category still represented
