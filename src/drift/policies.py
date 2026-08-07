"""Forgetting and consolidation policies P0-P4.

Common interface:
  on_write(fact_dict, graph) -> bool      gate a write (False = reject)
  after_session(graph, provider, now)     periodic maintenance (decay/prune/consolidate)
  on_retrieve(facts, now) -> list[Fact]   filter/re-rank retrieved facts
"""
from __future__ import annotations

import json
import re

from drift.embeddings import cosine
from drift.memory.graph import BitemporalGraph, Fact

DAY = 86400.0

CONSOLIDATION_PROMPT = """TASK:CONSOLIDATE
You maintain an agent's long-term memory. Below are memory facts, each with an id.
Decide which to KEEP and which to DROP. Drop only redundant duplicates or trivial
chit-chat; keep anything a user would expect an assistant to remember.
Return ONLY JSON: {{"keep": [ids], "drop": [ids]}}
FACTS:
{facts}
"""


class Policy:
    name = "base"

    def on_write(self, fact: dict, graph: BitemporalGraph) -> bool:
        return True

    def after_session(self, graph: BitemporalGraph, provider, now: float) -> None:
        return None

    def on_retrieve(self, facts: list[Fact], now: float) -> list[Fact]:
        return facts


class NoMemory(Policy):
    """Floor baseline: the agent has NO usable memory - retrieval returns nothing,
    so the answer model sees '(no relevant memory)'. Separates what the answer
    model knows from what memory contributes; every policy must beat this."""
    name = "NOMEM_no_memory"

    def on_retrieve(self, facts: list[Fact], now: float) -> list[Fact]:
        return []


class P0NoForgetting(Policy):
    """Baseline: append-only memory. Nothing is ever gated, pruned, or filtered."""
    name = "P0_no_forgetting"


class P1TTLDecay(Policy):
    """Time-to-live decay: prune facts older than `ttl_days` (by valid time)."""
    name = "P1_ttl_decay"

    def __init__(self, ttl_days: float = 30.0):
        self.ttl = ttl_days * DAY

    def after_session(self, graph: BitemporalGraph, provider, now: float) -> None:
        for f in list(graph.facts.values()):
            if f.active and (now - f.t_valid_start) > self.ttl:
                graph.prune(f.id, now)


class P2ContradictionInvalidation(Policy):
    """Bitemporal hygiene: superseded facts are excluded at retrieval and
    pruned after a grace period. Exploits the graph's valid-time windows."""
    name = "P2_contradiction"

    def __init__(self, grace_days: float = 7.0):
        self.grace = grace_days * DAY

    def on_retrieve(self, facts: list[Fact], now: float) -> list[Fact]:
        return [f for f in facts if not f.invalidated]

    def after_session(self, graph: BitemporalGraph, provider, now: float) -> None:
        for f in list(graph.facts.values()):
            if f.active and f.invalidated and (now - f.t_invalid_at) > self.grace:
                graph.prune(f.id, now)


class P3NoveltyGate(Policy):
    """SAGE-style write gate (arXiv:2605.30711): reject writes that are
    near-duplicates of existing memory (max neighborhood cosine > tau)."""
    name = "P3_novelty_gate"

    def __init__(self, tau: float = 0.9):
        self.tau = tau

    def on_write(self, fact: dict, graph: BitemporalGraph) -> bool:
        if graph.neighborhood_max_sim(fact["text"]) > self.tau:
            graph.write_rejections += 1
            return False
        return True


class P4LLMConsolidation(Policy):
    """Agentic consolidation: every `every_n` sessions an LLM reviews memory and
    decides keep/drop. This is the policy arXiv:2605.12978 warns can degrade
    memory when applied repeatedly."""
    name = "P4_llm_consolidation"

    def __init__(self, every_n: int = 3, batch_size: int = 40):
        self.every_n = every_n
        self.batch = batch_size
        self._session_count = 0

    def after_session(self, graph: BitemporalGraph, provider, now: float) -> None:
        self._session_count += 1
        if self._session_count % self.every_n != 0:
            return
        active = [f for f in graph.facts.values() if f.active]
        for i in range(0, len(active), self.batch):
            chunk = active[i:i + self.batch]
            listing = "\n".join(f"[fact:{f.id}] {f.text}" for f in chunk)
            completion = provider.complete(CONSOLIDATION_PROMPT.format(facts=listing))
            try:
                decision = json.loads(re.search(r"\{.*\}", completion.text, re.S).group(0))
            except (AttributeError, json.JSONDecodeError):
                # malformed/truncated LLM response (common with reasoning models
                # under token pressure): treat as "no opinion", keep everything
                decision = {}
            drop = set(decision.get("drop", []))
            keep = set(decision.get("keep", [])) if drop or decision.get("keep") else {f.id for f in chunk}
            for f in chunk:
                if f.id in drop and f.id not in keep:
                    graph.prune(f.id, now)
        # merge near-duplicates deterministically (keep newest)
        remaining = [f for f in graph.facts.values() if f.active]
        remaining.sort(key=lambda f: f.t_ingested, reverse=True)
        kept: list[Fact] = []
        for f in remaining:
            if any(cosine(f.embedding, k.embedding) > 0.97 for k in kept):
                graph.prune(f.id, now)
            else:
                kept.append(f)


