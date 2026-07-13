"""Swarm topology tests — fully offline via MockProvider."""
import json
from pathlib import Path

from drift.runner import load_dataset
from drift.swarm import (cross_writer_invalidations, global_timeline,
                         run_independent, run_orchestrator, run_shared)

CFG = {
    "embedder": "hashing", "retrieval_k": 8, "n_agents": 3, "coverage": 0.8,
    "seed": 42, "extract_models": ["mock"], "answer_model": "mock",
    "judge_model": "mock", "router_model": "mock", "cache_dir": ".drift_cache",
}
DATASET = load_dataset(str(Path(__file__).parent.parent / "data" / "synthetic_smoke.json"))


def test_global_timeline_is_time_ordered():
    sessions, questions = global_timeline(DATASET)
    times = [s["time"] for s in sessions]
    assert times == sorted(times)
    assert all("conversation" in s for s in sessions)
    assert len(questions) == sum(len(c["questions"]) for c in DATASET["conversations"])


def test_shared_topology_runs_and_tracks_writers():
    result = run_shared("P2", DATASET, CFG)
    s = result["summary"]
    assert s["n_questions"] > 0
    assert 0.0 <= s["accuracy"] <= 1.0
    assert s["n_agents"] == 3
    # multi-writer provenance recorded on the memory curve
    agents_seen = {step["agent"] for step in result["memory_curve"]}
    assert len(agents_seen) == 3
    # invalidation accounting is present
    assert "cross_writer_invalidations" in s
    assert s["cross_writer_invalidations"] <= s["invalidations"]


def test_shared_p2_beats_p0_on_staleness():
    stale_p0 = run_shared("P0", DATASET, CFG)["summary"]["staleness_rate"]
    stale_p2 = run_shared("P2", DATASET, CFG)["summary"]["staleness_rate"]
    assert stale_p2 <= stale_p0


def test_independent_topology_reports_variance():
    result = run_independent("P0", DATASET, CFG)
    s = result["summary"]
    assert len(result["per_agent"]) == 3
    assert "accuracy_std" in s and s["accuracy_std"] >= 0.0
    # partial observation: each agent saw at most all sessions
    n_total = len(global_timeline(DATASET)[0])
    for a in result["per_agent"]:
        assert 0 < a["sessions_observed"] <= n_total


def test_orchestrator_routes_every_question():
    result = run_orchestrator("P2", DATASET, CFG)
    s = result["summary"]
    assert sum(s["routing"].values()) == s["n_questions"]
    assert all("worker" in r for r in result["records"])


def test_cross_writer_invalidation_detection():
    from drift.embeddings import make_embedder
    from drift.memory.graph import BitemporalGraph
    g = BitemporalGraph(make_embedder("hashing"))
    g.add_fact("Alice", "lives_in", "Boston", "Alice lives in Boston",
               t_event=0, provenance="agent_0")
    g.add_fact("Alice", "lives_in", "Seattle", "Alice lives in Seattle",
               t_event=100, provenance="agent_1")
    counts = cross_writer_invalidations(g)
    assert counts == {"invalidations": 1, "cross_writer_invalidations": 1}


def test_save_graph_snapshot_and_export():
    cfg = {**CFG, "save_graph": True}
    result = run_shared("P2", DATASET, cfg)
    snap = result["graph_snapshot"]
    assert snap and all("subject" in f and "t_valid_start" in f for f in snap)
    from analysis.graphify_export import facts_to_graph
    g = facts_to_graph(snap)
    assert g["nodes"] and g["links"]
    assert g["graph"]["god_nodes"]
    assert all("community" in n for n in g["nodes"])
    assert any(l["invalidated"] for l in g["links"])  # contradictions visible in export
