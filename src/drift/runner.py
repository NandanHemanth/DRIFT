"""Experiment runner: {policies} x {models} x {dataset} -> results JSON.

Resumable: one results file per experiment cell; completed cells are skipped.

Usage:
    python -m drift.runner --config configs/smoke.json
    python -m drift.runner --config configs/locomo.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from drift import live
from drift.embeddings import make_embedder
from drift.memory import extraction
from drift.memory.graph import BitemporalGraph
from drift.pipeline import answer_question, ingest_session, judge_answer
from drift.policies import make_policy
from drift.progress import CampaignTracker, ProgressBar
from drift.providers import BaseProvider, FallbackProvider, SpendLedger, make_provider


def _build_providers(specs: list[str], cache_dir: str) -> list[BaseProvider]:
    """Build a role's provider list. When there's more than one provider, each
    is built with max_retries=2 instead of the default 4: the list itself
    (via _rotated_fallback below) is what provides resilience, so a single
    provider doesn't also need to burn its own full retry-and-backoff cycle
    against a provider that's already confirmed dead for the day."""
    retries = 2 if len(specs) > 1 else 4
    return [make_provider(s, cache_dir, max_retries=retries) for s in specs]


def _rotated_fallback(providers: list[BaseProvider], i: int) -> BaseProvider:
    """Prefer providers[i % n] (preserves round-robin load spreading across
    conversations) but fall back through the rest of the list on failure, so
    one exhausted/dead provider fails over instead of failing the whole cell.
    """
    n = len(providers)
    if n == 1:
        return providers[0]
    order = [providers[(i + j) % n] for j in range(n)]
    return FallbackProvider(order)


def _functional_predicates(cfg: dict):
    """Config hook for which predicates admit one true object at a time.

    Accepts "*" (every predicate is functional -- right for fact-consolidation
    corpora) or an explicit list. Omitted keeps the substrate default, so
    existing configs are unaffected.
    """
    fp = cfg.get("functional_predicates")
    if fp is None or fp == "*":
        return fp
    return set(fp)


def _retrieval_weights(cfg: dict):
    """Optional (semantic, lexical, recency) override for hybrid retrieval.

    Omitted in every published config, so those runs keep the substrate default
    of 0.6/0.3/0.1. Present only so the parameter search in
    scripts/param_search.py can evaluate a candidate weighting end to end.
    """
    w = cfg.get("retrieval_weights")
    return tuple(w) if w else None


def _fusion(cfg: dict):
    """Optional fusion method: "weighted" (published) or "rrf" (weight-free).

    Omitted in every published config, so those runs keep the weighted default.
    """
    return cfg.get("retrieval_fusion")


def configure_provider(provider, spec: str, cfg: dict, answer_role: bool = False):
    """Apply per-model request settings from the config.

    request_extras pins an upstream host or switches reasoning on, e.g.
    {"openrouter:qwen/qwen3-8b": {"provider": {"order": ["Alibaba"],
    "allow_fallbacks": false}, "reasoning": {"enabled": true}}}. For answer
    models the thought trace is never used as a fallback answer: an empty reply
    is recorded as empty.
    """
    extras = cfg.get("request_extras", {}).get(spec)
    if extras and hasattr(provider, "extra_body"):
        provider.extra_body = extras
    if answer_role and hasattr(provider, "reasoning_fallback"):
        provider.reasoning_fallback = False
    rpm = cfg.get("rpm_overrides", {}).get(spec.split(":", 1)[0])
    if rpm and hasattr(provider, "limiter"):
        from drift.providers import RateLimiter
        provider.limiter = RateLimiter(rpm)
    return provider


def make_graph(embedder, cfg: dict, cache_dir: str):
    """The memory substrate for one conversation, as configured."""
    judge = None
    if cfg.get("relation_matching") == "llm":
        from drift.memory.normalize import make_llm_judge
        spec = cfg["contradiction_model"]
        judge = make_llm_judge(configure_provider(make_provider(spec, cache_dir), spec, cfg),
                               max_candidates=cfg.get("contradiction_candidates", 8))
    return BitemporalGraph(embedder, functional_predicates=_functional_predicates(cfg),
                           weights=_retrieval_weights(cfg), fusion=_fusion(cfg),
                           relation_matching=cfg.get("relation_matching"),
                           relation_sim=cfg.get("relation_sim"),
                           contradiction_judge=judge)


