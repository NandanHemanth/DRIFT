"""DRIFT: Decay and Retention In Forgetful Temporal-graph memory.

A controlled framework for choosing a forgetting policy in LLM agent memory
over a bitemporal knowledge-graph substrate.

Two ways in:

    from drift import Memory            # use DRIFT inside your own agent
    python -m drift.runner --config ... # reproduce or extend the experiments

`Memory` is documented in `drift/memory_api.py`; the experimental harness is
documented in README.md.
"""

from drift.memory_api import Memory
from drift.memory.graph import BitemporalGraph, Fact
from drift.policies import POLICY_REGISTRY, Policy, make_policy

__version__ = "1.0.0"

__all__ = [
    "Memory",
    "BitemporalGraph",
    "Fact",
    "Policy",
    "make_policy",
    "POLICY_REGISTRY",
    "__version__",
]
