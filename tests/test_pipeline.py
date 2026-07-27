import json
from pathlib import Path

from drift.embeddings import HashingEmbedder
from drift.memory.extraction import extract_facts
from drift.memory.graph import BitemporalGraph
from drift.pipeline import answer_question, ingest_session, judge_answer, token_f1
from drift.policies import P0NoForgetting, P2ContradictionInvalidation
from drift.providers import DiskCache, MockProvider

DAY = 86400.0


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