def prompt_fingerprint() -> str:
    """Short hash of the answer and judge prompts this process is actually using.

    Stored in every cell summary so that cells produced under different prompts
    can be told apart after the fact. This exists because it happened: the
    published FactConsolidation matrix was launched before the answer prompt was
    fixed in commit 187575e, and a running Python process keeps the module it
    imported at startup, so every cell in that run used the old prompt even
    though most of them finished after the commit. Nothing in the saved cells
    recorded that. Comparing fingerprints across a results directory now does.
    """
    import hashlib
    from drift import pipeline
    blob = "\x00".join([pipeline.ANSWER_SYSTEM, pipeline.ANSWER_PROMPT,
                        pipeline.JUDGE_SYSTEM, pipeline.JUDGE_PROMPT])
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def load_dataset(path: str) -> dict:
    """Dataset schema:
    {"conversations": [{"id": str, "sessions": [{"time": float, "lines": [str]}],
                        "questions": [{"question": str, "answer": str,
                                       "category": str, "stale_answer": str|null}]}]}
    """
    return json.loads(Path(path).read_text())


def staleness_hit(answer: str, stale_answer: str | None) -> bool:
    """An answer is stale if it contains the superseded (old) fact string."""
    if not stale_answer:
        return False
    return stale_answer.lower() in answer.lower()


