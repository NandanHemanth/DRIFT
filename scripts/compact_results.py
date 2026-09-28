"""Strip embedding vectors out of saved result cells.

Why this exists
---------------
`"save_graph": true` writes the full memory snapshot into each result cell so
that pruned and superseded fact text can be recovered after the fact. Each Fact
carries its embedding, and at 768 dimensions those vectors are 97% of the file:
the two real campaigns weigh 230 MB, of which 6.6 MB is the part any analysis
tool reads.

Nothing downstream uses the stored vectors. `analysis/graphify_export.py`,
`analysis/timeline.py`, `analysis/record.py` and `analysis/report_tables.py`
read only subject, predicate, object, text, the three timestamps and `active`.
Embeddings are recomputed from `embedder` on every run, so dropping them from
the archive loses nothing that can not be regenerated.

This is a post-processing step rather than a change to the runner: the runner's
output format stays exactly as it was, and compaction is an explicit, reversible
decision about what to keep in version control.

Usage:
    python scripts/compact_results.py artifacts/results          # all cells
    python scripts/compact_results.py artifacts/results --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SKIP = {"summary_table.json", "live.json", "search_summary.json"}


def compact_file(path: Path, dry_run: bool = False) -> tuple[int, int]:
    """-> (bytes before, bytes after). Returns (0, 0) if there is nothing to do."""
    before = path.stat().st_size
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return (0, 0)
    # Only result cells are dicts. Summaries written by scripts/param_search.py
    # and other aggregators are lists, and carry no snapshot to strip.
    if not isinstance(data, dict):
        return (0, 0)
    snap = data.get("graph_snapshot")
    if not isinstance(snap, list) or not any("embedding" in f for f in snap):
        return (0, 0)
    for fact in snap:
        fact.pop("embedding", None)
    if not dry_run:
        path.write_text(json.dumps(data))
    return (before, len(json.dumps(data)))


def main() -> None:
    ap = argparse.ArgumentParser(description="Drop embeddings from result cells")
    ap.add_argument("root", nargs="?", default="artifacts/results")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_before = total_after = touched = 0
    for path in sorted(Path(args.root).rglob("*.json")):
        if path.name in SKIP or path.name.endswith(".graph.json"):
            continue
        before, after = compact_file(path, args.dry_run)
        if before:
            touched += 1
            total_before += before
            total_after += after

    verb = "would free" if args.dry_run else "freed"
    print(f"{touched} cells compacted · "
          f"{total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB "
          f"({verb} {(total_before - total_after) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
