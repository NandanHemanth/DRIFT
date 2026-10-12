"""Deep sensitivity analysis of the hybrid retrieval weights, end to end.

What the committee asked for
----------------------------
Try every one of ten values for each retrieval weight (semantic, lexical,
recency) and show what changing each one does to the results. That is a full
10 x 10 x 10 factorial: 1,000 weightings, each run through the real pipeline
with real answers and real grades.

Why it is affordable
--------------------
Two facts make this tractable on a laptop.

1. Retrieval only depends on the *ratio* between the weights. Multiplying all
   three by the same number rescales every score and leaves the ranking alone,
   so (0.2, 0.2, 0.2) and (0.5, 0.5, 0.5) produce the same context. Of the 1,000
   grid points only 841 are distinct rankings.
2. Even distinct rankings often put the same facts in the same order for a given
   question. The answer model only ever sees the prompt, so two weightings that
   yield the same prompt must yield the same answer. Every prompt is therefore
   answered once and the result is shared across every weighting that produced
   it. The provider disk cache makes this exact and resumable.

Three stages
------------
  plan     Build each benchmark's memory once per policy (extraction comes from
           the run cache), compute every weighting's context for every question,
           record the free retrieval metrics, and write the unique prompts.
           Prints the exact number of model calls stage 2 will make. No answer
           or judge model is called.
  run      Answer every unique prompt with every answer model, grade each answer
           with the judge, append to a results file. Resumable at any point.
  analyze  Expand the answers back onto the full grid and produce every analysis
           in paper/DEEP_SENSITIVITY.md plus figures.

Usage
-----
    python -m analysis.deep_sensitivity plan    --config configs/deep_sensitivity.json
    python -m analysis.deep_sensitivity run     --config configs/deep_sensitivity.json
    python -m analysis.deep_sensitivity analyze --config configs/deep_sensitivity.json

Everything replicates the runner exactly: same graph construction, same policy
hooks, same `now`, same k, same prompt rendering, same answer and judge prompts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path

import numpy as np

from analysis.sensitivity import MemoEmbedder, _extract_provider, _fp
from drift.embeddings import make_embedder
from drift.memory.graph import BitemporalGraph
from drift.pipeline import (ANSWER_PROMPT, ANSWER_SYSTEM, ingest_session, judge_answer,
                            render_fact, token_f1)
from drift.policies import make_policy
from drift.providers import make_provider
from drift.runner import staleness_hit

PUBLISHED = (0.6, 0.3, 0.1)
SIGNALS = ("semantic", "lexical", "recency")

# Typed short values, identical to scripts/download_convomem.py. Used only to
# recover a short gold needle when the gold answer is a full sentence, so that
# the free gold-support metric works on ConvoMem too.
_VALUE_PATTERNS = [
    r"\$\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?\b",
    r"\b\d+(?:\.\d+)?\s?%",
    r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)\b",
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b",
    r"\b\d[\d,]*(?:\.\d+)?\b",
]


# ------------------------------------------------------------------ helpers

def grid_values(cfg: dict) -> list[float]:
    return [round(v, 4) for v in cfg.get("grid_values", [i / 10 for i in range(1, 11)])]


def full_grid(values: list[float]) -> list[tuple[float, float, float]]:
    return [(a, b, c) for a in values for b in values for c in values]


def design_weightings(grid, designs) -> list[int]:
    """Indices of the weightings a design asks to run end to end.

    designs is a list of strings, combined as a union:
      "full"                 every weighting in the grid
      "oat"                  one weight at a time: all values of each weight with
                             the other two held at the published 0.6 / 0.3 / 0.1
      "factorial:a,b,c,..."  the full factorial over just those values
    """
    idx = {tuple(round(x, 4) for x in w): i for i, w in enumerate(grid)}
    vals = sorted({round(w[0], 4) for w in grid})
    out = set()
    for d in designs:
        if d == "full":
            out |= set(range(len(grid)))
        elif d == "oat":
            for ax in range(3):
                for v in vals:
                    w = list(PUBLISHED)
                    w[ax] = v
                    key = tuple(round(x, 4) for x in w)
                    if key in idx:
                        out.add(idx[key])
        elif d.startswith("factorial:"):
            fv = [round(float(x), 4) for x in d.split(":", 1)[1].split(",")]
            for a in fv:
                for b in fv:
                    for c in fv:
                        if (a, b, c) in idx:
                            out.add(idx[(a, b, c)])
        else:
            raise ValueError(f"unknown design {d!r}")
    return sorted(out)


def factorial_values(designs) -> list[float] | None:
    for d in designs:
        if d.startswith("factorial:"):
            return [round(float(x), 4) for x in d.split(":", 1)[1].split(",")]
    return None


def direction(w) -> tuple:
    """Scale-free identity of a weighting: the rounded shares."""
    s = sum(w)
    return tuple(round(x / s, 9) for x in w)


def gold_needle(q: dict) -> str:
    """Short string whose presence in a fact means the gold answer is available.

    Most benchmarks store a short gold value already. ConvoMem stores a sentence
    ("The call is scheduled for 10 AM."), which never appears inside a fact, so
    the free sweep reported gold support near zero there. Recover the typed value
    the sentence asserts, skipping the superseded one.
    """
    gold = q.get("answer_value") or q["answer"]
    if len(gold) <= 40:
        return gold
    stale = (q.get("stale_answer") or "").lower()
    for pat in _VALUE_PATTERNS:
        for m in re.finditer(pat, gold):
            v = m.group(0).strip()
            if v.lower() != stale:
                return v
    return gold


def rule_grade(answer: str, gold: str, stale: str | None) -> bool | None:
    """Decide the unambiguous cases without a model call; None means "ask the judge".

    Two cases are clear-cut. An empty or "I don't know" answer is never correct.
    A short answer that contains the gold value and not the superseded one is
    correct. Everything else, including long answers that recite the history of
    a fact, goes to the LLM judge, because that is exactly where a string match
    is too lenient.

    Checked against the first 200 judge-graded answers of this sweep before use:
    it decided 111 of them and agreed with the judge on 110; the one disagreement
    was an answer reading "[2024-02-05]: Erik ten Hag" for gold "Erik ten Hag",
    where the judge was the one in error.
    """
    a = answer.lower().strip()
    if not a or "don't know" in a or "do not know" in a:
        return False
    needle = gold_needle({"answer": gold, "stale_answer": stale}).lower()
    if needle in a and not (stale and stale.lower() in a):
        if len(a) <= len(needle) + 40:
            return True
        # A single plain sentence that names the gold value and never the old one
        # ("The current head of the Italy government is Giorgia Meloni."). qwen3
        # answers in full sentences, which sent 94% of its answers to the judge.
        # Checked against 1,441 judge-graded answers from this sweep before use:
        # this case decides 1,157 of them and agrees with the judge on 1,156.
        # Longer answers still go to the judge; beyond ~100 characters they start
        # listing several people ("Rishi Sunak ... and Charles ...").
        if len(a) <= 100 and a.count(".") <= 2:
            return True
    return None


def audit_pick(h: str, rate: int = 20) -> bool:
    """Deterministic 1-in-`rate` sample of rule-graded answers that the judge
    also grades, so rule-judge agreement keeps being measured on this data."""
    return int(h[:8], 16) % rate == 0


def order_context(post, order: str, position: dict):
    """The facts exactly as the answer model will see them.

    "rank" (the thesis pipeline): best retrieval score first.
    "date": the same facts, oldest first, ties broken by the order the facts
    were written to memory. The weights still decide *which* facts are in the
    prompt; they no longer decide the order. Two weightings that retrieve the
    same set of facts therefore produce the identical prompt, which is what
    makes the full 1,000-weighting grid affordable, and it isolates the thing
    the weights exist to control.
    """
    if order == "rank":
        return post
    if order == "date":
        return sorted(post, key=lambda f: (f.t_valid_start, position[f.id]))
    raise ValueError(f"unknown context_order {order!r}")


THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def strip_thinking(text: str) -> str:
    """Remove a reasoning model's visible <think> block, keeping only the answer."""
    return THINK_RE.sub("", text).strip()