def run_cell(policy_spec: str, model_spec: str, dataset: dict, cfg: dict, out_path: Path) -> dict:
    extraction.FAILED_PARSES.update(first=0, after_retry=0)
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    fp = _functional_predicates(cfg)
    cache_dir = cfg.get("cache_dir", ".drift_cache")
    answer_provider = configure_provider(make_provider(model_spec, cache_dir), model_spec, cfg,
                                         answer_role=True)
    answer_max_tokens = cfg.get("answer_max_tokens", {}).get(model_spec, 1024)
    maint_spec = cfg.get("maintenance_model")
    maintenance_provider = (configure_provider(make_provider(maint_spec, cache_dir), maint_spec, cfg)
                            if maint_spec else None)
    # extract_model may be a single spec or a list of specs. A list is
    # round-robined one-per-conversation, spreading the highest-volume calls
    # in the pipeline (extraction) across several providers' independent free
    # tiers instead of hammering one rate limit.
    extract_spec = cfg.get("extract_model", model_spec)
    extract_specs = extract_spec if isinstance(extract_spec, list) else [extract_spec]
    extract_providers = _build_providers(extract_specs, cache_dir)
    # judge_model may also be a list, round-robined per conversation, exactly
    # like extract_model. This splits judge-call volume (the single largest
    # quota cost, since every question needs one) across multiple providers'
    # independent free-tier ceilings instead of one.
    judge_spec = cfg.get("judge_model", "mock")
    judge_specs = judge_spec if isinstance(judge_spec, list) else [judge_spec]
    judge_providers = [configure_provider(p, sp, cfg)
                       for p, sp in zip(_build_providers(judge_specs, cache_dir), judge_specs)]

    # One bar spans BOTH phases (session ingestion/extraction, then Q&A) so
    # it starts moving on the very first ingested session instead of sitting
    # silent through the whole extraction pass -- that silence, for LoCoMo's
    # 272 sessions, looked identical to a hung process.
    total_sessions = sum(len(c["sessions"]) for c in dataset["conversations"])
    total_questions = sum(len(c["questions"]) for c in dataset["conversations"])
    n_convos = len(dataset["conversations"])
    bar = ProgressBar(total_sessions + total_questions, label="cell")

    records, memory_curves = [], []
    snapshots: dict[str, list[dict]] = {}
    totals = {"active_facts": 0, "total_facts": 0, "invalidated_active": 0, "pruned": 0,
              "write_rejections": 0, "closed_total": 0, "contradiction_judgements": 0}
    for convo_i, convo in enumerate(dataset["conversations"]):
        extract_provider = _rotated_fallback(extract_providers, convo_i)
        judge_provider = _rotated_fallback(judge_providers, convo_i)
        policy = make_policy(policy_spec)  # fresh policy state per conversation
        graph = make_graph(embedder, cfg, cache_dir)
        t_last = 0.0
        for s_idx, session in enumerate(convo["sessions"]):
            ingest_session(session, graph, policy, extract_provider, maintenance_provider)
            t_last = max(t_last, session["time"])
            memory_curves.append({"conversation": convo["id"], "session": s_idx, **graph.stats()})
            if cfg.get("live"):
                # Opt-in monitoring. live.write() swallows every exception, so a
                # failure here costs the live view and not the campaign.
                live.write(cfg.get("results_dir", "results"),
                           policy=policy_spec, model=model_spec,
                           conversation=convo["id"], session=s_idx,
                           n_sessions=len(convo["sessions"]),
                           graph=graph, curves=memory_curves)
            bar.update(stats=f"ingesting convo {convo_i + 1}/{n_convos}, "
                             f"session {s_idx + 1}/{len(convo['sessions'])}")

        # Per-conversation end state. ConvoMem has ten conversations, and the
        # summary used to keep only the last one's memory, so totals and saved
        # graphs now cover every conversation.
        st = graph.stats()
        for key in ("active_facts", "total_facts", "invalidated_active", "pruned", "write_rejections"):
            totals[key] += st.get(key, 0)
        totals["closed_total"] += sum(1 for f in graph.facts.values() if f.invalidated)
        totals["contradiction_judgements"] += getattr(graph, "llm_judgements", 0)
        if cfg.get("save_graph"):
            snapshots[convo["id"]] = [f.to_dict() for f in graph.facts.values()]

        def qa(q, graph=graph, policy=policy, judge_provider=judge_provider, t_last=t_last,
               convo_id=convo["id"]):
            result = answer_question(q["question"], graph, policy, answer_provider,
                                     k=cfg.get("retrieval_k", 8), now=t_last,
                                     show_supersession=cfg.get("show_supersession", False),
                                     max_tokens=answer_max_tokens)
            verdict = judge_answer(q["question"], q["answer"], result["answer"], judge_provider,
                                   max_tokens=cfg.get("judge_max_tokens", 1024))
            return {
                "conversation": convo_id, "category": q.get("category", "single_hop"),
                **result, "gold": q["answer"], **verdict,
                "stale": staleness_hit(result["answer"], q.get("stale_answer")),
            }

        # Questions only read the finished graph, so they can be answered in
        # parallel; results keep question order. qa_workers = 1 is the old path.
        workers = cfg.get("qa_workers", 1)
        if workers > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers) as ex:
                convo_records = list(ex.map(qa, convo["questions"]))
        else:
            convo_records = [qa(q) for q in convo["questions"]]
        for rec in convo_records:
            records.append(rec)
            n_so_far = len(records)
            acc_so_far = sum(r["correct"] for r in records) / n_so_far
            stale_so_far = sum(r["stale"] for r in records) / n_so_far
            bar.update(stats=f"acc={acc_so_far:.3f} stale={stale_so_far:.3f}")

    bar.close()
    n = len(records)
    summary = {
        "policy": policy_spec, "model": model_spec, "n_questions": n,
        "accuracy": sum(r["correct"] for r in records) / n if n else 0.0,
        "mean_f1": sum(r["f1"] for r in records) / n if n else 0.0,
        "staleness_rate": sum(r["stale"] for r in records) / n if n else 0.0,
        "mean_tokens_per_q": sum(r["tokens"] for r in records) / n if n else 0.0,
        "final_memory": memory_curves[-1] if memory_curves else {},
        "timestamp": time.time(),
        "prompt_fingerprint": prompt_fingerprint(),
        "relation_matching": cfg.get("relation_matching", "exact"),
        "maintenance_model": maint_spec,
        "contradiction_judgements": totals["contradiction_judgements"],
        "memory_totals": totals,
        "extraction_parse_failures": dict(extraction.FAILED_PARSES),
        "n_conversations": n_convos,
    }
    payload = {"summary": summary, "records": records, "memory_curves": memory_curves}
    if cfg.get("save_graph"):
        payload["graph_snapshot"] = [f.to_dict() for f in graph.facts.values()]
        if len(snapshots) > 1:
            payload["graph_snapshots"] = snapshots
    out_path.write_text(json.dumps(payload, indent=1))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="DRIFT experiment runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--force", action="store_true", help="rerun completed cells")
    parser.add_argument("--live", action="store_true",
                        help="publish <results_dir>/live.json + live.html after "
                             "each ingested session; open live.html to watch "
                             "memory build. Failures are swallowed, so this "
                             "cannot break a run.")
    parser.add_argument("--policies", help="comma list, run only these policies (e.g. P0,P2)")
    parser.add_argument("--models", help="comma list of substrings, run only matching models")
    parser.add_argument("--budget", type=float, help="stop starting new cells past this USD spend")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    if args.live:
        cfg["live"] = True
    if args.policies:
        keep = set(args.policies.split(","))
        cfg["policies"] = [p for p in cfg["policies"] if p.split(":")[0] in keep]
    if args.models:
        subs = args.models.split(",")
        cfg["models"] = [m for m in cfg["models"] if any(x in m for x in subs)]
    budget = args.budget if args.budget is not None else cfg.get("budget_usd")
    extraction.RETRY_MAX_TOKENS = cfg.get("extract_retry_tokens")
    dataset = load_dataset(cfg["dataset"])
    results_dir = Path(cfg.get("results_dir", "results"))
    results_dir.mkdir(parents=True, exist_ok=True)
    if cfg.get("live"):
        print(f"live view -> open {results_dir / 'live.html'} in a browser")

    total_cells = len(cfg["policies"]) * len(cfg["models"])
    tracker = CampaignTracker(total_cells)
    print(f"Campaign: {total_cells} cells ({len(cfg['policies'])} policies x {len(cfg['models'])} models)")

    summaries, failures = [], []
    for policy_spec in cfg["policies"]:
        for model_spec in cfg["models"]:
            cell = f"{policy_spec.split(':')[0]}__{model_spec.replace(':', '_').replace('/', '_')}"
            out_path = results_dir / f"{cell}.json"
            if out_path.exists() and not args.force:
                print(f"[skip] {cell} (exists)  {tracker.cell_done()}")
                summaries.append(json.loads(out_path.read_text())["summary"])
                continue
            if budget is not None and SpendLedger.total() >= budget:
                print(f"[stop] budget ${budget:.2f} reached ({SpendLedger.report()})")
                failures.append(cell)
                continue
            print(f"[run ] {cell}")
            try:
                summary = run_cell(policy_spec, model_spec, dataset, cfg, out_path)
            except (RuntimeError, OSError) as e:
                # One dead provider must not kill the campaign: log, move on,
                # rerun later (completed work is cached, the cell will resume).
                print(f"[fail] {cell}: {str(e)[:160]}  {tracker.cell_done()}")
                failures.append(cell)
                continue
            print(f"       acc={summary['accuracy']:.3f} f1={summary['mean_f1']:.3f} "
                  f"stale={summary['staleness_rate']:.3f} tok/q={summary['mean_tokens_per_q']:.0f}")
            print(f"       {tracker.cell_done()}")
            print(f"       {SpendLedger.report()}")
            summaries.append(summary)

    table_path = results_dir / "summary_table.json"
    table_path.write_text(json.dumps(summaries, indent=1))
    print(f"\nWrote {table_path}")
    if failures:
        print(f"{len(failures)} cell(s) failed and will resume on rerun: {', '.join(failures)}")


if __name__ == "__main__":
    main()
