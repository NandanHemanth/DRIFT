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
from drift.providers import FallbackProvider, SpendLedger, make_provider
from drift.runner import (add_cell_cost, configure_provider, load_dataset, make_graph, mentions_old,
                          staleness_hit, write_run_record)

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
    providers = [configure_provider(make_provider(s, cache, max_retries=retries), s, cfg)
                 for s in specs]
    return providers[0] if len(providers) == 1 else FallbackProvider(providers)


def _single_extractor(cfg: dict, cache: str):
    """Extractor for the topologies with one writer (independent, orchestrator).

    "single_extract_model" may name the same cached extraction chain the
    single-agent matrix uses, so those topologies start from the same facts as
    the single-agent runs; otherwise the first shared-topology writer is used.
    """
    from drift.runner import _build_providers, _rotated_fallback
    spec = cfg.get("single_extract_model") or cfg["extract_models"][0]
    specs = spec if isinstance(spec, list) else [spec]
    providers = [configure_provider(p, sp, cfg) for p, sp in zip(_build_providers(specs, cache), specs)]
    return _rotated_fallback(providers, 0)


def _answerer(spec: str, cfg: dict, cache: str):
    return configure_provider(make_provider(spec, cache), spec, cfg, answer_role=True)


def _maintenance(cfg: dict, cache: str):
    spec = cfg.get("maintenance_model")
    return configure_provider(make_provider(spec, cache), spec, cfg) if spec else None


