"""Preflight: is every provider in a config actually alive right now?

Motivation
----------
Endpoints disappear. Mid-project, NVIDIA stopped serving a model this thesis had
been using for extraction and began returning HTTP 410. The published benchmarks
did not notice, because their extraction calls were already in `.drift_cache` and
never touched the network. The failure only surfaced when a new dataset produced
a cache miss, and it surfaced as a crash several minutes into a sweep.

This script makes that a ten-second check instead. It sends the smallest possible
prompt to every model named in a config, in every role, and reports which are
reachable. Run it before any campaign that will miss the cache.

Cost is one tiny completion per provider, which is negligible next to the run it
protects.

Usage:
    python scripts/check_providers.py --config configs/convomem.json
    python scripts/check_providers.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drift.providers import make_provider  # noqa: E402

ROLES = ("extract_model", "judge_model", "models")
PROBE = "Reply with the single word: ok"


def specs_in(cfg: dict) -> list[tuple[str, str]]:
    """Every (role, spec) pair named in a config, de-duplicated but order-kept."""
    out, seen = [], set()
    for role in ROLES:
        value = cfg.get(role)
        if not value:
            continue
        for spec in (value if isinstance(value, list) else [value]):
            if (role, spec) not in seen:
                seen.add((role, spec))
                out.append((role, spec))
    return out


def probe(spec: str, cache_dir: str, timeout_retries: int = 1) -> tuple[bool, str]:
    if spec == "mock":
        return True, "offline mock"
    try:
        provider = make_provider(spec, cache_dir, max_retries=timeout_retries)
        completion = provider.complete(PROBE)
        text = (completion.text or "").strip().replace("\n", " ")
        return True, f"ok ({text[:40]})" if text else "ok (empty reply)"
    except Exception as exc:                       # any failure is a dead route
        return False, f"{type(exc).__name__}: {str(exc)[:110]}"


def check(path: Path) -> list[dict]:
    cfg = json.loads(path.read_text())
    cache_dir = cfg.get("cache_dir", ".drift_cache")
    rows = []
    for role, spec in specs_in(cfg):
        alive, detail = probe(spec, cache_dir)
        rows.append({"config": path.name, "role": role, "spec": spec,
                     "alive": alive, "detail": detail})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Check every provider named in a config")
    ap.add_argument("--config", help="a single config to check")
    ap.add_argument("--all", action="store_true", help="check every config in configs/")
    args = ap.parse_args()

    if args.all:
        paths = sorted(Path("configs").glob("*.json"))
    elif args.config:
        paths = [Path(args.config)]
    else:
        ap.error("pass --config or --all")

    rows = []
    for p in paths:
        try:
            rows.extend(check(p))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[skip] {p}: {exc}")

    width = max((len(r["spec"]) for r in rows), default=10)
    print(f"\n{'config':<34} {'role':<14} {'model':<{width}}  status")
    print("-" * (34 + 14 + width + 10))
    for r in rows:
        mark = "LIVE" if r["alive"] else "DEAD"
        print(f"{r['config']:<34} {r['role']:<14} {r['spec']:<{width}}  {mark}  {r['detail']}")

    dead = [r for r in rows if not r["alive"]]
    unique_dead = {r["spec"] for r in dead}
    print(f"\n{len(rows) - len(dead)} live, {len(dead)} dead")
    if dead:
        print("\nDead routes, which will crash any run that misses the cache:")
        for spec in sorted(unique_dead):
            print(f"  {spec}")
        print("\nA config whose extract_model is a list fails over automatically;")
        print("a single-spec config does not, so give it a list or replace the spec.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
