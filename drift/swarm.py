"""Multi-agent (swarm) experiments over a bitemporal memory.

Three topologies, each isolating one question about how forgetting policies
behave when memory is used the way production agent systems use it:

  shared        N writer agents ingest an interleaved global session timeline
                into ONE shared BitemporalGraph. Contradictions now arrive from
                *different* writers. Measures: does structure-aware forgetting
                (P2) survive multi-writer contention?

  independent   N agents each own a private graph and observe only a random
                subset of sessions (partial observation, seeded per agent).
                Measures: variance / robustness of each policy across agent
                instances -- mean +/- std accuracy and staleness.

  orchestrator  One shared graph; K specialist worker agents answer questions;
                a router assigns each question to a worker by category.
                Measures: policy behaviour under a production-style
                coordinator/worker read pattern.

Usage:
    python -m drift.swarm --config configs/swarm_smoke.json
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from drift.embeddings import make_embedder
from drift.memory.graph import BitemporalGraph
from drift.pipeline import answer_question, ingest_session, judge_answer
from drift.policies import make_policy
from drift.progress import CampaignTracker, ProgressBar
from drift.providers import FallbackProvider, make_provider
from drift.runner import load_dataset, staleness_hit

ROUTER_SYSTEM = (
    "You route a question to the best specialist. Reply with exactly one worker id."
)
ROUTER_PROMPT = """TASK:ROUTE
WORKERS:
{workers}
QUESTION:
{question}
Reply with only the worker id (e.g. w0)."""


def _make_judge(cfg: dict, cache: str):
    """judge_model may be a single spec or a list; a list is wrapped in a
    FallbackProvider so one exhausted/dead judge doesn't fail the whole
    topology cell. The judge is a neutral scorer, not the experimental
    variable under test, so failing over between judge models doesn't
    confound results the way silently swapping an answer/extractor model
    would.
    """
    spec = cfg.get("judge_model", "mock")
    specs = spec if isinstance(spec, list) else [spec]
    # max_retries=2 (instead of the default 4) when there's more than one
    # judge: the fallback chain itself provides resilience, so one provider
    # shouldn't also burn a full retry-and-backoff cycle against a provider
    # that's already confirmed dead for the day.
    retries = 2 if len(specs) > 1 else 4
    providers = [make_provider(s, cache, max_retries=retries) for s in specs]
    return providers[0] if len(providers) == 1 else FallbackProvider(providers)


# --------------------------------------------------------------------- helpers

def global_timeline(dataset: dict) -> tuple[list[dict], list[dict]]:
    """Interleave all conversations' sessions into one time-ordered stream.

    Each session is tagged with its conversation id; questions carry theirs too.
    This is the 'world' the swarm collectively observes.
    """
    sessions, questions = [], []
    for convo in dataset["conversations"]:
        for s in convo["sessions"]:
            sessions.append({**s, "conversation": convo["id"]})
        for q in convo["questions"]:
            questions.append({**q, "conversation": convo["id"]})
    sessions.sort(key=lambda s: s["time"])
    return sessions, questions


def cross_writer_invalidations(graph: BitemporalGraph) -> dict:
    """Count invalidations where the superseding fact came from a different agent.

    The writer of every fact is recorded in `provenance` (agent_i). For each
    invalidated fact we find its superseder: same subject+predicate, different
    object, valid-start equal to the old fact's invalidation time.
    """
    total, cross = 0, 0
    facts = list(graph.facts.values())
    for old in facts:
        if not old.invalidated:
            continue
        total += 1
        for new in facts:
            if (new.subject.lower() == old.subject.lower()
                    and new.predicate == old.predicate
                    and new.object.lower() != old.object.lower()
                    and new.t_valid_start == old.t_invalid_at):
                if new.provenance != old.provenance:
                    cross += 1
                break
    return {"invalidations": total, "cross_writer_invalidations": cross}


def summarize(records: list[dict]) -> dict:
    n = len(records)
    if not n:
        return {"n_questions": 0, "accuracy": 0.0, "mean_f1": 0.0,
                "staleness_rate": 0.0, "mean_tokens_per_q": 0.0}
    return {
        "n_questions": n,
        "accuracy": sum(r["correct"] for r in records) / n,
        "mean_f1": sum(r["f1"] for r in records) / n,
        "staleness_rate": sum(r["stale"] for r in records) / n,
        "mean_tokens_per_q": sum(r["tokens"] for r in records) / n,
    }


def _answer_and_judge(q: dict, graph: BitemporalGraph, policy, provider,
                      judge_provider, k: int, now: float) -> dict:
    result = answer_question(q["question"], graph, policy, provider, k=k, now=now)
    verdict = judge_answer(q["question"], q["answer"], result["answer"], judge_provider)
    return {
        "conversation": q["conversation"], "category": q.get("category", "single_hop"),
        **result, "gold": q["answer"], **verdict,
        "stale": staleness_hit(result["answer"], q.get("stale_answer")),
    }


# ------------------------------------------------------------------ topologies

def run_shared(policy_spec: str, dataset: dict, cfg: dict) -> dict:
    """N writers -> one graph -> one reader. Contention is the variable."""
    n_agents = cfg.get("n_agents", 3)
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache = cfg.get("cache_dir", ".drift_cache")
    extractors = [make_provider(m, cache) for m in _cycle(cfg["extract_models"], n_agents)]
    answerer = make_provider(cfg["answer_model"], cache)
    judge = _make_judge(cfg, cache)

    sessions, questions = global_timeline(dataset)
    policy = make_policy(policy_spec)
    graph = BitemporalGraph(embedder)

    # One bar spans ingestion + Q&A so it moves from the first session
    # onward instead of sitting silent through the whole extraction pass.
    bar = ProgressBar(len(sessions) + len(questions), label="cell")
    memory_curve, t_last = [], 0.0
    for i, session in enumerate(sessions):
        agent_id = i % n_agents  # round-robin: agents take turns observing the world
        tagged = {**session, "provenance": f"agent_{agent_id}"}
        ingest_session(tagged, graph, policy, extractors[agent_id])
        t_last = max(t_last, session["time"])
        memory_curve.append({"step": i, "agent": agent_id, "time": session["time"],
                             **graph.stats()})
        bar.update(stats=f"ingesting session {i + 1}/{len(sessions)} (agent {agent_id})")

    records = []
    for q in questions:
        records.append(_answer_and_judge(q, graph, policy, answerer, judge,
                                         cfg.get("retrieval_k", 8), t_last))
        n_so_far = len(records)
        acc = sum(r["correct"] for r in records) / n_so_far
        stale = sum(r["stale"] for r in records) / n_so_far
        bar.update(stats=f"acc={acc:.3f} stale={stale:.3f}")
    bar.close()
    result = {"summary": {**summarize(records), "n_agents": n_agents,
                          **cross_writer_invalidations(graph),
                          "final_memory": graph.stats()},
              "records": records, "memory_curve": memory_curve}
    if cfg.get("save_graph"):
        result["graph_snapshot"] = [f.to_dict() for f in graph.facts.values()]
    return result


def run_independent(policy_spec: str, dataset: dict, cfg: dict) -> dict:
    """N private graphs, each agent sees a seeded random subset of sessions."""
    n_agents = cfg.get("n_agents", 3)
    coverage = cfg.get("coverage", 0.8)  # fraction of sessions each agent observes
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache = cfg.get("cache_dir", ".drift_cache")
    extractor = make_provider(cfg["extract_models"][0], cache)
    answerer = make_provider(cfg["answer_model"], cache)
    judge = _make_judge(cfg, cache)

    sessions, questions = global_timeline(dataset)
    # Precompute each agent's observed subset up front (seeded, deterministic)
    # so the bar's total -- and therefore its ETA -- is exact from the start,
    # rather than only covering the Q&A phase once ingestion has already
    # silently finished.
    observed_per_agent = []
    for a in range(n_agents):
        rng = random.Random(cfg.get("seed", 42) + a)
        observed_per_agent.append([s for s in sessions if rng.random() < coverage])
    total_ingest = sum(len(o) for o in observed_per_agent)
    bar = ProgressBar(total_ingest + n_agents * len(questions), label="cell")

    per_agent, all_records = [], []
    for a in range(n_agents):
        observed = observed_per_agent[a]
        policy = make_policy(policy_spec)
        graph = BitemporalGraph(embedder)
        t_last = 0.0
        for s_idx, session in enumerate(observed):  # already time-ordered
            ingest_session({**session, "provenance": f"agent_{a}"}, graph, policy, extractor)
            t_last = max(t_last, session["time"])
            bar.update(stats=f"ingesting agent {a}, session {s_idx + 1}/{len(observed)}")
        records = []
        for q in questions:
            records.append(_answer_and_judge(q, graph, policy, answerer, judge,
                                             cfg.get("retrieval_k", 8), t_last))
            n_so_far = len(records)
            acc = sum(r["correct"] for r in records) / n_so_far
            stale = sum(r["stale"] for r in records) / n_so_far
            bar.update(stats=f"agent={a} acc={acc:.3f} stale={stale:.3f}")
        s = summarize(records)
        per_agent.append({"agent": a, "sessions_observed": len(observed),
                          **s, "final_memory": graph.stats()})
        all_records.extend([{**r, "agent": a} for r in records])
    bar.close()

    accs = [a["accuracy"] for a in per_agent]
    stales = [a["staleness_rate"] for a in per_agent]
    return {"summary": {**summarize(all_records), "n_agents": n_agents,
                        "coverage": coverage,
                        "accuracy_mean": _mean(accs), "accuracy_std": _std(accs),
                        "staleness_mean": _mean(stales), "staleness_std": _std(stales)},
            "per_agent": per_agent, "records": all_records}


def run_orchestrator(policy_spec: str, dataset: dict, cfg: dict) -> dict:
    """Shared graph; router LLM assigns each question to a specialist worker."""
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache = cfg.get("cache_dir", ".drift_cache")
    extractor = make_provider(cfg["extract_models"][0], cache)
    judge = _make_judge(cfg, cache)
    router = make_provider(cfg.get("router_model", cfg["answer_model"]), cache)

    workers = cfg.get("workers", [
        {"id": "w0", "specialty": "current state of people (where they live/work now)",
         "model": cfg["answer_model"]},
        {"id": "w1", "specialty": "old memories and long-ago events",
         "model": cfg["answer_model"]},
        {"id": "w2", "specialty": "recent events and updates",
         "model": cfg["answer_model"]},
    ])
    worker_providers = {w["id"]: make_provider(w["model"], cache) for w in workers}
    worker_desc = "\n".join(f"{w['id']}: {w['specialty']}" for w in workers)

    sessions, questions = global_timeline(dataset)
    policy = make_policy(policy_spec)
    graph = BitemporalGraph(embedder)
    t_last = 0.0
    # One bar spans ingestion + Q&A so it moves from the first session
    # onward instead of sitting silent through the whole extraction pass.
    bar = ProgressBar(len(sessions) + len(questions), label="cell")
    for s_idx, session in enumerate(sessions):
        ingest_session({**session, "provenance": "ingestor"}, graph, policy, extractor)
        t_last = max(t_last, session["time"])
        bar.update(stats=f"ingesting session {s_idx + 1}/{len(sessions)}")

    records, routing = [], {w["id"]: 0 for w in workers}
    for q in questions:
        route = router.complete(
            ROUTER_PROMPT.format(workers=worker_desc, question=q["question"]),
            system=ROUTER_SYSTEM, max_tokens=8).text.strip().lower()
        wid = next((w["id"] for w in workers if w["id"] in route), workers[0]["id"])
        routing[wid] += 1
        rec = _answer_and_judge(q, graph, policy, worker_providers[wid], judge,
                                cfg.get("retrieval_k", 8), t_last)
        records.append({**rec, "worker": wid})
        n_so_far = len(records)
        acc = sum(r["correct"] for r in records) / n_so_far
        stale = sum(r["stale"] for r in records) / n_so_far
        bar.update(stats=f"acc={acc:.3f} stale={stale:.3f}")
    bar.close()

    return {"summary": {**summarize(records), "routing": routing,
                        "final_memory": graph.stats()},
            "records": records}


TOPOLOGIES = {"shared": run_shared, "independent": run_independent,
              "orchestrator": run_orchestrator}


def _cycle(items: list[str], n: int) -> list[str]:
    return [items[i % len(items)] for i in range(n)]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


# ------------------------------------------------------------------------ main

def main() -> None:
    parser = argparse.ArgumentParser(description="DRIFT swarm experiment runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    dataset = load_dataset(cfg["dataset"])
    results_dir = Path(cfg.get("results_dir", "results/swarm"))
    results_dir.mkdir(parents=True, exist_ok=True)

    topologies = cfg.get("topologies", ["shared", "independent", "orchestrator"])
    total_cells = len(topologies) * len(cfg["policies"])
    tracker = CampaignTracker(total_cells)
    print(f"Campaign: {total_cells} cells ({len(topologies)} topologies x {len(cfg['policies'])} policies)")

    summaries = []
    for topology in topologies:
        for policy_spec in cfg["policies"]:
            cell = f"{topology}__{policy_spec.split(':')[0]}"
            out_path = results_dir / f"{cell}.json"
            if out_path.exists() and not args.force:
                print(f"[skip] {cell}  {tracker.cell_done()}")
                summaries.append(json.loads(out_path.read_text())["summary"])
                continue
            print(f"[run ] {cell}")
            t0 = time.time()
            try:
                result = TOPOLOGIES[topology](policy_spec, dataset, cfg)
            except (RuntimeError, OSError) as e:
                print(f"[fail] {cell}: {str(e)[:160]}  (rerun to resume)  {tracker.cell_done()}")
                continue
            result["summary"].update({"topology": topology, "policy": policy_spec,
                                      "wall_seconds": round(time.time() - t0, 1)})
            out_path.write_text(json.dumps(result, indent=1))
            s = result["summary"]
            print(f"       acc={s['accuracy']:.3f} stale={s['staleness_rate']:.3f} "
                  f"({s['wall_seconds']}s)")
            print(f"       {tracker.cell_done()}")
            summaries.append(s)

    (results_dir / "summary_table.json").write_text(json.dumps(summaries, indent=1))
    print(f"\nWrote {results_dir / 'summary_table.json'}")


if __name__ == "__main__":
    main()
