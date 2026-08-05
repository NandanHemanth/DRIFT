import json
from pathlib import Path

from drift.embeddings import HashingEmbedder
from drift.memory.extraction import extract_facts
from drift.memory.graph import BitemporalGraph
from drift.pipeline import answer_question, ingest_session, judge_answer, token_f1
from drift.policies import P0NoForgetting, P2ContradictionInvalidation
from drift.providers import (
    BaseProvider, Completion, DiskCache, FallbackProvider, MockProvider, OpenAICompatProvider,
)

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


def test_ollama_preset_needs_no_api_key():
    """The local Ollama provider (used for the judge role, the single
    highest-call-volume role in the whole campaign) must construct without
    an API key -- Ollama's server doesn't check the Authorization header."""
    provider = OpenAICompatProvider("ollama", "gpt-oss:20b")
    assert provider.api_key  # placeholder, non-empty, never raises
    assert provider.base_url == "http://localhost:11434/v1"


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


def test_render_fact_surfaces_valid_time():
    """The bitemporal fields must reach the answer prompt: before this, only
    f.text was sent, so 'when did X happen' was unanswerable by construction."""
    from drift.pipeline import render_fact
    g = BitemporalGraph(HashingEmbedder())
    f = g.add_fact("Alice", "lives_in", "Boston", "Alice: I live in Boston.",
                   t_event=1_684_000_000.0)
    rendered = render_fact(f)
    assert rendered.startswith("[2023-05-13]")
    assert "Alice: I live in Boston." in rendered
    assert "superseded" not in rendered


def test_render_fact_marks_superseded():
    g = BitemporalGraph(HashingEmbedder())
    g.add_fact("Alice", "lives_in", "Boston", "Alice: I live in Boston.",
               t_event=1_684_000_000.0)
    g.add_fact("Alice", "lives_in", "Seattle", "Alice: I moved to Seattle.",
               t_event=1_686_000_000.0)
    from drift.pipeline import render_fact
    old = next(f for f in g.facts.values() if f.object == "Boston")
    assert old.invalidated
    assert "superseded" in render_fact(old)


def test_render_fact_tolerates_zero_timestamp():
    """Synthetic datasets use t=0 sentinels; those must not emit a 1970 date."""
    from drift.pipeline import render_fact
    g = BitemporalGraph(HashingEmbedder())
    f = g.add_fact("Bob", "likes", "tea", "Bob: I like tea.", t_event=0.0)
    assert render_fact(f) == "Bob: I like tea."


def test_ku_builder_parses_reasoning_model_replies():
    """gpt-oss:20b (the default annotator) emits a thought trace and puts the
    answer last; taking the first line silently zeroed out every annotation."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from build_longmemeval_ku import clean_stale

    reasoning = ("We need the old value. Earlier they said 27:12.\n"
                 "The current answer is 25:50.\n27:12")
    assert clean_stale(reasoning, "25:50") == "27:12"
    assert clean_stale("<think>hmm</think>\nthree", "four") == "three"
    assert clean_stale("Answer: $350,000", "$400,000") == "$350,000"
    # empty content (reasoning ate the whole token budget) must not annotate
    assert clean_stale("", "25:50") is None


def test_ku_builder_rejects_ambiguous_stale_values():
    """staleness_hit is a substring test, so bare polarity tokens or a restated
    gold answer would manufacture false positives."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from build_longmemeval_ku import clean_stale

    assert clean_stale("No.", "Yes.") is None          # ambiguous polarity
    assert clean_stale("four", "four") is None          # same as gold
    assert clean_stale("NONE", "four") is None
    assert clean_stale("a" * 80, "four") is None        # too long to ever match
    assert clean_stale("$350,000", "$400,000") == "$350,000"   # good value kept


