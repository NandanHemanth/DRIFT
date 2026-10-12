"""Offline preflight for the final campaign: is every extraction already cached?

The final matrix reuses the extraction calls from the published runs, so that
every policy and every answer model starts from the same facts and the run pays
nothing for extraction. This script checks that promise without touching the
network: it blocks all HTTP, rebuilds each benchmark's memory from the cache
alone, and reports

  * how many sessions would need a new (paid, and possibly different) extraction,
  * how many facts the substrate holds and how many contradictions it closes,
    under exact and normalised relation matching,
  * how many closed facts are reversed-direction pairs that neither mode catches.

It uses the offline hashing embedder, because extraction and contradiction
detection do not depend on embeddings.

Usage:
    python scripts/preflight_final.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _blocked(*_a, **_k):
    raise OSError("network blocked by preflight")


urllib.request.urlopen = _blocked          # nothing below may reach the network
time.sleep = lambda *_: None                # retries back off instantly

from drift.embeddings import HashingEmbedder  # noqa: E402
from drift.memory.extraction import extract_facts  # noqa: E402
from drift.memory.graph import BitemporalGraph  # noqa: E402
from drift.runner import _build_providers, _functional_predicates, _rotated_fallback  # noqa: E402

CONFIGS = ["configs/final_mquake_t.json", "configs/final_factconsolidation.json",
           "configs/final_convomem.json"]


def build(dataset: dict, specs: list[str], cfg: dict, mode: str):
    emb = HashingEmbedder()
    providers = _build_providers(specs, str(ROOT / cfg.get("cache_dir", ".drift_cache")))
    for p in providers:
        if hasattr(p, "max_retries"):
            p.max_retries = 1
    misses = sessions = facts = closed = 0
    graphs = []
    for i, convo in enumerate(dataset["conversations"]):
        ext = _rotated_fallback(providers, i)
        g = BitemporalGraph(emb, functional_predicates=_functional_predicates(cfg),
                            relation_matching=mode)
        for s in convo["sessions"]:
            sessions += 1
            try:
                fs = extract_facts(ext, s["lines"])
            except Exception:  # noqa: BLE001 - a miss: every provider in the chain missed
                misses += 1
                continue
            for f in fs:
                g.add_fact(f["subject"], f["predicate"], f["object"], f["text"], t_event=s["time"])
        facts += len(g.facts)
        closed += sum(1 for f in g.facts.values() if f.invalidated)
        graphs.append(g)
    return {"sessions": sessions, "misses": misses, "facts": facts, "closed": closed}, graphs


def reversed_pairs(graphs) -> int:
    """Pairs that look like one role changing hands but were stored the other way
    round: same relation, same object, different subject, where the relation names
    a single-holder role (head of government or state, chief executive, director,
    head coach). Neither exact nor normalised matching can close these."""
    roles = ("head_of_government", "head_of_state", "chief_executive", "director", "head_coach")
    n = 0
    for g in graphs:
        seen: dict[tuple, set] = {}
        for f in g.facts.values():
            p = f.predicate.lower()
            if any(r in p for r in roles) and p.endswith("_of"):
                seen.setdefault((p, f.object.lower()), set()).add(f.subject.lower())
        n += sum(len(v) - 1 for v in seen.values() if len(v) > 1)
    return n


def coverage(dataset: dict, graphs) -> dict:
    """Question-level check of contradiction detection.

    detected      the superseded value sits in a closed fact (P2 can hide it)
    missed        the superseded value is stored but never closed
    gold_closed   the current answer itself sits only in closed facts, so P2
                  would hide the right answer (a false closure that costs accuracy)
    """
    det = miss = gold_closed = n = 0
    for convo, g in zip(dataset["conversations"], graphs):
        fs = list(g.facts.values())
        for q in convo["questions"]:
            st, gold = q.get("stale_answer"), q.get("answer", "")
            if not st:
                continue
            n += 1
            holders = [f for f in fs if st.lower() in f.text.lower()]
            if holders and any(f.invalidated for f in holders):
                det += 1
            elif holders:
                miss += 1
            gh = [f for f in fs if gold and gold.lower() in f.text.lower()]
            if gh and all(f.invalidated for f in gh):
                gold_closed += 1
    return {"questions": n, "detected": det, "missed": miss, "gold_closed": gold_closed}


def main() -> None:
    out = []
    for path in CONFIGS:
        cfg = json.loads((ROOT / path).read_text())
        dataset = json.loads((ROOT / cfg["dataset"]).read_text())
        specs = cfg["extract_model"] if isinstance(cfg["extract_model"], list) else [cfg["extract_model"]]
        row = {"benchmark": Path(cfg["dataset"]).stem}
        for mode in ("exact", "normalized"):
            stats, graphs = build(dataset, specs, cfg, mode)
            row.update({"sessions": stats["sessions"], "extraction_misses": stats["misses"],
                        "facts": stats["facts"], f"closed_{mode}": stats["closed"]})
            for k, v in coverage(dataset, graphs).items():
                row[f"{k}_{mode}" if k != "questions" else k] = v
        row["reversed_role_pairs"] = reversed_pairs(graphs)
        out.append(row)
        print(json.dumps(row))
    (ROOT / "artifacts/preflight_final.json").write_text(json.dumps(out, indent=1))
    bad = [r for r in out if r["extraction_misses"]]
    print("\nOK: every extraction is cached" if not bad else
          f"\nWARNING: {sum(r['extraction_misses'] for r in bad)} sessions would be re-extracted")


if __name__ == "__main__":
    main()