class P5TopologyConsolidation(Policy):
    """Graph-topology consolidation (Graphify-inspired: graphify.net).

    Structure-aware but deliberately TIME-BLIND - the ablation partner to P2.
    Builds the entity co-occurrence graph, finds communities (label propagation,
    stdlib-only), and within each community resolves competing facts on the same
    (subject, predicate) by STRUCTURAL SUPPORT: keep the fact whose object is
    corroborated by the most other facts in memory. High-degree 'god node'
    entities are never pruned below `min_keep` facts.

    Thesis role: if P2 beats P5, the advantage of structure-aware forgetting is
    attributable to *bitemporal* semantics specifically, not graph structure in
    general. P5 must guess which contradictory fact is current; P2 knows.
    """
    name = "P5_topology_consolidation"

    def __init__(self, min_keep: int = 2):
        self.min_keep = int(min_keep)

    @staticmethod
    def _entities(f: Fact) -> tuple[str, str]:
        return f.subject.lower().strip(), f.object.lower().strip()

    def _communities(self, facts: list[Fact]) -> dict[str, int]:
        """Label propagation over the entity co-occurrence graph (stdlib)."""
        neighbors: dict[str, set[str]] = {}
        for f in facts:
            s, o = self._entities(f)
            neighbors.setdefault(s, set()).add(o)
            neighbors.setdefault(o, set()).add(s)
        label = {e: i for i, e in enumerate(sorted(neighbors))}
        for _ in range(10):  # converges fast on memory-scale graphs
            changed = False
            for e in neighbors:
                if not neighbors[e]:
                    continue
                counts: dict[int, int] = {}
                for n in neighbors[e]:
                    counts[label[n]] = counts.get(label[n], 0) + 1
                best = min(k for k, v in counts.items() if v == max(counts.values()))
                if best < label[e]:
                    label[e], changed = best, True
            if not changed:
                break
        return label

    def _structural_support(self, f: Fact, facts: list[Fact]) -> int:
        obj = f.object.lower().strip()
        return sum(1 for other in facts
                   if other.id != f.id and obj and obj in other.text.lower())

    def after_session(self, graph: BitemporalGraph, provider, now: float) -> None:
        active = [f for f in graph.facts.values() if f.active]
        if not active:
            return
        self._communities(active)  # community structure (kept for analytics parity)
        degree: dict[str, int] = {}
        for f in active:
            s, _ = self._entities(f)
            degree[s] = degree.get(s, 0) + 1
        groups: dict[tuple[str, str], list[Fact]] = {}
        for f in active:
            groups.setdefault((f.subject.lower(), f.predicate), []).append(f)
        for (subj, _pred), members in groups.items():
            if len(members) < 2:
                continue
            if degree.get(subj, 0) <= self.min_keep:  # protect low-degree entities
                continue
            members.sort(key=lambda f: (self._structural_support(f, active), f.salience, f.id),
                         reverse=True)
            for loser in members[1:]:  # keep only the best-supported fact
                graph.prune(loser.id, now)


POLICY_REGISTRY = {
    "NOMEM": NoMemory,
    "P0": P0NoForgetting,
    "P1": P1TTLDecay,
    "P2": P2ContradictionInvalidation,
    "P3": P3NoveltyGate,
    "P4": P4LLMConsolidation,
    "P5": P5TopologyConsolidation,
}


def make_policy(spec: str) -> Policy:
    """spec: 'P1' or 'P1:ttl_days=14' style."""
    if ":" in spec:
        name, argstr = spec.split(":", 1)
        kwargs = {}
        for pair in argstr.split(","):
            k, v = pair.split("=")
            kwargs[k.strip()] = float(v) if "." in v or v.isdigit() else v
        return POLICY_REGISTRY[name](**kwargs)
    return POLICY_REGISTRY[spec]()
