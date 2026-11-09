"""Dry run for the v3 campaign: exact call counts, estimated cost and time.

No model is called. Counts come from the configs and the datasets; cost per
answer per model comes from the October final run (list prices, measured token
use: artifacts/cost_per_answer_oct.json). Throughput (answers per minute per
process) is the rate the October main matrix achieved.

Usage:
    python scripts/estimate_v3.py                 # all v3 configs
    python scripts/estimate_v3.py --only run1     # one folder
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COST = json.loads((ROOT / "artifacts/cost_per_answer_oct.json").read_text())
JUDGE_PER_ANSWER = 0.000018      # DeepSeek V4.1 Flash, October measurement
ROUTER_PER_CALL = 0.0002          # Gemini 3.8 Flash, 8-token reply
EXTRACT_PER_SESSION = {           # rough list-price cost of one extraction call
    "deepseek": 0.0003, "gpt-6.1-sol": 0.003, "claude-sonnet-5.5": 0.006,
    "gemini-3.8-flash": 0.002, "qwen3-14b": 0.0005, "llama-3.1-8b-instruct": 0.00002}
ANSWERS_PER_MINUTE = 40           # October main matrix, one process


def bench_of(path: str) -> str:
    for b in ("mquake_t", "factconsolidation", "convomem"):
        if b in path:
            return b
    return "mquake_t"


def short(m: str) -> str:
    return m.split("/")[-1]


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    rows, total_cost, total_answers = [], 0.0, 0
    by_group = defaultdict(lambda: [0, 0.0])
    for path in sorted((ROOT / "configs/v3").rglob("*.json")):
        rel = str(path.relative_to(ROOT / "configs/v3"))
        if only and not rel.startswith(only):
            continue
        cfg = json.loads(path.read_text())
        answers, cost, sessions_extract = 0, 0.0, 0.0
        if "benchmarks" in cfg:                                   # grace study
            for b in cfg["benchmarks"]:
                data = json.loads((ROOT / b["dataset"]).read_text())
                probes = sum(1 for c in data["conversations"] for q in c["questions"] if q.get("stale_answer"))
                n = 2 * probes * len(cfg["grace_grid"])
                for m in cfg["answer_models"]:
                    answers += n
                    cost += n * (COST["openrouter:" + m.split(":", 1)[1]][b["name"]])
                sessions_extract += sum(len(c["sessions"]) for c in data["conversations"]) * 0.0003
        else:
            data = json.loads((ROOT / cfg["dataset"]).read_text())
            b = bench_of(cfg["dataset"])
            q = sum(len(c["questions"]) for c in data["conversations"])
            s = sum(len(c["sessions"]) for c in data["conversations"])
            models = cfg.get("models") or cfg.get("answer_models")
            if "topologies" in cfg:                               # RQ4
                for topo in cfg["topologies"]:
                    agents = cfg.get("independent_agents", 3) if topo == "independent" else 1
                    for _p in cfg["policies"]:
                        for m in models:
                            n = q * agents
                            answers += n
                            cost += n * COST["openrouter:" + m.split(":", 1)[1]][b]
                    if topo == "orchestrator":
                        cost += len(cfg["policies"]) * q * ROUTER_PER_CALL
                    if topo == "shared":
                        cost += sum(EXTRACT_PER_SESSION[short(w)] for w in cfg["extract_models"]) / len(
                            cfg["extract_models"]) * s
                    else:
                        sessions_extract += s * 0.0003
            else:
                for p in cfg["policies"]:
                    for m in models:
                        answers += q
                        cost += q * COST["openrouter:" + m.split(":", 1)[1]][b]
                sessions_extract += s * 0.0003
        cost += answers * JUDGE_PER_ANSWER + sessions_extract
        group = rel.split("/")[0] + ("/rq4" if "rq4_" in rel else "/main" if "main_" in rel else "")
        by_group[group][0] += answers
        by_group[group][1] += cost
        total_cost += cost
        total_answers += answers
        rows.append((rel, answers, cost))
    print(f"{'config':45s} {'answers':>9s} {'USD':>8s}")
    for rel, a, c in rows:
        print(f"{rel:45s} {a:9d} {c:8.2f}")
    print("\nby study")
    for g, (a, c) in sorted(by_group.items()):
        print(f"  {g:20s} {a:9d} answers  ${c:7.2f}  ~{a / ANSWERS_PER_MINUTE / 60:5.1f} h in one process")
    print(f"\nTOTAL {total_answers} answers, about ${total_cost:.2f} at list price "
          f"(October billed about 17% below list), ~{total_answers / ANSWERS_PER_MINUTE / 60:.0f} h of "
          f"calls if run one process at a time")


if __name__ == "__main__":
    main()