def test_ku_builder_keeps_all_evidence_sessions_when_budgeting():
    """Capping distractors must never drop a session that carries the answer."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from build_longmemeval_ku import budget_sessions

    item = {"question_id": "q1",
            "haystack_session_ids": [f"s{i}" for i in range(20)],
            "answer_session_ids": ["s3", "s17"]}
    sessions = [{"time": float(i), "lines": [f"line {i}"]} for i in range(20)]
    out = budget_sessions(item, sessions, max_sessions=5, seed=42)
    assert len(out) == 5
    kept = {s["lines"][0] for s in out}
    assert "line 3" in kept and "line 17" in kept       # evidence survives
    assert out == sorted(out, key=lambda s: s["time"])  # stays time-ordered


def test_cache_key_separates_different_max_tokens():
    """A reasoning model given 32 tokens returns a truncated trace and given 512
    returns the answer -- those must not share a cache entry, or raising the
    budget silently replays the response generated under the old one."""
    from drift.providers import DiskCache
    a = DiskCache.key("ollama", "gpt-oss:20b", "p", 0.0, max_tokens=32)
    b = DiskCache.key("ollama", "gpt-oss:20b", "p", 0.0, max_tokens=512)
    assert a != b


def test_cache_key_stable_for_default_max_tokens():
    """Existing caches must stay warm: keys for default-budget calls (extraction,
    answering, judging) are unchanged whether or not max_tokens is passed."""
    from drift.providers import DiskCache
    omitted = DiskCache.key("nvidia", "m", "p", 0.0)
    explicit = DiskCache.key("nvidia", "m", "p", 0.0, max_tokens=DiskCache.DEFAULT_MAX_TOKENS)
    assert omitted == explicit


def test_ku_builder_extracts_inline_reasoning_conclusion():
    """gpt-oss states its conclusion inside the sentence rather than on its own
    line: '...So old value is "three".' Taking the whole line would trip the
    length guard and drop the item."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from build_longmemeval_ku import clean_stale

    assert clean_stale('We need the old value. So old value is "three".', "four") == "three"
    assert clean_stale("The old value is $350,000", "$400,000") == "$350,000"
    assert clean_stale("previous value was Chicago", "the suburbs") == "Chicago"
    # genuinely truncated mid-quote -> refuse rather than emit a fragment
    assert clean_stale('The earlier message says 27:12. So old value is "27:', "25:50") is None


def test_functional_predicates_default_is_domain_specific():
    """The default set only covers personal-life predicates, so contradiction is
    a silent no-op on any other domain -- the reason P2 looked inert on a
    fact-consolidation corpus."""
    g = BitemporalGraph(HashingEmbedder())
    g.add_fact("goaltender", "associated_sport", "ice hockey", "a", t_event=0.0)
    g.add_fact("goaltender", "associated_sport", "pesapallo", "b", t_event=100.0)
    assert g.stats()["invalidated_active"] == 0


def test_functional_predicates_wildcard_enables_contradiction():
    g = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
    g.add_fact("goaltender", "associated_sport", "ice hockey", "a", t_event=0.0)
    g.add_fact("goaltender", "associated_sport", "pesapallo", "b", t_event=100.0)
    assert g.stats()["invalidated_active"] == 1
    old = next(f for f in g.facts.values() if f.object == "ice hockey")
    assert old.invalidated and old.t_invalid_at == 100.0


def test_functional_predicates_explicit_set():
    g = BitemporalGraph(HashingEmbedder(), functional_predicates={"associated_sport"})
    g.add_fact("goaltender", "associated_sport", "ice hockey", "a", t_event=0.0)
    g.add_fact("goaltender", "associated_sport", "pesapallo", "b", t_event=100.0)
    g.add_fact("x", "unlisted_pred", "one", "c", t_event=0.0)
    g.add_fact("x", "unlisted_pred", "two", "d", t_event=100.0)
    assert g.stats()["invalidated_active"] == 1   # only the listed predicate


def test_snapshot_preserves_functional_predicates():
    g = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
    assert g.snapshot().functional_predicates == "*"


def test_runner_functional_predicates_config_hook():
    from drift.runner import _functional_predicates
    assert _functional_predicates({}) is None                       # substrate default
    assert _functional_predicates({"functional_predicates": "*"}) == "*"
    assert _functional_predicates({"functional_predicates": ["a", "b"]}) == {"a", "b"}


def test_speech_act_predicates_never_invalidate_even_under_wildcard():
    """A degenerate extraction returns `speaker / stated / <whole line>` for every
    fact; under "*" that made each new fact supersede the previous one -- 379 of
    380 facts invalidated on a corpus whose true count is 133. Silent, and it
    looks exactly like a policy result."""
    g = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
    g.add_fact("user", "stated", "line one", "a", t_event=0.0)
    g.add_fact("user", "stated", "line two", "b", t_event=100.0)
    g.add_fact("user", "said", "line three", "c", t_event=200.0)
    assert g.stats()["invalidated_active"] == 0


def test_wildcard_still_invalidates_real_predicates():
    g = BitemporalGraph(HashingEmbedder(), functional_predicates="*")
    g.add_fact("Thomas Kyd", "born_in_city", "London", "a", t_event=0.0)
    g.add_fact("Thomas Kyd", "born_in_city", "Leeds", "b", t_event=100.0)
    assert g.stats()["invalidated_active"] == 1
