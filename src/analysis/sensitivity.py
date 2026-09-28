"""Sensitivity analysis for every fixed constant in the DRIFT pipeline.

Why this exists
---------------
The thesis fixes four numbers by design rather than by search: the hybrid
retrieval weighting (0.6 semantic, 0.3 lexical, 0.1 recency), the retrieval
depth (k = 25), P1's time-to-live (20 days), P2's grace period (7 days), and
P3's novelty threshold (tau = 0.9). Holding them identical across every policy
and every benchmark is what makes the comparison controlled: a constant cannot
explain a difference between two conditions that both received it.

That argument answers "could this constant have biased the comparison?" but not
"would a different constant have changed the conclusion?". This module answers
the second question by sweeping each constant and reporting whether the ordering
of the policies survives.

Intrinsic metrics, not end-task accuracy
----------------------------------------
Sweeping with the full pipeline would mean an answer-model call and a judge call
per question per setting, which is thousands of paid calls and reintroduces
judge noise into a measurement about retrieval. Instead this module measures the
retrieval step directly, before any model is called:

  gold_support    the gold answer string appears in some retrieved fact, so the
                  answer model *could* answer correctly. Retrieval's actual job.
  stale_exposure  the superseded answer string appears in some retrieved fact,
                  so the answer model *could* answer staleley.
  clean           gold supported and stale not exposed: the unambiguous case.
  wasted_slots    facts that occupied one of the k slots and were then dropped by
                  policy.on_retrieve, so they cost retrieval budget and bought
                  nothing. This is the only channel through which P2's grace
                  period can affect anything, since on_retrieve already excludes
                  invalidated facts regardless of their age.
  ctx_facts       facts actually handed to the answer model.

These are deterministic, free, and judge-independent. `--validate` checks the
proxy against reality by correlating gold_support with the graded per-question
outcomes of a campaign that was actually run.

Usage
-----
    python -m analysis.sensitivity --config configs/sensitivity.json
    python -m analysis.sensitivity --config configs/sensitivity.json --sweep weights
    python -m analysis.sensitivity --config configs/sensitivity.json --validate \\
        --results artifacts/results/mquake_t
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from drift.embeddings import make_embedder
from drift.memory.graph import DEFAULT_RETRIEVAL_WEIGHTS, BitemporalGraph
from drift.pipeline import ingest_session, render_fact
from drift.policies import make_policy
from drift.providers import BaseProvider, FallbackProvider, make_provider

# Sweep grids. Coarse on purpose: the claim being tested is "the ordering is
# stable across a plausible range", not "here is the optimum to three decimals".
WEIGHT_STEP = 0.1
K_GRID = [5, 10, 25, 50]
GRACE_GRID = [0.0, 1.0, 3.0, 7.0, 14.0, 30.0]
TTL_GRID = [5.0, 10.0, 20.0, 30.0, 60.0]
TAU_GRID = [0.80, 0.85, 0.90, 0.95, 0.99]


class MemoEmbedder:
    """Memoizing wrapper. A sweep re-embeds the same questions and the same fact
    text hundreds of times; with a network-backed embedder that is the dominant
    cost and it is entirely redundant, since the embedding of a string never
    changes within a run."""

    def __init__(self, inner):
        self.inner = inner
        self.name = getattr(inner, "name", "wrapped")
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        hit = self._cache.get(text)
        if hit is None:
            hit = self.inner.embed(text)
            self._cache[text] = hit
        return hit


def _extract_provider(cfg: dict) -> BaseProvider:
    """Build the extraction provider, honouring a list with fallback.

    The runner has always accepted a list here and failed over between entries.
    This harness used to take a single spec, so one dead endpoint aborted the
    whole sweep rather than degrading. That is exactly what happened when NVIDIA
    stopped serving a model mid-project: the cached benchmarks were unaffected
    because they never touched the network, but a new dataset hit the live
    endpoint and the run died. Matching the runner's behaviour removes that
    failure mode.
    """
    spec = cfg.get("extract_model", "mock")
    specs = spec if isinstance(spec, list) else [spec]
    cache_dir = cfg.get("cache_dir", ".drift_cache")
    retries = 2 if len(specs) > 1 else 4
    providers = [make_provider(x, cache_dir, max_retries=retries) for x in specs]
    return providers[0] if len(providers) == 1 else FallbackProvider(providers)


def simplex_grid(step: float = WEIGHT_STEP) -> list[tuple[float, float, float]]:
    """All (semantic, lexical, recency) weightings on a simplex of the given step."""
    n = round(1.0 / step)
    out = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            k = n - i - j
            out.append((round(i * step, 3), round(j * step, 3), round(k * step, 3)))
    return out


def build_graph(convo: dict, policy_spec: str, cfg: dict, embedder, provider):
    """Ingest one conversation under one policy. Extraction calls are served from
    the run cache after a campaign has been run, so this costs nothing new."""
    graph = BitemporalGraph(embedder, functional_predicates=_fp(cfg))
    policy = make_policy(policy_spec)
    t_last = 0.0
    for session in convo["sessions"]:
        ingest_session(session, graph, policy, provider)
        t_last = max(t_last, session["time"])
    return graph, policy, t_last


def _fp(cfg: dict):
    fp = cfg.get("functional_predicates")
    if fp is None or fp == "*":
        return fp
    return set(fp)


def _supported(facts, needle: str | None) -> bool:
    if not needle:
        return False
    n = needle.lower()
    return any(n in f.text.lower() for f in facts)


def measure(graph, policy, questions: list[dict], k: int,
            weights: tuple[float, float, float], now: float) -> dict:
    """Intrinsic retrieval metrics for one setting. No model is called."""
    gold_hits = stale_hits = clean_hits = 0
    wasted = ctx_facts = ctx_chars = 0
    n_stale_annotated = 0
    for q in questions:
        pre = graph.search(q["question"], k=k, now=now, weights=weights)
        post = policy.on_retrieve(pre, now=now)
        gold_ok = _supported(post, q.get("answer"))
        stale_ok = _supported(post, q.get("stale_answer"))
        gold_hits += gold_ok
        if q.get("stale_answer"):
            n_stale_annotated += 1
            stale_hits += stale_ok
        clean_hits += gold_ok and not stale_ok
        wasted += len(pre) - len(post)
        ctx_facts += len(post)
        ctx_chars += sum(len(render_fact(f)) for f in post)
    n = max(1, len(questions))
    stats = graph.stats()
    return {
        "n_questions": len(questions),
        "gold_support": gold_hits / n,
        "stale_exposure": stale_hits / max(1, n_stale_annotated),
        "clean": clean_hits / n,
        "wasted_slots": wasted / n,
        "ctx_facts": ctx_facts / n,
        # ~4 chars per token is the usual rule of thumb; used only to compare
        # settings against each other, never reported as an absolute cost.
        "est_ctx_tokens": ctx_chars / n / 4.0,
        "active_facts": stats["active_facts"],
        "pruned": stats["pruned"],
        "invalidated_active": stats["invalidated_active"],
    }


def _agg(per_convo: list[dict]) -> dict:
    """Question-weighted mean across conversations."""
    total_q = sum(r["n_questions"] for r in per_convo) or 1
    out = {}
    for key in per_convo[0]:
        if key == "n_questions":
            continue
        if key in ("active_facts", "pruned", "invalidated_active"):
            out[key] = sum(r[key] for r in per_convo)
        else:
            out[key] = sum(r[key] * r["n_questions"] for r in per_convo) / total_q
    out["n_questions"] = total_q
    return out


def evaluate(dataset: dict, policy_spec: str, cfg: dict, embedder, provider,
             k: int, weights: tuple[float, float, float], graphs=None) -> dict:
    """One (policy, k, weights) point. `graphs` reuses already-ingested graphs,
    which is what makes the weight and k sweeps cheap."""
    rows = []
    for idx, convo in enumerate(dataset["conversations"]):
        if graphs is not None:
            graph, policy, t_last = graphs[idx]
        else:
            graph, policy, t_last = build_graph(convo, policy_spec, cfg, embedder, provider)
        rows.append(measure(graph, policy, convo["questions"], k, weights, t_last))
    return _agg(rows)


# --------------------------------------------------------------------- sweeps

def sweep_weights(dataset, cfg, embedder, provider) -> list[dict]:
    grid = simplex_grid(cfg.get("weight_step", WEIGHT_STEP))
    # The published weighting must always be evaluated, even when it does not
    # land on the grid for a coarse step, since every stability claim is stated
    # relative to it.
    published = tuple(cfg.get("weights", DEFAULT_RETRIEVAL_WEIGHTS))
    if published not in grid:
        grid.append(published)
    k = cfg.get("retrieval_k", 25)
    out = []
    for policy_spec in cfg["policies"]:
        graphs = [build_graph(c, policy_spec, cfg, embedder, provider)
                  for c in dataset["conversations"]]
        for w in grid:
            res = evaluate(dataset, policy_spec, cfg, embedder, provider, k, w, graphs)
            out.append({"sweep": "weights", "policy": policy_spec, "k": k,
                        "w_sem": w[0], "w_lex": w[1], "w_rec": w[2], **res})
    return out


def sweep_k(dataset, cfg, embedder, provider) -> list[dict]:
    w = tuple(cfg.get("weights", DEFAULT_RETRIEVAL_WEIGHTS))
    out = []
    for policy_spec in cfg["policies"]:
        graphs = [build_graph(c, policy_spec, cfg, embedder, provider)
                  for c in dataset["conversations"]]
        for k in cfg.get("k_grid", K_GRID):
            res = evaluate(dataset, policy_spec, cfg, embedder, provider, k, w, graphs)
            out.append({"sweep": "k", "policy": policy_spec, "k": k,
                        "w_sem": w[0], "w_lex": w[1], "w_rec": w[2], **res})
    return out


def _sweep_policy_param(dataset, cfg, embedder, provider, base: str,
                        param: str, grid: list[float]) -> list[dict]:
    """Sweeps a parameter that changes ingestion or maintenance, so the graph has
    to be rebuilt for each value (extraction is cached, so this is embedding and
    graph work only)."""
    w = tuple(cfg.get("weights", DEFAULT_RETRIEVAL_WEIGHTS))
    k = cfg.get("retrieval_k", 25)
    out = []
    for value in grid:
        spec = f"{base}:{param}={value}"
        res = evaluate(dataset, spec, cfg, embedder, provider, k, w)
        out.append({"sweep": param, "policy": base, param: value, "k": k,
                    "w_sem": w[0], "w_lex": w[1], "w_rec": w[2], **res})
    return out


def sweep_grace(dataset, cfg, embedder, provider):
    return _sweep_policy_param(dataset, cfg, embedder, provider, "P2", "grace_days",
                               cfg.get("grace_grid", GRACE_GRID))


def sweep_ttl(dataset, cfg, embedder, provider):
    return _sweep_policy_param(dataset, cfg, embedder, provider, "P1", "ttl_days",
                               cfg.get("ttl_grid", TTL_GRID))


def sweep_tau(dataset, cfg, embedder, provider):
    return _sweep_policy_param(dataset, cfg, embedder, provider, "P3", "tau",
                               cfg.get("tau_grid", TAU_GRID))


SWEEPS = {"weights": sweep_weights, "k": sweep_k, "grace": sweep_grace,
          "ttl": sweep_ttl, "tau": sweep_tau}


# ----------------------------------------------------------------- reporting

def rank_stability(rows: list[dict], metric: str = "clean",
                   published: tuple[float, float, float] | None = None) -> dict:
    """Across every weighting in the grid, does the policy ordering hold?

    This is the actual claim the thesis needs: not that 0.6/0.3/0.1 is optimal,
    but that the conclusion drawn under it is not an artifact of it.
    """
    by_setting: dict[tuple, dict[str, float]] = defaultdict(dict)
    for r in rows:
        key = (r.get("w_sem"), r.get("w_lex"), r.get("w_rec"), r.get("k"))
        by_setting[key][r["policy"]] = r[metric]
    policies = sorted({r["policy"] for r in rows})
    pub = tuple(published or DEFAULT_RETRIEVAL_WEIGHTS)
    default_key = (pub[0], pub[1], pub[2], rows[0].get("k"))
    baseline = by_setting.get(default_key)
    if baseline is None:
        baseline = by_setting[next(iter(by_setting))]
    ref_order = sorted(policies, key=lambda p: -baseline.get(p, 0.0))
    agree = 0
    # Pairs are counted in reference order, so "held" always means "the ordering
    # observed at the published setting was not reversed here".
    pairwise = {(a, b): [0, 0, 0] for i, a in enumerate(ref_order) for b in ref_order[i + 1:]}
    for scores in by_setting.values():
        order = sorted(policies, key=lambda p: -scores.get(p, 0.0))
        agree += order == ref_order
        for (a, b), cell in pairwise.items():
            if a in scores and b in scores:
                cell[0] += 1
                cell[1] += scores[a] > scores[b]
                cell[2] += scores[a] == scores[b]
    return {
        "reference_order": ref_order,
        "settings": len(by_setting),
        "identical_order": agree,
        "identical_order_pct": 100.0 * agree / max(1, len(by_setting)),
        "pairwise": {f"{a} > {b}": {"settings": n, "held": h, "ties": t,
                                    "reversed": n - h - t,
                                    "pct": 100.0 * h / max(1, n)}
                     for (a, b), (n, h, t) in pairwise.items()},
    }


def validate_proxy(dataset: dict, cfg: dict, embedder, provider,
                   results_dir: Path) -> list[dict]:
    """Does gold_support actually predict a correct graded answer?

    For each policy cell that was really run, recompute retrieval offline and
    cross-tabulate gold_support against the judge's verdict for the same
    question. If the proxy is informative, accuracy given support should be far
    above accuracy given no support.
    """
    w = tuple(cfg.get("weights", DEFAULT_RETRIEVAL_WEIGHTS))
    k = cfg.get("retrieval_k", 25)
    out = []
    for cell in sorted(results_dir.glob("*.json")):
        if cell.name in ("summary_table.json", "live.json"):
            continue
        payload = json.loads(cell.read_text())
        summary = payload.get("summary", {})
        policy_spec = summary.get("policy")
        if not policy_spec or policy_spec.startswith("NOMEM"):
            continue
        graded = {r["question"]: bool(r["correct"]) for r in payload.get("records", [])}
        if not graded:
            continue
        graphs = [build_graph(c, policy_spec, cfg, embedder, provider)
                  for c in dataset["conversations"]]
        cells = {"supported_correct": 0, "supported_wrong": 0,
                 "unsupported_correct": 0, "unsupported_wrong": 0}
        for idx, convo in enumerate(dataset["conversations"]):
            graph, policy, t_last = graphs[idx]
            for q in convo["questions"]:
                if q["question"] not in graded:
                    continue
                pre = graph.search(q["question"], k=k, now=t_last, weights=w)
                post = policy.on_retrieve(pre, now=t_last)
                sup = _supported(post, q.get("answer"))
                ok = graded[q["question"]]
                cells[f"{'supported' if sup else 'unsupported'}_{'correct' if ok else 'wrong'}"] += 1
        n_sup = cells["supported_correct"] + cells["supported_wrong"]
        n_uns = cells["unsupported_correct"] + cells["unsupported_wrong"]
        out.append({
            "cell": cell.stem, "policy": policy_spec, "model": summary.get("model"),
            "reported_accuracy": summary.get("accuracy"),
            "acc_given_support": cells["supported_correct"] / n_sup if n_sup else None,
            "acc_given_no_support": cells["unsupported_correct"] / n_uns if n_uns else None,
            "n_supported": n_sup, "n_unsupported": n_uns,
            "phi": _phi(cells),
        })
    return out


def _phi(c: dict) -> float | None:
    """Phi coefficient for the 2x2 support-by-correctness table."""
    a, b = c["supported_correct"], c["supported_wrong"]
    d, e = c["unsupported_correct"], c["unsupported_wrong"]
    num = a * e - b * d
    den = math.sqrt((a + b) * (d + e) * (a + d) * (b + e))
    return num / den if den else None


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def to_markdown(rows: list[dict], title: str, columns: list[str]) -> str:
    lines = [f"### {title}", "",
             "| " + " | ".join(columns) + " |",
             "|" + "|".join(["---"] * len(columns)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(_fmt(r.get(c, "")) for c in columns) + " |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="DRIFT hyperparameter sensitivity analysis")
    ap.add_argument("--config", required=True)
    ap.add_argument("--sweep", default="all",
                    choices=["all", *SWEEPS.keys()])
    ap.add_argument("--validate", action="store_true",
                    help="cross-tabulate offline gold_support against graded answers")
    ap.add_argument("--results", help="results dir to validate against")
    ap.add_argument("--out", help="output directory (default artifacts/sensitivity)")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    dataset = json.loads(Path(cfg["dataset"]).read_text())
    embedder = MemoEmbedder(make_embedder(cfg.get("embedder", "hashing")))
    provider = _extract_provider(cfg)
    out_dir = Path(args.out or cfg.get("out_dir", "artifacts/sensitivity"))
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = cfg.get("name", Path(cfg["dataset"]).stem)

    if args.validate:
        results_dir = Path(args.results or cfg["results_dir"])
        rows = validate_proxy(dataset, cfg, embedder, provider, results_dir)
        (out_dir / f"{tag}_validation.json").write_text(json.dumps(rows, indent=1))
        md = to_markdown(rows, f"Proxy validation on {tag}",
                         ["cell", "reported_accuracy", "acc_given_support",
                          "acc_given_no_support", "n_supported", "n_unsupported", "phi"])
        (out_dir / f"{tag}_validation.md").write_text(md)
        print(md)
        return

    names = list(SWEEPS) if args.sweep == "all" else [args.sweep]
    all_rows: dict[str, list[dict]] = {}
    report = [f"# Sensitivity analysis: {tag}", "",
              f"Dataset: `{cfg['dataset']}`  |  embedder: `{cfg.get('embedder', 'hashing')}`  "
              f"|  default weights: {DEFAULT_RETRIEVAL_WEIGHTS}  |  default k: {cfg.get('retrieval_k', 25)}",
              ""]
    for name in names:
        print(f"[sweep] {name}")
        rows = SWEEPS[name](dataset, cfg, embedder, provider)
        all_rows[name] = rows
        if name == "weights":
            pub = tuple(cfg.get("weights", DEFAULT_RETRIEVAL_WEIGHTS))
            stab = rank_stability(rows, published=pub)
            report.append(to_markdown(
                [r for r in rows if (r["w_sem"], r["w_lex"], r["w_rec"]) == pub],
                "Weights: value at the published setting",
                ["policy", "w_sem", "w_lex", "w_rec", "gold_support", "stale_exposure",
                 "clean", "wasted_slots", "ctx_facts"]))
            report.append(f"Ordering by `clean` at the published weighting: "
                          f"{' > '.join(stab['reference_order'])}. "
                          f"That exact ordering holds in {stab['identical_order']} of "
                          f"{stab['settings']} weightings on the simplex "
                          f"({stab['identical_order_pct']:.1f} percent).\n")
            report.append(to_markdown(
                [{"pair": p, **v} for p, v in stab["pairwise"].items()],
                "Weights: pairwise ordering stability across the whole simplex",
                ["pair", "settings", "held", "ties", "reversed", "pct"]))
            (out_dir / f"{tag}_weights_stability.json").write_text(json.dumps(stab, indent=1))
        elif name == "k":
            report.append(to_markdown(rows, "Retrieval depth k",
                                      ["policy", "k", "gold_support", "stale_exposure",
                                       "clean", "wasted_slots", "ctx_facts", "est_ctx_tokens"]))
        else:
            param = rows[0]["sweep"]
            report.append(to_markdown(rows, f"Policy parameter: {param}",
                                      ["policy", param, "gold_support", "stale_exposure",
                                       "clean", "wasted_slots", "ctx_facts",
                                       "active_facts", "pruned"]))

    (out_dir / f"{tag}_sensitivity.json").write_text(json.dumps(all_rows, indent=1))
    md_path = out_dir / f"{tag}_sensitivity.md"
    md_path.write_text("\n".join(report))
    print("\n".join(report))
    print(f"\nWrote {md_path}")


if __name__ == "__main__":
    main()
