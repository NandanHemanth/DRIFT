"""What does P2's grace period buy? A measurement that can reward history.

Why this exists
---------------
Every earlier grace sweep found that correctness does not move between 0 and 30
days, and that only cost moves (fewer stored facts and fewer wasted retrieval
slots at short grace). Read naively that argues for grace 0. It does not,
because none of those benchmarks ever asks about the past: no metric could
reward keeping a superseded fact, so the measurement was one-sided.

This experiment adds the missing side. For every benchmark question that has a
superseded answer, it asks two probes against the same P2 memory:

  current   the original question, gold = the current answer. Answered with
            P2's normal retrieval (closed facts filtered out).
  history   "Before it was last changed, what was the answer to: <question>",
            gold = the superseded answer. Answered from retrieval that keeps
            closed but not yet pruned facts and labels them with the date they
            were superseded. This is the bitemporal "as of" read that a grace
            period exists to protect.

Sweeping the grace period then gives both sides of the trade-off on one axis:
history recall rises with grace, and storage and wasted slots rise with it too.
The "best" grace is a point on that curve that depends on how far back history
questions reach, which is reported directly as the age of each closed fact at
question time.

Two levels, like the rest of the sensitivity work:
  retrieval  free, no model calls: does the needed answer string reach the
             context? (accuracy tracked this at r = 0.99 in the deep analysis)
  answers    optional, `answer_models` in the config: real answers graded by the
             fixed judge, to confirm the retrieval curve end to end.

Usage
-----
    python -m analysis.grace_history run --config configs/grace_history.json
    python -m analysis.grace_history run --config configs/grace_history.json --answers
    python -m analysis.grace_history analyze --config configs/grace_history.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from analysis.sensitivity import MemoEmbedder
from drift.embeddings import make_embedder
from drift.pipeline import ANSWER_PROMPT, ANSWER_SYSTEM, _THINK, ingest_session, judge_answer, \
    render_fact
from drift.policies import make_policy
from drift.providers import SpendLedger, make_provider
from drift.runner import _build_providers, _rotated_fallback, configure_provider, make_graph

DAY = 86400.0
NEVER = 1e6  # days; "never prune"
HISTORY_TEMPLATE = "Before it was last changed, what was the answer to this question: {q}"


def _grace_label(g) -> str:
    return "never" if g == "never" else f"{g:g}"


def _grace_days(g) -> float:
    return NEVER if g == "never" else float(g)


def _contains(facts, needle: str | None) -> bool:
    if not needle:
        return False
    n = needle.lower()
    return any(n in f.text.lower() for f in facts)


def build(convo: dict, convo_i: int, grace, bench_cfg: dict, cfg: dict, embedder):
    cache_dir = cfg.get("cache_dir", ".drift_cache")
    specs = bench_cfg["extract_model"]
    specs = specs if isinstance(specs, list) else [specs]
    extractor = _rotated_fallback([configure_provider(p, sp, cfg) for p, sp in
                                   zip(_build_providers(specs, cache_dir), specs)], convo_i)
    graph = make_graph(embedder, cfg, cache_dir)
    policy = make_policy(f"P2:grace_days={_grace_days(grace)}")
    t_last = 0.0
    for session in convo["sessions"]:
        ingest_session(session, graph, policy, extractor)
        t_last = max(t_last, session["time"])
    return graph, policy, t_last


def probes(convo: dict) -> list[dict]:
    """Only questions with a superseded answer have a history probe."""
    return [q for q in convo["questions"] if q.get("stale_answer")]


def retrieval_row(graph, policy, q: dict, k: int, now: float) -> dict:
    pre = graph.search(q["question"], k=k, now=now)
    post = policy.on_retrieve(pre, now=now)
    hist = graph.search(HISTORY_TEMPLATE.format(q=q["question"]), k=k, now=now)
    alive = [f for f in graph.facts.values() if f.active]
    closed_with_stale = [f for f in alive if f.invalidated
                         and q["stale_answer"].lower() in f.text.lower()]
    age = min(((now - f.t_invalid_at) / DAY for f in closed_with_stale), default=None)
    return {
        "current_gold": _contains(post, q["answer"]),
        "current_stale": _contains(post, q["stale_answer"]),
        "wasted_slots": len(pre) - len(post),
        "history_stored": _contains(alive, q["stale_answer"]),
        "history_support": _contains(hist, q["stale_answer"]),
        "closure_age_days": age,
    }


def answer_history(graph, q: dict, provider, k: int, now: float, max_tokens: int) -> str:
    hq = HISTORY_TEMPLATE.format(q=q["question"])
    facts = graph.search(hq, k=k, now=now)
    block = "\n".join(render_fact(f, show_supersession=True) for f in facts) or "(no relevant memory)"
    c = provider.complete(ANSWER_PROMPT.format(memory=block, question=hq), system=ANSWER_SYSTEM,
                          max_tokens=max_tokens)
    return _THINK.sub("", c.text).strip()


def answer_current(graph, policy, q: dict, provider, k: int, now: float, max_tokens: int) -> str:
    facts = policy.on_retrieve(graph.search(q["question"], k=k, now=now), now=now)
    block = "\n".join(render_fact(f) for f in facts) or "(no relevant memory)"
    c = provider.complete(ANSWER_PROMPT.format(memory=block, question=q["question"]),
                          system=ANSWER_SYSTEM, max_tokens=max_tokens)
    return _THINK.sub("", c.text).strip()


def run(cfg: dict, with_answers: bool, limit: int | None) -> None:
    from drift.memory import extraction
    extraction.RETRY_MAX_TOKENS = cfg.get("extract_retry_tokens")
    out_dir = Path(cfg["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    embedder = MemoEmbedder(make_embedder(cfg.get("embedder", "hashing")))
    k = cfg.get("retrieval_k", 25)
    cache_dir = cfg.get("cache_dir", ".drift_cache")
    models = cfg.get("answer_models", []) if with_answers else []
    answerers = {m: configure_provider(make_provider(m, cache_dir), m, cfg, answer_role=True)
                 for m in models}
    judge = None
    if models:
        js = cfg["judge_model"]
        judge = configure_provider(make_provider(js, cache_dir), js, cfg)
    workers = cfg.get("qa_workers", 4)

    for bench in cfg["benchmarks"]:
        dataset = json.loads(Path(bench["dataset"]).read_text())
        out_path = out_dir / f"{bench['name']}.json"
        done = json.loads(out_path.read_text()) if out_path.exists() else {"rows": []}
        have = {(r["grace"], r.get("model")) for r in done["rows"]}
        for grace in cfg["grace_grid"]:
            g = _grace_label(grace)
            need_ret = (g, None) not in have
            need_models = [m for m in models if (g, m) not in have]
            if not need_ret and not need_models:
                print(f"[skip] {bench['name']} grace={g}")
                continue
            print(f"[run ] {bench['name']} grace={g}")
            built = []
            for i, convo in enumerate(dataset["conversations"]):
                graph, policy, t_last = build(convo, i, grace, bench, cfg, embedder)
                qs = probes(convo)[:limit] if limit else probes(convo)
                built.append((graph, policy, t_last, qs))
            if need_ret:
                rows = [retrieval_row(gr, po, q, k, t) for gr, po, t, qs in built for q in qs]
                stats = [gr.stats() for gr, _, _, _ in built]
                done["rows"].append({
                    "grace": g, "model": None, "n": len(rows),
                    "current_gold": _mean(r["current_gold"] for r in rows),
                    "current_stale": _mean(r["current_stale"] for r in rows),
                    "wasted_slots": _mean(r["wasted_slots"] for r in rows),
                    "history_stored": _mean(r["history_stored"] for r in rows),
                    "history_support": _mean(r["history_support"] for r in rows),
                    "active_facts": sum(s["active_facts"] for s in stats),
                    "pruned": sum(s["pruned"] for s in stats),
                    "closure_ages": [r["closure_age_days"] for r in rows
                                     if r["closure_age_days"] is not None],
                })
            for m in need_models:
                prov = answerers[m]
                mt = cfg.get("answer_max_tokens", {}).get(m, 1024)

                def one(item, prov=prov, mt=mt):
                    gr, po, t, q = item
                    cur = answer_current(gr, po, q, prov, k, t, mt)
                    his = answer_history(gr, q, prov, k, t, mt)
                    hq = HISTORY_TEMPLATE.format(q=q["question"])
                    return {"question": q["question"],
                            "current_answer": cur, "history_answer": his,
                            "current_correct": judge_answer(q["question"], q["answer"], cur,
                                                            judge)["correct"],
                            "history_correct": judge_answer(hq, q["stale_answer"], his,
                                                            judge)["correct"]}

                items = [(gr, po, t, q) for gr, po, t, qs in built for q in qs]
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    recs = list(ex.map(one, items))
                done["rows"].append({
                    "grace": g, "model": m, "n": len(recs),
                    "current_acc": _mean(r["current_correct"] for r in recs),
                    "history_acc": _mean(r["history_correct"] for r in recs),
                    "records": recs})
                print(f"       {m.split('/')[-1]}: current {done['rows'][-1]['current_acc']:.3f} "
                      f"history {done['rows'][-1]['history_acc']:.3f}   {SpendLedger.report()}")
            out_path.write_text(json.dumps(done, indent=1))
        print(f"wrote {out_path}")


def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def analyze(cfg: dict) -> None:
    out_dir = Path(cfg["results_dir"])
    lines = ["# Grace period with history questions", ""]
    for bench in cfg["benchmarks"]:
        p = out_dir / f"{bench['name']}.json"
        if not p.exists():
            continue
        rows = json.loads(p.read_text())["rows"]
        ret = [r for r in rows if r["model"] is None]
        if not ret:
            continue
        order = {_grace_label(g): i for i, g in enumerate(cfg["grace_grid"])}
        ret.sort(key=lambda r: order.get(r["grace"], 99))
        ages = max((r["closure_ages"] for r in ret), key=len)
        lines += [f"## {bench['name']}", "",
                  f"Closed facts at question time: {len(ages)}; age in days: "
                  + (f"median {statistics.median(ages):.1f}, max {max(ages):.1f}" if ages else "n/a"),
                  "",
                  "| grace (days) | current gold in context | wasted slots | history stored "
                  "| history in context | active facts |",
                  "|---|---|---|---|---|---|"]
        for r in ret:
            lines.append(f"| {r['grace']} | {r['current_gold']:.3f} | {r['wasted_slots']:.2f} | "
                         f"{r['history_stored']:.3f} | {r['history_support']:.3f} | "
                         f"{r['active_facts']} |")
        ans = [r for r in rows if r["model"] is not None]
        if ans:
            lines += ["", "| grace | model | current accuracy | history accuracy |",
                      "|---|---|---|---|"]
            for r in sorted(ans, key=lambda r: (r["model"], order.get(r["grace"], 99))):
                lines.append(f"| {r['grace']} | {r['model'].split('/')[-1]} | "
                             f"{r['current_acc']:.3f} | {r['history_acc']:.3f} |")
        lines.append("")
    text = "\n".join(lines)
    (out_dir / "grace_history.md").write_text(text)
    print(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "analyze"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--answers", action="store_true", help="also answer and grade (paid)")
    ap.add_argument("--limit", type=int, help="probes per conversation, for a dry run")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if args.command == "run":
        run(cfg, args.answers, args.limit)
    else:
        analyze(cfg)


if __name__ == "__main__":
    main()
