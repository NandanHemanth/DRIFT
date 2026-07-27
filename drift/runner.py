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

from drift.embeddings import make_embedder
from drift.memory.graph import BitemporalGraph
from drift.pipeline import answer_question, ingest_session, judge_answer
from drift.policies import make_policy
from drift.progress import CampaignTracker, ProgressBar
from drift.providers import BaseProvider, FallbackProvider, make_provider


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
    embedder = make_embedder(cfg.get("embedder", "hashing"))
    cache_dir = cfg.get("cache_dir", ".drift_cache")
    answer_provider = make_provider(model_spec, cache_dir)
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
    judge_providers = _build_providers(judge_specs, cache_dir)

    # One bar spans BOTH phases (session ingestion/extraction, then Q&A) so
    # it starts moving on the very first ingested session instead of sitting
    # silent through the whole extraction pass -- that silence, for LoCoMo's
    # 272 sessions, looked identical to a hung process.
    total_sessions = sum(len(c["sessions"]) for c in dataset["conversations"])
    total_questions = sum(len(c["questions"]) for c in dataset["conversations"])
    n_convos = len(dataset["conversations"])
    bar = ProgressBar(total_sessions + total_questions, label="cell")

    records, memory_curves = [], []
    for convo_i, convo in enumerate(dataset["conversations"]):
        extract_provider = _rotated_fallback(extract_providers, convo_i)
        judge_provider = _rotated_fallback(judge_providers, convo_i)
        policy = make_policy(policy_spec)  # fresh policy state per conversation
        graph = BitemporalGraph(embedder)
        t_last = 0.0
        for s_idx, session in enumerate(convo["sessions"]):
            ingest_session(session, graph, policy, extract_provider)
            t_last = max(t_last, session["time"])
            memory_curves.append({"conversation": convo["id"], "session": s_idx, **graph.stats()})
            bar.update(stats=f"ingesting convo {convo_i + 1}/{n_convos}, "
                             f"session {s_idx + 1}/{len(convo['sessions'])}")

        for q in convo["questions"]:
            result = answer_question(q["question"], graph, policy, answer_provider,
                                     k=cfg.get("retrieval_k", 8), now=t_last)
            verdict = judge_answer(q["question"], q["answer"], result["answer"], judge_provider)
            records.append({
                "conversation": convo["id"], "category": q.get("category", "single_hop"),
                **result, "gold": q["answer"], **verdict,
                "stale": staleness_hit(result["answer"], q.get("stale_answer")),
            })
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
    }
    payload = {"summary": summary, "records": records, "memory_curves": memory_curves}
    if cfg.get("save_graph"):
        payload["graph_snapshot"] = [f.to_dict() for f in graph.facts.values()]
    out_path.write_text(json.dumps(payload, indent=1))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="DRIFT experiment runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--force", action="store_true", help="rerun completed cells")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    dataset = load_dataset(cfg["dataset"])
    results_dir = Path(cfg.get("results_dir", "results"))
    results_dir.mkdir(parents=True, exist_ok=True)

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
            summaries.append(summary)

    table_path = results_dir / "summary_table.json"
    table_path.write_text(json.dumps(summaries, indent=1))
    print(f"\nWrote {table_path}")
    if failures:
        print(f"{len(failures)} cell(s) failed and will resume on rerun: {', '.join(failures)}")


if __name__ == "__main__":
    main()