# --------------------------------------------------------------------- helpers
_ANSWER_MAX_TOKENS: dict[str, int] = {}  # model id -> budget, filled from the config in main()


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
    invalidated fact we find its superseder: a fact that became valid exactly when
    the old one was closed and shares an entity with it. Matching on entities
    rather than on (subject, predicate) also counts supersessions found by
    normalised, reversed-direction or LLM matching, where the two facts' subjects
    or relation names differ.
    """
    from drift.memory.normalize import entity_key
    total, cross = 0, 0
    facts = list(graph.facts.values())
    for old in facts:
        if not old.invalidated:
            continue
        total += 1
        ents = {entity_key(old.subject), entity_key(old.object)}
        for new in facts:
            if (new is not old and new.t_valid_start == old.t_invalid_at
                    and ents & {entity_key(new.subject), entity_key(new.object)}):
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
                      judge_provider, k: int, now: float,
                      show_supersession: bool = False) -> dict:
    result = answer_question(q["question"], graph, policy, provider, k=k, now=now,
                             show_supersession=show_supersession,
                             max_tokens=_ANSWER_MAX_TOKENS.get(getattr(provider, "model", ""), 1024))
    verdict = judge_answer(q["question"], q["answer"], result["answer"], judge_provider,
                           stale_answer=q.get("stale_answer"))
    return {
        "conversation": q["conversation"], "category": q.get("category", "single_hop"),
        **result, "gold": q["answer"], **verdict,
        "stale": staleness_hit(result["answer"], q.get("stale_answer"), q.get("current_answer")),
        "mentions_old": mentions_old(result["answer"], q.get("stale_answer")),
    }


# ------------------------------------------------------------------ topologies
#
# Every topology builds memory once and then answers with every model in
# cfg["answer_models"] (or the single cfg["answer_model"]). Extraction and
# maintenance never depend on the answer model, so all answer models read the
# identical memory and only the reader differs, as in the single-agent matrix.
#
# Memory is built per conversation: ConvoMem has ten unrelated users, and one
# graph across them would let one user's "my call" contradict another's. The
# single-conversation benchmarks (MQuAKE-T, FactConsolidation) are unchanged.

def _answer_models(cfg: dict) -> list[str]:
    return cfg.get("answer_models") or [cfg["answer_model"]]


def _by_conversation(sessions: list[dict], questions: list[dict]):
    """(conversation id, its sessions in time order, its questions), in first-seen order."""
    order, ss, qs = [], {}, {}
    for s in sessions:
        c = s["conversation"]
        if c not in ss:
            order.append(c)
            ss[c], qs[c] = [], []
        ss[c].append(s)
    for q in questions:
        qs.setdefault(q["conversation"], []).append(q)
    return [(c, ss[c], qs.get(c, [])) for c in order]


def _per_model_summary(records: list[dict]) -> dict:
    by = {}
    for r in records:
        by.setdefault(r["answer_model"], []).append(r)
    return {m: summarize(rs) for m, rs in by.items()}


def run_shared(policy_spec: str, dataset: dict, cfg: dict) -> dict:
    """N writers -> one graph per conversation -> each answer model reads it."""
    n_agents = cfg.get("n_agents", 3)
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache = cfg.get("cache_dir", ".drift_cache")
    extractors = [configure_provider(make_provider(m, cache), m, cfg)
                  for m in _cycle(cfg["extract_models"], n_agents)]
    models = _answer_models(cfg)
    answerers = {m: _answerer(m, cfg, cache) for m in models}
    maint = _maintenance(cfg, cache)
    judge = _make_judge(cfg, cache)

    sessions, questions = global_timeline(dataset)
    step_agent = {id(s): i % n_agents for i, s in enumerate(sessions)}  # round-robin over the world
    bar = ProgressBar(len(sessions) + len(questions) * len(models), label="cell")
    memory_curve, records, snapshots = [], [], {}
    inv = {"invalidations": 0, "cross_writer_invalidations": 0}
    final_mem = {}
    judgements = 0
    for convo, c_sessions, c_questions in _by_conversation(sessions, questions):
        policy = make_policy(policy_spec)
        graph = make_graph(embedder, cfg, cache)
        t_last = 0.0
        for session in c_sessions:
            agent_id = step_agent[id(session)]
            ingest_session({**session, "provenance": f"agent_{agent_id}"}, graph, policy,
                           extractors[agent_id], maint)
            t_last = max(t_last, session["time"])
            memory_curve.append({"conversation": convo, "agent": agent_id, "time": session["time"],
                                 **graph.stats()})
            bar.update(stats=f"ingesting {convo} (agent {agent_id})")
        for m in models:
            for q in c_questions:
                records.append({**_answer_and_judge(q, graph, policy, answerers[m], judge,
                                                    cfg.get("retrieval_k", 8), t_last),
                                "answer_model": m})
                bar.update(stats=f"{m.split('/')[-1]} answering")
        for k, v in cross_writer_invalidations(graph).items():
            inv[k] += v
        judgements += getattr(graph, "llm_judgements", 0)
        for k, v in graph.stats().items():
            final_mem[k] = final_mem.get(k, 0) + v
        snapshots[convo] = [f.to_dict() for f in graph.facts.values()]
    bar.close()
    result = {"summary": {**summarize(records), "n_agents": n_agents, **inv,
                          "contradiction_judgements": judgements, "final_memory": final_mem,
                          "by_model": _per_model_summary(records)},
              "records": records, "memory_curve": memory_curve}
    if cfg.get("save_graph"):
        result["graph_snapshots"] = snapshots
        # flat list kept for readers written before per-conversation snapshots
        result["graph_snapshot"] = [f for fs in snapshots.values() for f in fs]
    return result


def run_independent(policy_spec: str, dataset: dict, cfg: dict) -> dict:
    """N private graphs; each agent sees a seeded random subset of sessions."""
    n_agents = cfg.get("independent_agents", cfg.get("n_agents", 3))
    coverage = cfg.get("coverage", 0.8)  # fraction of sessions each agent observes
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache = cfg.get("cache_dir", ".drift_cache")
    extractor = _single_extractor(cfg, cache)
    models = _answer_models(cfg)
    answerers = {m: _answerer(m, cfg, cache) for m in models}
    maint = _maintenance(cfg, cache)
    judge = _make_judge(cfg, cache)

    sessions, questions = global_timeline(dataset)
    # Each agent's observed subset is drawn once over the global timeline, seeded
    # per agent, exactly as before; it is then split by conversation.
    observed_ids = []
    for a in range(n_agents):
        rng = random.Random(cfg.get("seed", 42) + a)
        observed_ids.append({id(s) for s in sessions if rng.random() < coverage})
    groups = _by_conversation(sessions, questions)
    total_ingest = sum(len(o) for o in observed_ids)
    bar = ProgressBar(total_ingest + n_agents * len(questions) * len(models), label="cell")

    per_agent, all_records, snapshots = [], [], {}
    for a in range(n_agents):
        agent_records, mem, n_obs = [], {}, 0
        for convo, c_sessions, c_questions in groups:
            policy = make_policy(policy_spec)
            graph = make_graph(embedder, cfg, cache)
            t_last = 0.0
            for session in c_sessions:
                if id(session) not in observed_ids[a]:
                    continue
                n_obs += 1
                ingest_session({**session, "provenance": f"agent_{a}"}, graph, policy, extractor, maint)
                t_last = max(t_last, session["time"])
                bar.update(stats=f"ingesting agent {a}, {convo}")
            for m in models:
                for q in c_questions:
                    agent_records.append({**_answer_and_judge(q, graph, policy, answerers[m], judge,
                                                              cfg.get("retrieval_k", 8), t_last),
                                          "answer_model": m, "agent": a})
                    bar.update(stats=f"agent={a} {m.split('/')[-1]}")
            for k, v in graph.stats().items():
                mem[k] = mem.get(k, 0) + v
            snapshots[f"agent_{a}|{convo}"] = [f.to_dict() for f in graph.facts.values()]
        per_agent.append({"agent": a, "sessions_observed": n_obs, **summarize(agent_records),
                          "by_model": _per_model_summary(agent_records), "final_memory": mem})
        all_records.extend(agent_records)
    bar.close()

    accs = [a["accuracy"] for a in per_agent]
    stales = [a["staleness_rate"] for a in per_agent]
    result = {"summary": {**summarize(all_records), "n_agents": n_agents, "coverage": coverage,
                          "accuracy_mean": _mean(accs), "accuracy_std": _std(accs),
                          "staleness_mean": _mean(stales), "staleness_std": _std(stales),
                          "by_model": _per_model_summary(all_records)},
              "per_agent": per_agent, "records": all_records}
    if cfg.get("save_graph"):
        result["graph_snapshots"] = snapshots
        # flat list kept for readers written before per-conversation snapshots
        result["graph_snapshot"] = [f for fs in snapshots.values() for f in fs]
    return result


def run_orchestrator(policy_spec: str, dataset: dict, cfg: dict) -> dict:
    """Shared graph per conversation; a fixed router assigns each question to one
    of three specialist workers, all played by the answer model under test."""
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache = cfg.get("cache_dir", ".drift_cache")
    extractor = _single_extractor(cfg, cache)
    judge = _make_judge(cfg, cache)
    models = _answer_models(cfg)
    router_spec = cfg.get("router_model", models[0])
    router = configure_provider(make_provider(router_spec, cache), router_spec, cfg)
    maint = _maintenance(cfg, cache)
    specialties = ([(w["id"], w["specialty"]) for w in cfg["workers"]] if cfg.get("workers")
                   else None) or cfg.get("worker_specialties", [
        ("w0", "current state of people (where they live/work now)"),
        ("w1", "old memories and long-ago events"),
        ("w2", "recent events and updates"),
    ])
    worker_desc = "\n".join(f"{wid}: {spec}" for wid, spec in specialties)
    answerers = {m: _answerer(m, cfg, cache) for m in models}

    sessions, questions = global_timeline(dataset)
    bar = ProgressBar(len(sessions) + len(questions) * len(models), label="cell")
    records, routing, snapshots, final_mem = [], {wid: 0 for wid, _ in specialties}, {}, {}
    for convo, c_sessions, c_questions in _by_conversation(sessions, questions):
        policy = make_policy(policy_spec)
        graph = make_graph(embedder, cfg, cache)
        t_last = 0.0
        for session in c_sessions:
            ingest_session({**session, "provenance": "ingestor"}, graph, policy, extractor, maint)
            t_last = max(t_last, session["time"])
            bar.update(stats=f"ingesting {convo}")
        # The router is fixed and model-independent, so every answer model gets
        # the same routing; only the worker that answers differs.
        routes = {}
        for q in c_questions:
            route = router.complete(ROUTER_PROMPT.format(workers=worker_desc, question=q["question"]),
                                    system=ROUTER_SYSTEM, max_tokens=8).text.strip().lower()
            routes[q["question"]] = next((wid for wid, _ in specialties if wid in route), specialties[0][0])
            routing[routes[q["question"]]] += 1
        for m in models:
            for q in c_questions:
                rec = _answer_and_judge(q, graph, policy, answerers[m], judge,
                                        cfg.get("retrieval_k", 8), t_last)
                records.append({**rec, "worker": routes[q["question"]], "answer_model": m})
                bar.update(stats=f"{m.split('/')[-1]} answering")
        for k, v in graph.stats().items():
            final_mem[k] = final_mem.get(k, 0) + v
        snapshots[convo] = [f.to_dict() for f in graph.facts.values()]
    bar.close()
    result = {"summary": {**summarize(records), "routing": routing, "final_memory": final_mem,
                          "by_model": _per_model_summary(records)},
              "records": records}
    if cfg.get("save_graph"):
        result["graph_snapshots"] = snapshots
        # flat list kept for readers written before per-conversation snapshots
        result["graph_snapshot"] = [f for fs in snapshots.values() for f in fs]
    return result


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
    parser.add_argument("--topologies", help="comma list, e.g. shared")
    parser.add_argument("--policies", help="comma list, e.g. P0,P2")
    parser.add_argument("--budget", type=float, help="stop starting new cells past this USD spend")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    if args.topologies:
        cfg["topologies"] = args.topologies.split(",")
    if args.policies:
        keep = set(args.policies.split(","))
        cfg["policies"] = [p for p in cfg["policies"] if p.split(":")[0] in keep]
    budget = args.budget if args.budget is not None else cfg.get("budget_usd")
    from drift.memory import extraction
    extraction.RETRY_MAX_TOKENS = cfg.get("extract_retry_tokens")
    extraction.CONTEXT_LINES = int(cfg.get("extract_context_lines", 0))
    for spec, n in cfg.get("answer_max_tokens", {}).items():
        _ANSWER_MAX_TOKENS[spec.split(":", 1)[1]] = n
    dataset = load_dataset(cfg["dataset"])
    results_dir = Path(cfg.get("results_dir", "results/swarm"))
    results_dir.mkdir(parents=True, exist_ok=True)
    write_run_record(results_dir, cfg, args.config)

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
            if budget is not None and SpendLedger.total() >= budget:
                print(f"[stop] budget ${budget:.2f} reached ({SpendLedger.report()})")
                continue
            print(f"[run ] {cell}")
            t0 = time.time()
            spent_before = SpendLedger.total()
            try:
                result = TOPOLOGIES[topology](policy_spec, dataset, cfg)
            except (RuntimeError, OSError) as e:
                print(f"[fail] {cell}: {str(e)[:160]}  (rerun to resume)  {tracker.cell_done()}")
                continue
            result["summary"].update({"topology": topology, "policy": policy_spec,
                                      "wall_seconds": round(time.time() - t0, 1),
                                      "relation_matching": cfg.get("relation_matching", "exact"),
                                      "embedder": cfg.get("embedder", "hashing")})
            out_path.write_text(json.dumps(result, indent=1))
            add_cell_cost(out_path, SpendLedger.total() - spent_before, cfg)
            s = result["summary"]
            print(f"       acc={s['accuracy']:.3f} stale={s['staleness_rate']:.3f} "
                  f"({s['wall_seconds']}s)")
            print(f"       {tracker.cell_done()}")
            print(f"       {SpendLedger.report()}")
            summaries.append(s)

    (results_dir / "summary_table.json").write_text(json.dumps(summaries, indent=1))
    print(f"\nWrote {results_dir / 'summary_table.json'}")


if __name__ == "__main__":
    main()