def _first_rank(facts, needle: str | None) -> int:
    """1-based rank of the first fact containing needle, 0 if absent."""
    if not needle:
        return 0
    n = needle.lower()
    for i, f in enumerate(facts, 1):
        if n in f.text.lower():
            return i
    return 0


def phash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def out_dir(cfg: dict) -> Path:
    p = Path(cfg.get("out_dir", "artifacts/deep_sensitivity"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _dump_gz(path: Path, obj) -> None:
    with gzip.open(path, "wt") as f:
        json.dump(obj, f)


def _load_gz(path: Path):
    with gzip.open(path, "rt") as f:
        return json.load(f)


# ------------------------------------------------------------------ stage 1

def build_graph(convo, policy_spec, cfg, embedder, extractor):
    graph = BitemporalGraph(embedder, functional_predicates=_fp(cfg))
    policy = make_policy(policy_spec)
    t_last = 0.0
    for session in convo["sessions"]:
        ingest_session(session, graph, policy, extractor)
        t_last = max(t_last, session["time"])
    return graph, policy, t_last


def contexts_for_question(graph, policy, question, now, k, grid):
    """Every weighting's post-policy context for one question.

    Replicates BitemporalGraph.search exactly: same candidate set, same signals,
    the same left-to-right float arithmetic, and a stable descending sort so ties
    break in insertion order just as Python's sorted(reverse=True) does.
    """
    candidates = [f for f in graph.facts.values() if f.active]
    if not candidates:
        return [([], []) for _ in grid]
    sig = graph._signals(question, candidates, now)
    S = np.array([sig[f.id] for f in candidates], dtype=np.float64)
    out, memo = [], {}
    for w in grid:
        score = w[0] * S[:, 0] + w[1] * S[:, 1] + w[2] * S[:, 2]
        order = np.argsort(-score, kind="stable")[:k]
        key = tuple(order.tolist())
        if key not in memo:
            pre = [candidates[i] for i in order]
            memo[key] = (pre, policy.on_retrieve(pre, now=now))
        out.append(memo[key])
    return out


def plan(cfg: dict) -> None:
    values = grid_values(cfg)
    grid = full_grid(values)
    # Walk the grid in a shuffled order (published first) so that if stage 2 is
    # stopped early, the completed weightings are spread across the whole grid
    # rather than bunched in one corner.
    order = list(range(len(grid)))
    random.Random(cfg.get("seed", 7)).shuffle(order)
    if PUBLISHED in grid:
        pi = grid.index(PUBLISHED)
        order.remove(pi)
        order.insert(0, pi)

    rank = {wi: r for r, wi in enumerate(order)}
    distinct = len({direction(w) for w in grid})
    print(f"grid: {len(values)} values per weight -> {len(grid)} weightings, "
          f"{distinct} distinct rankings")
    k = cfg.get("retrieval_k", 25)
    show_sup = cfg.get("show_supersession", False)
    ctx_order = cfg.get("context_order", "rank")
    print(f"context order in prompts: {ctx_order}")
    embedder = MemoEmbedder(make_embedder(cfg.get("embedder", "hashing")))
    policies = cfg.get("policies", ["P0", "P2"])
    d = out_dir(cfg)
    summary = {}

    for bench in cfg["benchmarks"]:
        name, bcfg = bench["name"], {**cfg, **bench}
        dataset = json.loads(Path(bench["dataset"]).read_text())
        extractor = _extract_provider(bcfg)
        questions = [{"conversation": c["id"], "question": q["question"], "gold": q["answer"],
                      "stale": q.get("stale_answer"), "needle": gold_needle(q)}
                     for c in dataset["conversations"] for q in c["questions"]]
        nq = len(questions)
        prompts: dict[str, dict] = {}
        prompt_order: list[str] = []
        per_policy = {}
        t0 = time.time()
        for pol in policies:
            fields = {x: [[0] * nq for _ in grid] for x in
                      ("prompt", "gold_rank", "stale_rank", "ctx_facts", "ctx_chars", "wasted")}
            qi = 0
            for convo in dataset["conversations"]:
                graph, policy, t_last = build_graph(convo, pol, bcfg, embedder, extractor)
                position = {fid: i for i, fid in enumerate(graph.facts)}
                for q in convo["questions"]:
                    ctxs = contexts_for_question(graph, policy, q["question"], t_last, k, grid)
                    meta = questions[qi]
                    for wi, (pre, post) in enumerate(ctxs):
                        shown = order_context(post, ctx_order, position)
                        block = "\n".join(render_fact(f, show_sup) for f in shown) \
                            or "(no relevant memory)"
                        prompt = ANSWER_PROMPT.format(memory=block, question=q["question"])
                        h = phash(prompt)
                        if h not in prompts:
                            prompts[h] = {"h": h, "qi": qi, "prompt": prompt,
                                          "question": q["question"], "gold": meta["gold"],
                                          "stale": meta["stale"], "first": rank[wi]}
                        elif rank[wi] < prompts[h]["first"]:
                            prompts[h]["first"] = rank[wi]
                        fields["prompt"][wi][qi] = h
                        fields["gold_rank"][wi][qi] = _first_rank(post, meta["needle"])
                        fields["stale_rank"][wi][qi] = _first_rank(post, meta["stale"])
                        fields["ctx_facts"][wi][qi] = len(post)
                        fields["ctx_chars"][wi][qi] = len(block)
                        fields["wasted"][wi][qi] = len(pre) - len(post)
                    qi += 1
            per_policy[pol] = fields
            print(f"  {name} {pol}: done in {time.time() - t0:.0f}s, "
                  f"{len(prompts)} unique prompts so far")

        prompt_order = sorted(prompts, key=lambda h: prompts[h]["first"])
        _dump_gz(d / f"{name}_plan.json.gz", {
            "benchmark": name, "grid": grid, "order": order, "questions": questions,
            "policies": policies, "k": k, "fields": per_policy})
        with gzip.open(d / f"{name}_prompts.jsonl.gz", "wt") as f:
            for h in prompt_order:
                f.write(json.dumps(prompts[h]) + "\n")
        total_slots = len(policies) * len(grid) * nq
        summary[name] = {"questions": nq, "grid_points": len(grid),
                         "policy_weighting_question_slots": total_slots,
                         "unique_prompts": len(prompts),
                         "dedup_factor": round(total_slots / max(1, len(prompts)), 1)}

    models = cfg["answer_models"]
    n_prompts = sum(s["unique_prompts"] for s in summary.values())
    a_calls = n_prompts * len(models)
    spa = cfg.get("est_seconds_per_answer", 1.5)
    spj = cfg.get("est_seconds_per_judge", 3.0)
    hours = (a_calls * spa + a_calls * spj) / 3600 / max(1, cfg.get("workers", 1))
    summary["_totals"] = {"unique_prompts": n_prompts, "answer_calls": a_calls,
                          "judge_calls_upper_bound": a_calls,
                          "est_hours_at_config_speeds": round(hours, 1)}
    (d / "plan_summary.json").write_text(json.dumps(summary, indent=1))
    print("\n" + json.dumps(summary, indent=1))
    print(f"\nStage 2 will make {a_calls:,} answer calls and at most {a_calls:,} judge "
          f"calls (identical judge prompts are free). Rough time: {hours:.1f} h at "
          f"{spa}s/answer and {spj}s/judge with {cfg.get('workers', 1)} worker(s).")


# ------------------------------------------------------------------ stage 2

def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def _pool(cfg, fn, items, label, out_path, workers=None):
    """Run fn over items with a thread pool, appending results to out_path."""
    total = len(items)
    if not total:
        return
    t0, n = time.time(), 0
    with open(out_path, "a") as out, ThreadPoolExecutor(max_workers=workers or cfg.get("workers", 1)) as ex:
        futs = [ex.submit(fn, it) for it in items]
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001 - one bad call must not kill the run
                print(f"  [fail] {str(e)[:120]}")
                continue
            out.write(json.dumps(r) + "\n")
            out.flush()
            n += 1
            if n % 100 == 0 or n == total:
                el = time.time() - t0
                print(f"    {label}: {n}/{total}  {el / n:.2f}s each  "
                      f"eta {el / n * (total - n) / 60:.0f} min")


def run(cfg: dict, limit: int | None = None) -> None:
    """Answer and grade every unique prompt.

    Work is done in chunks of prompts, and within a chunk one model at a time:
    all answers from the first model, then the second, then every grade. Ollama
    keeps a model in memory while it is being used, so this loads each model
    once per chunk instead of swapping models on every call, which on a laptop
    is the difference between hours and days. Chunks follow the shuffled grid
    order, so a run stopped at any point leaves complete weightings spread
    across the whole grid.
    """
    d = out_dir(cfg)
    cache = cfg.get("cache_dir", ".drift_cache")
    models = cfg["answer_models"]
    judge_spec = cfg["judge_model"]
    ans_path, res_path = d / "answers.jsonl", d / "results.jsonl"
    answered = {(r["h"], r["m"]): r for r in _read_jsonl(ans_path)}
    graded = {(r["h"], r["m"]) for r in _read_jsonl(res_path)}

    designs = cfg.get("e2e_design", ["full"])
    prompts = []
    for bi, bench in enumerate(cfg["benchmarks"]):
        pl = _load_gz(d / f"{bench['name']}_plan.json.gz")
        ws = design_weightings([tuple(w) for w in pl["grid"]], designs)
        pols = cfg.get("e2e_policies", pl["policies"])
        need = {pl["fields"][pol]["prompt"][wi][qi] for pol in pols
                for wi in ws for qi in range(len(pl["questions"]))}
        with gzip.open(d / f"{bench['name']}_prompts.jsonl.gz", "rt") as f:
            for p in map(json.loads, f):
                if p["h"] in need:
                    p["bench_i"] = bi
                    prompts.append(p)
        print(f"  {bench['name']}: {len(ws)} weightings in design {designs}, policies {pols}, "
              f"{len(need)} unique prompts")
    if cfg.get("benchmarks_in_order", False):
        # finish the first benchmark completely before starting the next
        prompts.sort(key=lambda p: (p["bench_i"], p["first"]))
    else:
        prompts.sort(key=lambda p: p["first"])
    todo = [p for p in prompts if any((p["h"], m) not in graded for m in models)]
    print(f"{len(prompts)} unique prompts; {len(prompts) - len(todo)} fully done; "
          f"{len(todo)} to go ({len(todo) * len(models)} answers and grades at most)")
    if limit:
        todo = todo[:limit]
        print(f"--limit: doing the first {len(todo)} this run")
    chunk = cfg.get("chunk_prompts", 400)
    local = threading.local()

    def prov(spec):
        if not hasattr(local, "p"):
            local.p = {}
        if spec not in local.p:
            pv = make_provider(spec, cache)
            extras = cfg.get("request_extras", {}).get(spec)
            if extras:
                pv.extra_body = extras
            rpm = cfg.get("rpm_per_worker", {}).get(spec.split(":", 1)[0])
            if rpm:
                from drift.providers import RateLimiter
                pv.limiter = RateLimiter(rpm)
            if spec in cfg.get("answer_models", []):
                pv.reasoning_fallback = False  # an empty answer, never the thought trace
            local.p[spec] = pv
        return local.p[spec]

    for start in range(0, len(todo), chunk):
        part = todo[start:start + chunk]
        print(f"  chunk {start // chunk + 1}/{math.ceil(len(todo) / chunk)} ({len(part)} prompts)")
        for m in models:
            need = [p for p in part if (p["h"], m) not in answered]

            mt = cfg.get("answer_max_tokens", {}).get(m, 1024)

            def answer(p, m=m, mt=mt):
                # Reasoning models spend tokens thinking before they answer; the
                # default 1024 can run out mid-thought, so they get a larger budget.
                c = prov(m).complete(p["prompt"], system=ANSWER_SYSTEM, max_tokens=mt)
                return {"h": p["h"], "m": m, "answer": strip_thinking(c.text),
                        "tokens": c.total_tokens}

            _pool(cfg, answer, need, f"answer {m}", ans_path, cfg.get("answer_workers"))
        answered = {(r["h"], r["m"]): r for r in _read_jsonl(ans_path)}
        need = [(p, m) for p in part for m in models
                if (p["h"], m) not in graded and (p["h"], m) in answered]

        use_rule = cfg.get("rule_grading", True)

        def grade(job):
            p, m = job
            a = answered[(p["h"], m)]["answer"]
            rule = rule_grade(a, p["gold"], p.get("stale")) if use_rule else None
            out = {"h": p["h"], "m": m, "answer": a,
                   "f1": token_f1(p["gold"], a), "tokens": answered[(p["h"], m)]["tokens"],
                   "stale": staleness_hit(a, p.get("stale"))}
            if rule is None or audit_pick(p["h"]):
                v = judge_answer(p["question"], p["gold"], a, prov(judge_spec))
                out["correct"] = v["correct"]
                out["graded_by"] = "judge"
                if rule is not None:
                    out["rule"] = rule  # audit record: both verdicts kept
            else:
                out["correct"] = rule
                out["graded_by"] = "rule"
            return out

        _pool(cfg, grade, need, "grade", res_path, cfg.get("grade_workers"))
        graded |= {(p["h"], m) for p, m in need}


# ------------------------------------------------------------------ stage 3

def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def spearman(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    rx = _rankdata(x)
    ry = _rankdata(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def _rankdata(a):
    order = np.argsort(a, kind="stable")
    ranks = np.empty(len(a))
    ranks[order] = np.arange(len(a))
    # average ties
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    return (sums / counts)[inv]


def anova3(Y: np.ndarray) -> dict:
    """Sum-of-squares decomposition of a full 3-factor factorial, one value per cell.

    Y has shape (10, 10, 10) indexed [semantic, lexical, recency]. Returns the
    fraction of total variance attributable to each main effect and each
    two-way interaction; the three-way term is the remainder.
    """
    m = Y.mean()
    a = Y.mean(axis=(1, 2)) - m
    b = Y.mean(axis=(0, 2)) - m
    c = Y.mean(axis=(0, 1)) - m
    ab = Y.mean(axis=2) - m - a[:, None] - b[None, :]
    ac = Y.mean(axis=1) - m - a[:, None] - c[None, :]
    bc = Y.mean(axis=0) - m - b[:, None] - c[None, :]
    na, nb, nc = Y.shape
    ss = {
        "semantic": (a ** 2).sum() * nb * nc,
        "lexical": (b ** 2).sum() * na * nc,
        "recency": (c ** 2).sum() * na * nb,
        "semantic x lexical": (ab ** 2).sum() * nc,
        "semantic x recency": (ac ** 2).sum() * nb,
        "lexical x recency": (bc ** 2).sum() * na,
    }
    total = ((Y - m) ** 2).sum()
    ss["three-way"] = max(0.0, total - sum(ss.values()))
    return {k: (v / total if total > 0 else 0.0) for k, v in ss.items()}


class Grid:
    """All outcomes for one benchmark, as arrays [policy][model] -> (W, Q)."""

    def __init__(self, plan_obj: dict, answers: dict, models: list[str]):
        self.name = plan_obj["benchmark"]
        self.grid = [tuple(w) for w in plan_obj["grid"]]
        self.values = sorted({w[0] for w in self.grid})
        self.q = plan_obj["questions"]
        self.policies = plan_obj["policies"]
        self.models = models
        self.f = plan_obj["fields"]
        W, Q = len(self.grid), len(self.q)
        self.has_stale = np.array([bool(x["stale"]) for x in self.q])
        self.out = {}
        self.complete = {}
        for pol in self.policies:
            H = self.f[pol]["prompt"]
            for m in models:
                arrs = {k: np.full((W, Q), np.nan) for k in ("correct", "stale", "f1", "tokens")}
                for wi in range(W):
                    for qi in range(Q):
                        r = answers.get((H[wi][qi], m))
                        if r is not None:
                            arrs["correct"][wi, qi] = r["correct"]
                            arrs["stale"][wi, qi] = r["stale"]
                            arrs["f1"][wi, qi] = r["f1"]
                            arrs["tokens"][wi, qi] = r["tokens"]
                self.out[(pol, m)] = arrs
                self.complete[(pol, m)] = ~np.isnan(arrs["correct"]).any(axis=1)
            gr = np.array(self.f[pol]["gold_rank"], float)
            sr = np.array(self.f[pol]["stale_rank"], float)
            self.out[(pol, "retrieval")] = {
                "gold_support": (gr > 0).astype(float),
                "stale_exposure": np.where(self.has_stale[None, :], (sr > 0).astype(float), np.nan),
                "gold_rank": np.where(gr > 0, gr, np.nan),
                "ctx_tokens": np.array(self.f[pol]["ctx_chars"], float) / 4.0,
                "unique_prompt": None,
            }

    def usable(self, pol) -> np.ndarray:
        """Weightings with every question answered by every model."""
        ok = np.ones(len(self.grid), bool)
        for m in self.models:
            ok &= self.complete[(pol, m)]
        return ok

    def per_w(self, pol, metric, model=None) -> np.ndarray:
        """Mean over questions (and over models if model is None) per weighting."""
        if metric in ("gold_support", "stale_exposure", "gold_rank", "ctx_tokens"):
            return np.nanmean(self.out[(pol, "retrieval")][metric], axis=1)
        ms = [model] if model else self.models
        return np.mean([np.nanmean(self.out[(pol, m)][metric], axis=1) for m in ms], axis=0)

    def cube(self, v: np.ndarray) -> np.ndarray:
        n = len(self.values)
        return v.reshape(n, n, n)


METRICS = [("accuracy", "correct", "higher"), ("staleness", "stale", "lower"),
           ("token F1", "f1", "higher"), ("tokens per question", "tokens", "lower"),
           ("gold support", "gold_support", "higher"),
           ("stale exposure", "stale_exposure", "lower"),
           ("prompt tokens (est.)", "ctx_tokens", "lower")]


def _fmt(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def _paired(G: Grid, pol, wa, wb, metric="correct"):
    """McNemar over questions and models between two weightings."""
    b = c = 0
    for m in G.models:
        xa = G.out[(pol, m)][metric][wa]
        xb = G.out[(pol, m)][metric][wb]
        b += int(np.nansum((xa == 1) & (xb == 0)))
        c += int(np.nansum((xa == 0) & (xb == 1)))
    return b, c, mcnemar(b, c)


def analyze(cfg: dict) -> None:
    d = out_dir(cfg)
    models = cfg["answer_models"]
    answers = {}
    res_path = d / "results.jsonl"
    if res_path.exists():
        for line in res_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                answers[(r["h"], r["m"])] = r
    grids = {}
    for bench in cfg["benchmarks"]:
        grids[bench["name"]] = Grid(_load_gz(d / f"{bench['name']}_plan.json.gz"), answers, models)
    focus = cfg.get("focus_policy", "P2")
    L = []
    w = L.append
    w("# Deep sensitivity analysis of the retrieval weights\n")
    nv = len(next(iter(grids.values())).values)
    designs = cfg.get("e2e_design", ["full"])
    w(f"Full {nv} x {nv} x {nv} factorial over (semantic, lexical, recency). Retrieval is "
      f"measured at every weighting, free. Answers and grades cover the end-to-end design "
      f"{designs}. Generated by `python -m analysis.deep_sensitivity analyze`.\n")
    w(f"Answer models: {', '.join(models)}. Judge: {cfg['judge_model']}. "
      f"k = {cfg.get('retrieval_k', 25)}. Focus policy: {focus}.\n")

    # ---- 0. coverage and resolution
    w("## 0. Coverage and resolution\n")
    w("| benchmark | questions | weightings | distinct rankings | unique prompts | "
      f"weightings fully answered ({focus}) |")
    w("|---|---|---|---|---|---|")
    for n, G in grids.items():
        dist = len({direction(x) for x in G.grid})
        up = len({h for pol in G.policies for row in G.f[pol]["prompt"] for h in row})
        w(f"| {n} | {len(G.q)} | {len(G.grid)} | {dist} | {up} | "
          f"{int(G.usable(focus).sum())} / {len(G.grid)} |")
    w("")
    w("Per question, how many different contexts the weightings actually produce. "
      "A small number means the grid is far coarser in practice than it looks.\n")
    w("| benchmark | policy | median distinct contexts per question | max | "
      "questions with a single context |")
    w("|---|---|---|---|---|")
    for n, G in grids.items():
        for pol in G.policies:
            H = G.f[pol]["prompt"]
            per_q = [len({H[wi][qi] for wi in range(len(G.grid))}) for qi in range(len(G.q))]
            w(f"| {n} | {pol} | {int(np.median(per_q))} | {max(per_q)} | "
              f"{sum(1 for x in per_q if x == 1)} of {len(per_q)} |")
    w("")

    graded = list(answers.values())
    if graded:
        by_rule = sum(1 for r in graded if r.get("graded_by") == "rule")
        audits = [r for r in graded if "rule" in r]
        agree = sum(1 for r in audits if r["rule"] == r["correct"])
        w("**Grading.** "
          f"{len(graded)} graded answers: {by_rule} decided by the rule grader, "
          f"{len(graded) - by_rule} by the judge. Audit sample where both graded the same "
          f"answer: {agree} of {len(audits)} agree"
          f"{f' ({agree / len(audits) * 100:.1f}%)' if audits else ''}.\n")
        idk = sum(1 for r in graded if "know" in r["answer"].lower())
        w(f"Answers that say they don't know: {idk} of {len(graded)} "
          f"({idk / len(graded) * 100:.0f}%).\n")

    # ---- 1. scale invariance
    w("## 1. Only the ratio matters (check)\n")
    for n, G in grids.items():
        groups = defaultdict(list)
        for wi, x in enumerate(G.grid):
            groups[direction(x)].append(wi)
        bad = 0
        for pol in G.policies:
            H = G.f[pol]["prompt"]
            for idx in groups.values():
                if len(idx) > 1 and any(H[i] != H[idx[0]] for i in idx[1:]):
                    bad += 1
        w(f"- {n}: {sum(1 for g in groups.values() if len(g) > 1)} groups of equivalent "
          f"weightings; groups whose contexts disagree: {bad} "
          f"({'confirmed' if bad == 0 else 'floating-point ties differ; see note'}).")
    w("")

    for n, G in grids.items():
        ok = G.usable(focus)
        w(f"## {n}\n")
        if ok.sum() < len(G.grid):
            w(f"> Partial: {int(ok.sum())} of {len(G.grid)} weightings fully answered. "
              "End-to-end numbers below use only those; retrieval numbers use all.\n")

        # ---- 2. range and published position
        w(f"### {n} 2. How much the weights can move each outcome ({focus})\n")
        w("| outcome | best | worst | range | published 0.6/0.3/0.1 | published percentile |")
        w("|---|---|---|---|---|---|")
        pub = G.grid.index(PUBLISHED) if PUBLISHED in G.grid else None
        for label, key, better in METRICS:
            v = G.per_w(focus, key)
            mask = ok if key in ("correct", "stale", "f1", "tokens") else np.ones_like(ok)
            vv = v[mask]
            if vv.size == 0 or np.all(np.isnan(vv)):
                continue
            best = np.nanmax(vv) if better == "higher" else np.nanmin(vv)
            worst = np.nanmin(vv) if better == "higher" else np.nanmax(vv)
            pv = v[pub] if pub is not None else float("nan")
            if pub is None or math.isnan(pv):
                pct_s = "n/a"
            else:
                pct_s = f"{float(np.mean(vv <= pv) if better == 'higher' else np.mean(vv >= pv)) * 100:.0f}"
            w(f"| {label} | {_fmt(best)} | {_fmt(worst)} | {_fmt(abs(best - worst))} | "
              f"{_fmt(pv)} | {pct_s} |")
        w("")

        # ---- 2b. one weight at a time
        gidx = {tuple(round(x, 4) for x in g): i for i, g in enumerate(G.grid)}
        w(f"### {n} 2b. One weight at a time: every value, the other two held at 0.6 / 0.3 / 0.1\n")
        w("The literal version of 'try all ten values of each weight'. p compares each row "
          "with the published setting on the same questions (paired McNemar, both models).\n")
        for ax, sname in enumerate(SIGNALS):
            w(f"**{sname}**\n")
            w("| value | weighting | accuracy | p acc | staleness | p stale | gold support | "
              "stale exposure | prompt tokens |")
            w("|---|---|---|---|---|---|---|---|---|")
            for v_ in G.values:
                ww = list(PUBLISHED)
                ww[ax] = v_
                wi = gidx.get(tuple(round(x, 4) for x in ww))
                if wi is None:
                    continue
                e2e = ok[wi]
                acc_s = _fmt(G.per_w(focus, "correct")[wi]) if e2e else "pending"
                st_s = _fmt(G.per_w(focus, "stale")[wi]) if e2e else "pending"
                pa = ps = ""
                if e2e and pub is not None and ok[pub] and wi != pub:
                    pa = f"{_paired(G, focus, wi, pub)[2]:.3f}"
                    ps = f"{_paired(G, focus, wi, pub, 'stale')[2]:.3f}"
                tag = " (published)" if wi == pub else ""
                w(f"| {v_:.1f} | {ww[0]:.1f}/{ww[1]:.1f}/{ww[2]:.1f}{tag} | {acc_s} | {pa} | {st_s} | "
                  f"{ps} | {_fmt(G.per_w(focus, 'gold_support')[wi])} | "
                  f"{_fmt(G.per_w(focus, 'stale_exposure')[wi])} | "
                  f"{G.per_w(focus, 'ctx_tokens')[wi]:.0f} |")
            w("")

        # ---- 3. main effects
        fvals = factorial_values(cfg.get("e2e_design", ["full"]))
        if ok.all():
            fvals = G.values
        sub = None
        if fvals:
            sub_idx = [gidx.get((a_, b_, c_)) for a_ in fvals for b_ in fvals for c_ in fvals]
            if all(i is not None and ok[i] for i in sub_idx):
                sub = (fvals, np.array(sub_idx))

        def cube_for(key):
            """Full cube for retrieval metrics; complete sub-factorial for answers."""
            v = G.per_w(focus, key)
            if key in ("gold_support", "stale_exposure", "gold_rank", "ctx_tokens"):
                return G.values, G.cube(v)
            if sub is None:
                return None, None
            k_ = len(sub[0])
            return sub[0], v[sub[1]].reshape(k_, k_, k_)

        w(f"### {n} 3. Main effects: average outcome at each value of one weight\n")
        w("Each cell averages every weighting in the factorial that shares that value of "
          "the named weight, so it includes every combination of the other two. Retrieval "
          f"rows use all {len(G.grid)} weightings; answer rows use the complete factorial "
          f"{'over ' + ', '.join(f'{x:.1f}' for x in sub[0]) if sub else 'once it is run'}.\n")
        for label, key, better in METRICS[:2] + METRICS[4:6]:
            vals_, C = cube_for(key)
            if C is None:
                continue
            w(f"**{label}**\n")
            w("| weight value | " + " | ".join(f"{x:.1f}" for x in vals_) + " | range |")
            w("|---|" + "---|" * (len(vals_) + 1))
            for ax, s in enumerate(SIGNALS):
                me = np.nanmean(C, axis=tuple(i for i in range(3) if i != ax))
                w(f"| {s} | " + " | ".join(_fmt(x) for x in me) + f" | {_fmt(np.nanmax(me) - np.nanmin(me))} |")
            w("")

        # ---- 4. ANOVA
        w(f"### {n} 4. Which weight drives which outcome (variance decomposition)\n")
        w("Share of the variation across the factorial explained by each weight on "
          "its own and by each pair together. Large main effects mean one weight "
          "matters by itself; large interactions mean the weights only matter in "
          "combination (as ratios).\n")
        w("| outcome | " + " | ".join(["semantic", "lexical", "recency", "sem x lex",
                                        "sem x rec", "lex x rec", "three-way"]) + " |")
        w("|---|" + "---|" * 7)
        for label, key, _ in METRICS:
            if key in ("f1", "tokens"):
                v = G.per_w(focus, key)
                vals_, C = (None, None) if sub is None else (
                    sub[0], v[sub[1]].reshape(len(sub[0]), len(sub[0]), len(sub[0])))
            else:
                vals_, C = cube_for(key)
            if C is None:
                continue
            C = np.nan_to_num(C, nan=np.nanmean(C))
            fr = anova3(C)
            w(f"| {label} | " + " | ".join(f"{fr[k] * 100:.0f}%" for k in fr) + " |")
        w("")

        # ---- 5. share view
        w(f"### {n} 5. The same data in share terms\n")
        w("Because only ratios matter, the natural coordinates are each weight's share of "
          "the total. Mean outcome by recency share (rows) is the single most informative "
          "cut if recency turns out to dominate.\n")
        shares = np.array([[x / sum(g) for x in g] for g in G.grid])
        bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.85]
        for si, s in enumerate(SIGNALS):
            w(f"**by {s} share**\n")
            w("| share bin | weightings | " + " | ".join(m[0] for m in METRICS[:2] + METRICS[4:6]) + " |")
            w("|---|---|" + "---|" * 4)
            for lo, hi in zip(bins[:-1], bins[1:]):
                sel = (shares[:, si] >= lo) & (shares[:, si] < hi)
                if not sel.any():
                    continue
                cells = []
                for _, key, _ in METRICS[:2] + METRICS[4:6]:
                    v = G.per_w(focus, key)
                    m_ = sel & ok if key in ("correct", "stale") else sel
                    cells.append(_fmt(np.nanmean(v[m_])) if m_.any() else "n/a")
                w(f"| {lo:.2f} to {hi:.2f} | {int(sel.sum())} | " + " | ".join(cells) + " |")
            w("")

        # ---- 5b. hypothesis at the retrieval level, every weighting
        others = [p_ for p_ in G.policies if p_ != focus]
        if others:
            base = others[0]
            w(f"### {n} 5b. Does {focus} keep outdated facts out of the prompt better than {base}, "
              f"at every weighting? (retrieval, all {len(G.grid)})\n")
            w(f"| measure | mean {focus} minus {base} | range | {focus} better / tie / worse |")
            w("|---|---|---|---|")
            for lab, key, better in (("stale exposure", "stale_exposure", "lower"),
                                     ("gold support", "gold_support", "higher"),
                                     ("prompt tokens (est.)", "ctx_tokens", "lower")):
                dv = G.per_w(focus, key) - G.per_w(base, key)
                fav = (dv < -1e-12) if better == "lower" else (dv > 1e-12)
                tie = np.abs(dv) <= 1e-12
                w(f"| {lab} | {np.nanmean(dv):+.3f} | {np.nanmin(dv):+.3f} to {np.nanmax(dv):+.3f} | "
                  f"{int(fav.sum())} / {int(tie.sum())} / {int((~fav & ~tie).sum())} |")
            w("")

        if ok.sum() < 2:
            continue
        acc = G.per_w(focus, "correct")
        idx_ok = np.where(ok)[0]

        # ---- 6. plateau
        best_i = idx_ok[np.nanargmax(acc[ok])]
        within = []
        for wi in idx_ok:
            b, c, p = _paired(G, focus, wi, best_i)
            if p > 0.05:
                within.append(wi)
        w(f"### {n} 6. The plateau: how many weightings are statistically tied with the best\n")
        w(f"- Best accuracy: {_fmt(acc[best_i])} at {G.grid[best_i]}.")
        w(f"- Weightings not significantly worse than the best (paired McNemar, p > 0.05): "
          f"**{len(within)} of {int(ok.sum())}** ({len(within) / ok.sum() * 100:.0f}%).")
        if pub is not None and ok[pub]:
            b, c, p = _paired(G, focus, pub, best_i)
            w(f"- Published 0.6/0.3/0.1 against the best: {b} better, {c} worse, p = {p:.3f} "
              f"-> {'inside' if p > 0.05 else 'outside'} the plateau.")
        sig_worse = [wi for wi in idx_ok if wi not in within]
        if sig_worse:
            sw = shares[sig_worse]
            w(f"- The {len(sig_worse)} significantly worse weightings have mean shares "
              f"semantic {sw[:, 0].mean():.2f}, lexical {sw[:, 1].mean():.2f}, "
              f"recency {sw[:, 2].mean():.2f} (the plateau: "
              f"{shares[within][:, 0].mean():.2f} / {shares[within][:, 1].mean():.2f} / "
              f"{shares[within][:, 2].mean():.2f}).")
        w("- With this many comparisons some 'best' is guaranteed by noise alone; see "
          "section 7 for how much.\n")

        # ---- 7. winner's curse / split-half
        rng = np.random.default_rng(0)
        Q = len(G.q)
        gains, opt = [], []
        M = np.stack([G.out[(focus, m)]["correct"] for m in G.models])  # (models, W, Q)
        for _ in range(200):
            perm = rng.permutation(Q)
            A, B = perm[: Q // 2], perm[Q // 2:]
            accA = np.nanmean(M[:, :, A], axis=(0, 2))
            accB = np.nanmean(M[:, :, B], axis=(0, 2))
            accA[~ok] = -1
            wa = int(np.argmax(accA))
            opt.append(accA[wa] - accB[wa])
            if pub is not None:
                gains.append(accB[wa] - accB[pub])
        w(f"### {n} 7. Winner's curse: does 'the best weighting' survive new questions?\n")
        w("Pick the best weighting on a random half of the questions, then score it on the "
          "other half. Repeated 200 times.\n")
        w(f"- Average optimism (score on the half it was picked on minus score on the "
          f"unseen half): **{np.mean(opt):+.3f}**.")
        if gains:
            g = np.array(gains)
            w(f"- Picked weighting against published, on the unseen half: mean "
              f"{g.mean():+.3f}; it beat published in {np.mean(g > 0) * 100:.0f}% of splits, "
              f"tied in {np.mean(g == 0) * 100:.0f}%, lost in {np.mean(g < 0) * 100:.0f}%.")
        w("")

        # ---- 8. models
        if len(G.models) > 1:
            w(f"### {n} 8. Do the two answer models agree on which weightings are good?\n")
            for m1, m2 in combinations(G.models, 2):
                a1 = G.per_w(focus, "correct", m1)[ok]
                a2 = G.per_w(focus, "correct", m2)[ok]
                w(f"- Spearman rank correlation across weightings, {m1} vs {m2}: "
                  f"**{spearman(a1, a2):.2f}**; mean accuracy {a1.mean():.3f} vs {a2.mean():.3f}.")
            w("")

        # ---- 9. mediation
        w(f"### {n} 9. Does the free retrieval measurement predict the paid result?\n")
        gs = G.per_w(focus, "gold_support")[ok]
        se = G.per_w(focus, "stale_exposure")[ok]
        st = G.per_w(focus, "stale")[ok]
        a = acc[ok]
        r1 = np.corrcoef(gs, a)[0, 1] if gs.std() > 0 and a.std() > 0 else float("nan")
        r2 = np.corrcoef(se, st)[0, 1] if se.std() > 0 and st.std() > 0 else float("nan")
        w(f"- Across weightings, correlation of gold support with accuracy: r = {_fmt(r1, 2)} "
          f"(R^2 = {_fmt(r1 ** 2 if not math.isnan(r1) else r1, 2)}).")
        w(f"- Correlation of stale exposure with staleness: r = {_fmt(r2, 2)}.")
        low = gs < np.nanmax(gs) - 1e-9
        if low.any():
            w(f"- Weightings below the gold-support ceiling: {int(low.sum())}; their mean "
              f"accuracy {a[low].mean():.3f} against {a[~low].mean():.3f} at the ceiling.")
        w("")

        # ---- 10. hypothesis stability
        other = [p for p in G.policies if p != focus]
        if other and G.usable(other[0]).any():
            base = other[0]
            both = ok & G.usable(base)
            w(f"### {n} 10. Does {focus} beat {base} at every weighting?\n")
            rows = []
            for key, lab, better in (("stale", "staleness", "lower"), ("correct", "accuracy", "higher")):
                dv = (G.per_w(focus, key) - G.per_w(base, key))[both]
                sig_good = sig_bad = 0
                for wi in np.where(both)[0]:
                    b = c = 0
                    for m in G.models:
                        x = G.out[(focus, m)][key][wi]
                        y = G.out[(base, m)][key][wi]
                        b += int(np.nansum((x == 1) & (y == 0)))
                        c += int(np.nansum((x == 0) & (y == 1)))
                    p = mcnemar(b, c)
                    good = (b < c) if better == "lower" else (b > c)
                    if p <= 0.05:
                        sig_good += good
                        sig_bad += not good
                fav = (dv < 0) if better == "lower" else (dv > 0)
                tie = dv == 0
                rows.append(f"| {lab} | {dv.mean():+.3f} | {dv.min():+.3f} to {dv.max():+.3f} | "
                            f"{int(fav.sum())} / {int(tie.sum())} / {int((~fav & ~tie).sum())} | "
                            f"{sig_good} | {sig_bad} |")
            w(f"| outcome | mean {focus} minus {base} | range | weightings {focus} better / tie / worse "
              f"| significantly better | significantly worse |")
            w("|---|---|---|---|---|---|")
            L.extend(rows)
            w("")

        # ---- 11. pareto
        stale_v = G.per_w(focus, "stale")
        tok_v = G.per_w(focus, "ctx_tokens")
        pts = [(wi, acc[wi], stale_v[wi], tok_v[wi]) for wi in idx_ok]
        front = [p for p in pts if not any(
            (q[1] >= p[1] and q[2] <= p[2] and q[3] <= p[3]) and
            (q[1] > p[1] or q[2] < p[2] or q[3] < p[3]) for q in pts)]
        w(f"### {n} 11. Trade-offs: the Pareto front (accuracy up, staleness down, prompt tokens down)\n")
        w(f"{len(front)} of {len(pts)} weightings are not beaten on all three at once.\n")
        w("| semantic | lexical | recency | accuracy | staleness | prompt tokens |")
        w("|---|---|---|---|---|---|")
        for wi, a_, s_, t_ in sorted(front, key=lambda p: -p[1])[:15]:
            g = G.grid[wi]
            w(f"| {g[0]:.1f} | {g[1]:.1f} | {g[2]:.1f} | {a_:.3f} | {s_:.3f} | {t_:.0f} |")
        w("")

    # ---- 12. cross-benchmark
    names = list(grids)
    if len(names) > 1:
        w("## Cross-benchmark: do the same weightings win everywhere?\n")
        w("| pair | Spearman of weighting accuracy | best on first, rank on second | "
          "published rank on each |")
        w("|---|---|---|---|")
        for a_, b_ in combinations(names, 2):
            GA, GB = grids[a_], grids[b_]
            both = GA.usable(focus) & GB.usable(focus)
            if both.sum() < 3:
                continue
            xa, xb = GA.per_w(focus, "correct")[both], GB.per_w(focus, "correct")[both]
            idx = np.where(both)[0]
            ba = idx[np.argmax(xa)]
            rank_b = int((xb > GB.per_w(focus, "correct")[ba]).sum()) + 1
            pub = GA.grid.index(PUBLISHED) if PUBLISHED in GA.grid else None
            pr = ""
            if pub is not None and both[pub]:
                pr = (f"{int((xa > GA.per_w(focus, 'correct')[pub]).sum()) + 1} / "
                      f"{int((xb > GB.per_w(focus, 'correct')[pub]).sum()) + 1} of {len(idx)}")
            w(f"| {a_} vs {b_} | {spearman(xa, xb):.2f} | {rank_b} of {len(idx)} | {pr} |")
        w("")

    if len(names) > 1:
        w("## Cross-benchmark, retrieval: do the same weightings retrieve well everywhere?\n")
        w("Spearman rank correlation across all weightings of the free retrieval measures.\n")
        w("| pair | gold support | stale exposure |")
        w("|---|---|---|")
        for a_, b_ in combinations(names, 2):
            GA, GB = grids[a_], grids[b_]
            w(f"| {a_} vs {b_} | {spearman(GA.per_w(focus, 'gold_support'), GB.per_w(focus, 'gold_support')):.2f} | "
              f"{spearman(GA.per_w(focus, 'stale_exposure'), GB.per_w(focus, 'stale_exposure')):.2f} |")
        w("")

    report = "\n".join(L) + "\n"
    rp = Path(cfg.get("report", "paper/DEEP_SENSITIVITY.md"))
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(report)
    print(report)
    print(f"wrote {rp}")
    if cfg.get("figures", True):
        figures(grids, focus, d / "figures")


def figures(grids: dict, focus: str, fdir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping figures")
        return
    fdir.mkdir(parents=True, exist_ok=True)
    teal, grey, rust = "#0F766E", "#9AA5B1", "#B5523B"
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    cols = {"semantic": teal, "lexical": grey, "recency": rust}
    for n, G in grids.items():
        ok = G.usable(focus)
        full = ok.all()
        keys = [("accuracy", "correct"), ("staleness", "stale"),
                ("gold support", "gold_support"), ("stale exposure", "stale_exposure")]
        keys = [k for k in keys if full or k[1] not in ("correct", "stale")]
        # main effects
        fig, axes = plt.subplots(1, len(keys), figsize=(3.6 * len(keys), 3.2))
        axes = np.atleast_1d(axes)
        for ax, (lab, key) in zip(axes, keys):
            C = G.cube(G.per_w(focus, key))
            for i, s in enumerate(SIGNALS):
                me = np.nanmean(C, axis=tuple(j for j in range(3) if j != i))
                ax.plot(G.values, me, "o-", color=cols[s], label=s, ms=4)
            ax.set_title(lab, loc="left")
            ax.set_xlabel("weight value")
        axes[0].legend(frameon=False, fontsize=8)
        fig.suptitle(f"{n}: main effect of each weight ({focus})", x=0.01, ha="left")
        fig.tight_layout()
        fig.savefig(fdir / f"{n}_main_effects.png", dpi=180)
        plt.close(fig)
        # pairwise heatmaps
        for lab, key in keys:
            C = G.cube(G.per_w(focus, key))
            fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
            for ax, (i, j) in zip(axes, [(0, 1), (0, 2), (1, 2)]):
                other = 3 - i - j
                Mx = np.nanmean(C, axis=other)
                im = ax.imshow(Mx.T, origin="lower", cmap="viridis",
                               extent=[0.05, 1.05, 0.05, 1.05], aspect="auto")
                ax.set_xlabel(SIGNALS[i]); ax.set_ylabel(SIGNALS[j])
                fig.colorbar(im, ax=ax, fraction=0.046)
            fig.suptitle(f"{n}: {lab} by pairs of weights, third averaged out ({focus})",
                         x=0.01, ha="left")
            fig.tight_layout()
            fig.savefig(fdir / f"{n}_heatmap_{key}.png", dpi=180)
            plt.close(fig)
        # share scatter
        sh = np.array([[x / sum(g) for x in g] for g in G.grid])
        for lab, key in keys:
            v = G.per_w(focus, key)
            fig, ax = plt.subplots(figsize=(5, 4))
            sc = ax.scatter(sh[:, 2], sh[:, 0] / (sh[:, 0] + sh[:, 1]), c=v, cmap="viridis", s=14)
            ax.set_xlabel("recency share of total weight")
            ax.set_ylabel("semantic / (semantic + lexical)")
            fig.colorbar(sc, ax=ax, label=lab)
            ax.set_title(f"{n}: {lab} in ratio space", loc="left")
            fig.tight_layout()
            fig.savefig(fdir / f"{n}_ratio_{key}.png", dpi=180)
            plt.close(fig)
        # anova bars
        fig, ax = plt.subplots(figsize=(8, 3.4))
        labels = None
        width = 0.8 / len(keys)
        for kk, (lab, key) in enumerate(keys):
            v = G.per_w(focus, key)
            fr = anova3(G.cube(np.nan_to_num(v, nan=np.nanmean(v))))
            labels = list(fr)
            ax.bar(np.arange(len(fr)) + kk * width, [x * 100 for x in fr.values()], width, label=lab)
        ax.set_xticks(np.arange(len(labels)) + 0.4 - width / 2)
        ax.set_xticklabels(labels, rotation=20, fontsize=8)
        ax.set_ylabel("% of variance")
        ax.legend(frameon=False, fontsize=8)
        ax.set_title(f"{n}: what drives each outcome ({focus})", loc="left")
        fig.tight_layout()
        fig.savefig(fdir / f"{n}_variance.png", dpi=180)
        plt.close(fig)
    print(f"figures -> {fdir}")


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser(description="Deep 10x10x10 retrieval weight sensitivity")
    ap.add_argument("stage", choices=["plan", "run", "analyze"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--limit", type=int, help="run: stop after this many answers")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if args.stage == "plan":
        plan(cfg)
    elif args.stage == "run":
        run(cfg, args.limit)
    else:
        analyze(cfg)


if __name__ == "__main__":
    main()
