"""Lightweight, dependency-free progress reporting for long-running campaigns.

Stdlib only (matches the project's `dependencies = []` policy -- no tqdm).
Two pieces:

  ProgressBar     a single live-updating line for the work *inside* one cell
                  (e.g. 300 questions), showing elapsed/ETA and optional
                  running stats (accuracy/staleness so far).
  CampaignTracker one line printed after each cell completes, tracking
                  elapsed/ETA across the *whole* campaign (all cells in one
                  `python -m drift.runner` / `python -m drift.swarm` run).

Both write to stdout with a carriage return so the bar updates in place
rather than spamming one line per question; each cell/campaign print ends
with a real newline so it stays in scrollback.
"""
from __future__ import annotations

import sys
import time


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


class ProgressBar:
    """Live-updating single-line bar for the work inside one cell.

    Call update() once per unit of work (e.g. once per question answered),
    optionally passing a short `stats` string (running accuracy, etc.) to
    display alongside elapsed time and ETA. Call close() once done to leave
    the final state on screen and move to a fresh line.
    """

    def __init__(self, total: int, label: str = "", width: int = 24):
        self.total = max(1, total)
        self.label = label
        self.width = width
        self.start = time.monotonic()
        self.n = 0

    def update(self, n: int = 1, stats: str = "") -> None:
        self.n += n
        frac = min(1.0, self.n / self.total)
        filled = int(self.width * frac)
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = time.monotonic() - self.start
        rate = self.n / elapsed if elapsed > 0 else 0.0
        eta = (self.total - self.n) / rate if rate > 0 else 0.0
        prefix = f"{self.label} " if self.label else ""
        line = (f"\r  {prefix}[{bar}] {self.n}/{self.total} ({frac * 100:5.1f}%) "
                f"elapsed={format_duration(elapsed)} eta={format_duration(eta)}")
        if stats:
            line += f" | {stats}"
        sys.stdout.write(line.ljust(120))
        sys.stdout.flush()

    def close(self) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()


class CampaignTracker:
    """Tracks elapsed/ETA across every cell in a multi-cell campaign."""

    def __init__(self, total_cells: int):
        self.total_cells = max(1, total_cells)
        self.start = time.monotonic()
        self.done = 0

    def cell_done(self) -> str:
        self.done += 1
        elapsed = time.monotonic() - self.start
        rate = self.done / elapsed if elapsed > 0 else 0.0
        eta = (self.total_cells - self.done) / rate if rate > 0 else 0.0
        frac = self.done / self.total_cells
        return (f"[campaign {self.done}/{self.total_cells} ({frac * 100:4.1f}%)] "
                f"elapsed={format_duration(elapsed)} est.remaining={format_duration(eta)}")
