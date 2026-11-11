"""Compact every v3 result cell into a small file the analysis can load quickly.

For each cell under artifacts/results/v3 this keeps the summary, every
per-question record (re-graded and enriched with exactly the rules of
analysis.final_report: refusal = incorrect, plain gold = correct, staleness =
old value asserted without the current one, exposure = old value in a retrieved
fact's text), and the saved graphs without embeddings. Nothing calls a model.

Output mirrors the input tree under artifacts/v3_compact/.

Usage:
    python -m analysis.v3_compact
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from analysis.final_report import enrich, load_questions

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "artifacts/results/v3"
DST = ROOT / "artifacts/v3_compact"
DATA = {"mquake_t": "data/mquake_t_sh.json", "factconsolidation": "data/factconsolidation_sh_6k.json",
        "convomem": "data/convomem_changing.json", "mquake_t_mh": "data/mquake_t_mh.json",
        "factconsolidation_mh": "data/factconsolidation_mh_6k.json",
        **{f"mquake_cf_mh_s{k}": f"data/mquake_cf_mh_s{k}.json" for k in range(1, 5)}}
KEEP_REC = ["conversation", "category", "question", "answer", "gold", "correct", "judge_correct", "f1",
            "stale", "mentions_old", "tokens", "prompt_tokens", "completion_tokens", "retrieved_invalidated",
            "stale_in_ctx", "gold_in_ctx", "_ctx_known", "_stale_answer", "_category", "answer_model",
            "agent", "worker", "judged_by", "stale_answer", "current_answer", "hops", "edit_position",
            "n_edits", "case_id", "answer_alias", "stale_alias", "answer_seconds", "answer_cached"]
KEEP_FACT = ["id", "subject", "predicate", "object", "text", "t_valid_start", "t_ingested", "t_invalid_at",
             "t_pruned", "active", "provenance"]


def bench_of(path: Path) -> str:
    for b in DATA:
        if path.parent.name.endswith(b):
            return b
    raise ValueError(path)


def compact(path: Path, qcache: dict) -> None:
    out = DST / path.relative_to(SRC)
    if out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
        return
    c = json.loads(path.read_text())
    if not (isinstance(c, dict) and "records" in c and "summary" in c):
        return
    b = bench_of(path)
    if b not in qcache:
        qcache[b] = load_questions(str(ROOT / DATA[b]))
    enrich(c, qcache[b])
    res = {"summary": c["summary"], "benchmark": b,
           "records": [{k: r.get(k) for k in KEEP_REC if k in r} for r in c["records"]]}
    if c.get("per_agent"):
        res["per_agent"] = c["per_agent"]
    snaps = c.get("graph_snapshots")
    if not snaps and c.get("graph_snapshot"):
        snaps = {"_all": c["graph_snapshot"]}
    if snaps:
        res["graphs"] = {k: [{f: x.get(f) for f in KEEP_FACT} for x in v] for k, v in snaps.items()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))


def main() -> None:
    files = sorted(p for p in SRC.rglob("*.json")
                   if p.name not in ("summary_table.json", "run_record.json") and "grace_history" not in str(p))
    qcache: dict = {}
    for i, p in enumerate(files, 1):
        compact(p, qcache)
        print(f"\r{i}/{len(files)} {p.relative_to(SRC)}" + " " * 20, end="", file=sys.stderr)
    print(file=sys.stderr)


if __name__ == "__main__":
    main()
