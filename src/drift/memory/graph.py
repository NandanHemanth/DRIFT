"""Bitemporal knowledge-graph memory store.

Every fact (edge) carries two timelines, following the Zep/Graphiti model
(arXiv:2501.13956):
 - valid time:    t_valid_start .. t_invalid_at  (when the fact was true)
 - ingestion time: t_ingested                    (when the agent learned it)

Contradiction handling: adding a fact with the same (subject, predicate) but a
different object closes the valid window of the older fact instead of deleting
it - history is non-lossy until a forgetting policy decides otherwise.
"""
from __future__ import annotations

import itertools
import json
import re
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from drift.embeddings import cosine
from drift.memory.normalize import entity_key, is_multi_valued, relation_key

# Predicates that are functional (one true object at a time) -> contradiction closes old fact.
FUNCTIONAL_PREDICATES = {
    "lives_in", "works_at", "job", "relationship_status", "owns_pet", "studies", "located_in", "age",
}

# Hybrid retrieval weights: (semantic cosine, lexical overlap, recency prior).
# These are a fixed design constant, not a tuned parameter: the same weighting is
# used by every policy in every cell, so it cannot explain a difference *between*
# policies, which is what every research question in this thesis asks about.
# src/analysis/sensitivity.py sweeps them to show the conclusions do not depend on
# the specific values; changing this default invalidates the published results.
DEFAULT_RETRIEVAL_WEIGHTS = (0.6, 0.3, 0.1)

# Fusion method for combining the three retrieval signals. "weighted" is the
# published convex combination. "rrf" is reciprocal rank fusion, which needs no
# weights at all and is what Zep uses (Rasmussen et al. 2025, after Cormack et
# al., SIGIR 2009); it exists here so the weighted formula can be compared
# against a parameter-free alternative rather than only against itself.
DEFAULT_FUSION = "weighted"
RRF_K = 60  # the constant from the original RRF paper, used unchanged

