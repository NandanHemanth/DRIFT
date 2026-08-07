"""Turn results JSONs into the markdown tables used by THESIS_REPORT.md.

Usage:
    python analysis/report_tables.py results/smoke
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(results_dir: str) -> None:
    table_path = Path(results_dir) / "summary_table.json"
    summaries = json.loads(table_path.read_text())
    summaries.sort(key=lambda s: s["policy"])

    print("| Policy | Model | Accuracy | Mean F1 | Staleness | Tokens/Q | Active facts | Pruned | Write rejections |")
    print("|---|---|---|---|---|---|---|---|---|")
    for s in summaries:
        mem = s.get("final_memory", {})
        print(
            f"| {s['policy']} | {s['model']} | {s['accuracy']:.3f} | {s['mean_f1']:.3f} "
            f"| {s['staleness_rate']:.3f} | {s['mean_tokens_per_q']:.0f} "
            f"| {mem.get('active_facts', '-')} | {mem.get('pruned', '-')} | {mem.get('write_rejections', '-')} |"
        )

    print("\nPer-category accuracy:")
    cats: dict[str, dict[str, list[bool]]] = {}
    for f in sorted(Path(results_dir).glob("*.json")):
        if f.name == "summary_table.json":
            continue
        data = json.loads(f.read_text())
        policy = data["summary"]["policy"]
        for r in data["records"]:
            cats.setdefault(r["category"], {}).setdefault(policy, []).append(r["correct"])

    policies = sorted({p for by_p in cats.values() for p in by_p})
    print("| Category | " + " | ".join(policies) + " |")
    print("|---" * (len(policies) + 1) + "|")
    for cat in sorted(cats):
        row = [f"{sum(v)/len(v):.2f}" if (v := cats[cat].get(p)) else "-" for p in policies]
        print(f"| {cat} | " + " | ".join(row) + " |")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/smoke")
