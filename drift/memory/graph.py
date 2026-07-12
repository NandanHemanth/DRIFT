"""Bitemporal knowledge-graph memory store.

Every fact (edge) carries two timelines, following the Zep/Graphiti model
(arXiv:2501.13956):
  - valid time:    t_valid_start .. t_invalid_at  (when the fact was true)
  - ingestion time: t_ingested                    (when the agent learned it)

Contradiction handling: adding a fact with the same (subject, predicate) but a
different object closes the valid window of the older fact instead of deleting
it — history is non-lossy until a forgetting policy decides otherwise.
"""
from __future__ import annotations

import itertools
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from drift.embeddings import cosine

# Predicates that are functional (one true object at a time) -> contradiction closes old fact.
FUNCTIONAL_PREDICATES = {
    "lives_in", "works_at", "job", "relationship_status", "owns_pet", "studies", "located_in", "age",
}


@dataclass
class Fact:
    subject: str
    predicate: str
    object: str
    text: str
    t_valid_start: float
    t_ingested: float
    t_invalid_at: float | None = None
    salience: float = 1.0
    provenance: str = "conversation"
    embedding: list[float] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    active: bool = True  # False once a policy prunes it

    @property
    def invalidated(self) -> bool:
        return self.t_invalid_at is not None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Fact":
        return Fact(**d)


class BitemporalGraph:
    def __init__(self, embedder):
        self.embedder = embedder
        self.facts: dict[str, Fact] = {}
        self.pruned_count = 0
        self.write_rejections = 0

    # ------------------------------------------------------------------ write
    def add_fact(self, subject: str, predicate: str, object_: str, text: str,
                 t_event: float, provenance: str = "conversation", salience: float = 1.0) -> Fact:
        fact = Fact(
            subject=subject.strip(), predicate=predicate.strip(), object=object_.strip(),
            text=text.strip(), t_valid_start=t_event, t_ingested=t_event,
            provenance=provenance, salience=salience,
            embedding=self.embedder.embed(text),
        )
        if predicate in FUNCTIONAL_PREDICATES:
            for other in self.facts.values():
                if (other.active and not other.invalidated
                        and other.subject.lower() == fact.subject.lower()
                        and other.predicate == fact.predicate
                        and other.object.lower() != fact.object.lower()
                        and other.t_valid_start <= t_event):
                    other.t_invalid_at = t_event
        self.facts[fact.id] = fact
        return fact

    def prune(self, fact_id: str) -> None:
        f = self.facts.get(fact_id)
        if f and f.active:
            f.active = False
            self.pruned_count += 1

    # --------------------------------------------------------------- retrieve
    def search(self, query: str, k: int = 8, now: float | None = None,
               include_invalidated: bool = True) -> list[Fact]:
        """Hybrid retrieval: embedding cosine + lexical overlap + recency prior."""
        q_emb = self.embedder.embed(query)
        q_tokens = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
        candidates = [f for f in self.facts.values() if f.active]
        if not include_invalidated:
            candidates = [f for f in candidates if not f.invalidated]
        if not candidates:
            return []
        t_max = now if now is not None else max(f.t_valid_start for f in candidates)
        t_min = min(f.t_valid_start for f in candidates)
        span = max(1.0, t_max - t_min)

        def score(f: Fact) -> float:
            sem = cosine(q_emb, f.embedding)
            f_tokens = {t for t in re.findall(r"[a-z0-9]+", f.text.lower()) if len(t) > 2}
            lex = len(q_tokens & f_tokens) / max(1, len(q_tokens))
            rec = (f.t_valid_start - t_min) / span
            return 0.6 * sem + 0.3 * lex + 0.1 * rec

        return sorted(candidates, key=score, reverse=True)[:k]

    def neighborhood_max_sim(self, text: str) -> float:
        """Max cosine similarity of `text` against all active facts (novelty check)."""
        emb = self.embedder.embed(text)
        sims = [cosine(emb, f.embedding) for f in self.facts.values() if f.active]
        return max(sims, default=0.0)

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict:
        active = [f for f in self.facts.values() if f.active]
        return {
            "total_facts": len(self.facts),
            "active_facts": len(active),
            "invalidated_active": sum(1 for f in active if f.invalidated),
            "pruned": self.pruned_count,
            "write_rejections": self.write_rejections,
        }

    # ------------------------------------------------------------ persistence
    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps([f.to_dict() for f in self.facts.values()]))

    @classmethod
    def load(cls, path: str | Path, embedder) -> "BitemporalGraph":
        g = cls(embedder)
        for d in json.loads(Path(path).read_text()):
            f = Fact.from_dict(d)
            g.facts[f.id] = f
        return g

    def snapshot(self) -> "BitemporalGraph":
        """Deep-ish copy so policies can be compared from an identical base graph."""
        g = BitemporalGraph(self.embedder)
        for f in self.facts.values():
            g.facts[f.id] = Fact.from_dict(f.to_dict())
        return g