# Speech-act predicates: these record that an utterance happened, not a state that
# can be superseded, so they never trigger contradiction -- not even under "*".
# Without this guard a degenerate extraction (every fact coming back as
# `speaker / stated / <whole line>`) makes every new fact contradict the previous
# one: measured 379 of 380 facts invalidated on a corpus whose true count is 133.
# That failure is silent and looks exactly like a policy result.
NEVER_FUNCTIONAL = {
    "stated", "said", "says", "mentioned", "asked", "noted", "reported",
    "told", "wrote", "discussed", "talked_about", "utterance",
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
    # When a policy pruned this fact. `active=False` records *that* a fact was
    # dropped; this records *when*, which is what makes a run replayable as a
    # sequence of events rather than a single end state. Nullable and defaulted,
    # so older snapshots without the field still load through from_dict().
    t_pruned: float | None = None

    @property
    def invalidated(self) -> bool:
        return self.t_invalid_at is not None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Fact":
        # Tolerate snapshots written before a field existed, and ignore any
        # extra keys a future version might add -- a results file from an older
        # run must never fail to load into the analysis tooling.
        allowed = {f.name for f in fields(Fact)}
        return Fact(**{k: v for k, v in d.items() if k in allowed})


class BitemporalGraph:
    def __init__(self, embedder, functional_predicates: set[str] | str | None = None,
                 weights: tuple[float, float, float] | None = None,
                 fusion: str | None = None,
                 relation_matching: str | None = None,
                 relation_sim: float | None = None,
                 contradiction_judge=None):
        """functional_predicates selects which predicates admit only one true
        object at a time, and therefore trigger contradiction handling.

        The default set is tuned to personal-life conversation (lives_in,
        works_at, ...), which silently makes contradiction a no-op on any corpus
        outside that domain -- a fact-consolidation corpus where every predicate
        is functional would record zero invalidations, so P2 would look inert
        for reasons that have nothing to do with the policy. Pass an explicit
        set, or "*" to treat every predicate as functional.

        weights is the (semantic, lexical, recency) hybrid retrieval weighting.
        It defaults to DEFAULT_RETRIEVAL_WEIGHTS and exists so the sensitivity
        analysis can vary it; no experimental config sets it.
        """
        self.embedder = embedder
        self.facts: dict[str, Fact] = {}
        self.pruned_count = 0
        self.write_rejections = 0
        self.functional_predicates: set[str] | str = (
            FUNCTIONAL_PREDICATES if functional_predicates is None else functional_predicates
        )
        self.weights: tuple[float, float, float] = weights or DEFAULT_RETRIEVAL_WEIGHTS
        self.fusion: str = fusion or DEFAULT_FUSION
        # How contradiction detection decides two facts are about the same thing.
        # "exact" (published default): same subject (case-insensitive) and same
        # predicate string. "normalized": compare normalised keys
        # (drift.memory.normalize), and never treat list-like relations
        # (meetings, deliverables, ...) as single-valued under "*". relation_sim,
        # when set, also accepts two relation names whose embeddings are at least
        # that similar.
        self.relation_matching: str = relation_matching or "exact"
        if self.relation_matching not in ("exact", "normalized", "llm"):
            raise ValueError(f"unknown relation_matching {self.relation_matching!r}")
        self.relation_sim = relation_sim
        self._rel_emb: dict[str, list[float]] = {}
        # "llm" mode: a callable judge(new_fact, candidates) -> facts to close.
        self.contradiction_judge = contradiction_judge
        if self.relation_matching == "llm" and contradiction_judge is None:
            raise ValueError("relation_matching='llm' needs a contradiction_judge")
        self.llm_judgements = 0

    def _is_functional(self, predicate: str) -> bool:
        if predicate.strip().lower() in NEVER_FUNCTIONAL:
            return False
        if self.functional_predicates == "*":
            if self.relation_matching == "normalized" and is_multi_valued(predicate):
                return False
            return True
        if self.relation_matching == "normalized":
            key = relation_key(predicate)
            return predicate in self.functional_predicates or any(
                relation_key(p) == key for p in self.functional_predicates)
        return predicate in self.functional_predicates

    def _same_relation(self, a: str, b: str) -> bool:
        if self.relation_matching == "exact":
            return a == b
        ka, kb = relation_key(a), relation_key(b)
        if ka == kb:
            return True
        if self.relation_sim is None:
            return False
        for k in (ka, kb):
            if k not in self._rel_emb:
                self._rel_emb[k] = self.embedder.embed(k)
        return cosine(self._rel_emb[ka], self._rel_emb[kb]) >= self.relation_sim

    def _same_value(self, a: str, b: str) -> bool:
        if self.relation_matching == "exact":
            return a.lower() == b.lower()
        return entity_key(a) == entity_key(b)

    def _same_subject(self, a: str, b: str) -> bool:
        if self.relation_matching == "exact":
            return a.lower() == b.lower()
        return entity_key(a) == entity_key(b)

    def _crossed(self, old: Fact, new: Fact) -> bool:
        """Same relation, one of the two facts written the other way round.

        Extractors do not agree on direction: one stores
        "Ardern | head_of_government_of | New Zealand", a later session
        "New Zealand | head_of_government | Hipkins". The entity the relation is
        about (New Zealand) is then the object of one fact and the subject of the
        other, so a subject-only check never sees the change. This treats the two
        as the same slot when the shared entity sits on opposite sides and the
        remaining ends differ. Two facts that share only their object
        ("Duterte | head_of_government_of | Philippines" and
        "Marcos | head_of_government_of | Philippines") are deliberately NOT
        matched, because the same shape also covers "A | citizen_of | Malta" and
        "B | citizen_of | Malta", where both are true at once.
        """
        if self._same_value(old.object, new.subject) and not self._same_value(old.subject, new.object):
            return not self._same_value(old.subject, new.subject)
        if self._same_value(old.subject, new.object) and not self._same_value(old.object, new.subject):
            return not self._same_value(old.object, new.object)
        return False

    # ------------------------------------------------------------------ write
    def add_fact(self, subject: str, predicate: str, object_: str, text: str,
                 t_event: float, provenance: str = "conversation", salience: float = 1.0) -> Fact:
        fact = Fact(
            subject=subject.strip(), predicate=predicate.strip(), object=object_.strip(),
            text=text.strip(), t_valid_start=t_event, t_ingested=t_event,
            provenance=provenance, salience=salience,
            embedding=self.embedder.embed(text),
        )
        if self.relation_matching == "llm":
            if predicate.strip().lower() not in NEVER_FUNCTIONAL:
                keys = {entity_key(fact.subject), entity_key(fact.object)}
                cands = [o for o in self.facts.values()
                         if o.active and not o.invalidated and o.t_valid_start <= t_event
                         and not self._same_value(o.object, fact.object)
                         and keys & {entity_key(o.subject), entity_key(o.object)}]
                if cands:
                    cands.sort(key=lambda o: -cosine(fact.embedding, o.embedding))
                    self.llm_judgements += 1
                    for other in self.contradiction_judge(fact, cands):
                        other.t_invalid_at = t_event
        elif self._is_functional(predicate):
            for other in self.facts.values():
                if not (other.active and not other.invalidated
                        and other.t_valid_start <= t_event
                        and self._same_relation(other.predicate, fact.predicate)):
                    continue
                if (self._same_subject(other.subject, fact.subject)
                        and not self._same_value(other.object, fact.object)):
                    other.t_invalid_at = t_event
                elif self.relation_matching == "normalized" and self._crossed(other, fact):
                    other.t_invalid_at = t_event
        self.facts[fact.id] = fact
        return fact

    def prune(self, fact_id: str, now: float | None = None) -> None:
        """Deactivate a fact. `now` stamps when, for replay; policies pass the
        session time they are running at. Omitting it keeps the old behaviour."""
        f = self.facts.get(fact_id)
        if f and f.active:
            f.active = False
            f.t_pruned = now
            self.pruned_count += 1

    # --------------------------------------------------------------- retrieve
    def _signals(self, query: str, candidates: list[Fact], now: float | None):
        """Per-fact (semantic, lexical, recency) signal values, all in [0, 1].

        Shared by both fusion methods so that the only thing separating them is
        how the three signals are combined, not how they are computed.
        """
        q_emb = self.embedder.embed(query)
        q_tokens = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
        t_max = now if now is not None else max(f.t_valid_start for f in candidates)
        t_min = min(f.t_valid_start for f in candidates)
        span = max(1.0, t_max - t_min)
        out = {}
        for f in candidates:
            f_tokens = {t for t in re.findall(r"[a-z0-9]+", f.text.lower()) if len(t) > 2}
            out[f.id] = (
                cosine(q_emb, f.embedding),
                len(q_tokens & f_tokens) / max(1, len(q_tokens)),
                (f.t_valid_start - t_min) / span,
            )
        return out

    def _rrf(self, candidates: list[Fact], signals: dict, k_rrf: int = RRF_K) -> dict:
        """Reciprocal rank fusion: score(f) = sum over signals of 1 / (k + rank).

        Rank-based rather than score-based, so it needs no weights and is immune
        to the three signals living on different scales. This is the fusion Zep
        uses (Rasmussen et al. 2025, citing Cormack et al., SIGIR 2009), and it
        is included here as the weight-free comparison point for the weighted
        formula rather than as a replacement for it.
        """
        scores = {f.id: 0.0 for f in candidates}
        for i in range(3):
            ordered = sorted(candidates, key=lambda f: -signals[f.id][i])
            for rank, f in enumerate(ordered, start=1):
                scores[f.id] += 1.0 / (k_rrf + rank)
        return scores

    def search(self, query: str, k: int = 8, now: float | None = None,
               include_invalidated: bool = True,
               weights: tuple[float, float, float] | None = None,
               fusion: str | None = None) -> list[Fact]:
        """Hybrid retrieval over three signals: semantic, lexical, recency.

        fusion selects how they are combined. "weighted" is the published
        behaviour, a convex combination using `weights`. "rrf" is reciprocal
        rank fusion, which takes no weights at all. Both see identical signals.

        weights overrides self.weights for this call only, which is what lets
        the sensitivity sweep vary the weighting without re-ingesting the graph.
        """
        mode = fusion or self.fusion
        w_sem, w_lex, w_rec = weights or self.weights
        candidates = [f for f in self.facts.values() if f.active]
        if not include_invalidated:
            candidates = [f for f in candidates if not f.invalidated]
        if not candidates:
            return []
        signals = self._signals(query, candidates, now)

        if mode == "rrf":
            scores = self._rrf(candidates, signals)
        elif mode == "weighted":
            scores = {f.id: w_sem * signals[f.id][0] + w_lex * signals[f.id][1]
                             + w_rec * signals[f.id][2] for f in candidates}
        else:
            raise ValueError(f"unknown fusion {mode!r}, expected 'weighted' or 'rrf'")

        return sorted(candidates, key=lambda f: scores[f.id], reverse=True)[:k]

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
        g = BitemporalGraph(self.embedder, self.functional_predicates, self.weights, self.fusion,
                            self.relation_matching, self.relation_sim, self.contradiction_judge)
        for f in self.facts.values():
            g.facts[f.id] = Fact.from_dict(f.to_dict())
        return g
