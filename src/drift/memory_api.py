"""`Memory`: the integration surface for using DRIFT inside another agent.

The rest of this package is organised around running controlled experiments, in
which the policy is the independent variable and everything is driven from a
config file. That layout is right for producing the results but wrong for
someone who has already chosen a policy and wants memory in their own agent.

This module is a thin composition of pieces that already exist:
`BitemporalGraph` for the substrate, `make_policy` for the forgetting rule,
`extract_facts` for triple extraction and `graph.search` for retrieval. It adds
no behaviour of its own, so a `Memory` object and an experiment cell running the
same policy make identical decisions.

Two calls carry the whole interface:

    mem.observe(lines, when=...)   what the agent just saw
    mem.recall(query, k=8)         what the agent should be told about it

Everything else is optional.

Example
-------
    import time
    from drift import Memory

    mem = Memory(
        policy="P2",                        # bitemporal contradiction invalidation
        provider="openrouter:z-ai/glm-5.2", # used only for triple extraction
        embedder="ollama:nomic-embed-text",
        functional_predicates=["lives_in", "works_at", "assigned_to"],
    )

    mem.observe(["user: I just moved to Seattle."], when=time.time())
    for fact in mem.recall("Where does the user live?"):
        print(fact.text)

    print(mem.stats())

Choosing `policy` is the decision this whole framework exists to inform. If your
agent's facts get corrected over time, the measured answer is `"P2"`, and it is
specifically not `"P3"`. See README.md, section "Which policy should I use".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from drift.embeddings import make_embedder
from drift.memory.extraction import extract_facts
from drift.memory.graph import BitemporalGraph, Fact
from drift.policies import Policy, make_policy
from drift.providers import BaseProvider, make_provider


@dataclass
class Memory:
    """Bitemporal agent memory with a pluggable forgetting policy.

    policy
        A policy spec string: "NOMEM", "P0", "P1:ttl_days=30", "P2", "P3", "P4",
        "P5". Parameters after the colon are passed to the policy constructor.
    provider
        Spec for the model used to extract triples from text, for example
        "openrouter:z-ai/glm-5.2" or "mock" for offline use. Any
        OpenAI-compatible endpoint works; see `drift/providers.py`.
    embedder
        "hashing" (offline, deterministic) or "ollama:<model>" for real
        semantics. Retrieval quality depends on this more than on anything else.
    functional_predicates
        Which predicates admit exactly one true object at a time, and therefore
        trigger contradiction handling. Pass a list, or "*" if every predicate
        in your domain is single-valued. Leaving this at the default keeps the
        built-in personal-life set, under which a domain outside personal chat
        records zero invalidations and P2 has nothing to act on. This is the
        single most consequential setting after `policy`.
    cache_dir
        Provider responses are cached on disk by SHA-256 of the request, so
        repeated ingestion of the same text is free and deterministic.
    """

    policy: str = "P2"
    provider: str = "mock"
    embedder: str = "hashing"
    functional_predicates: list[str] | str | None = None
    cache_dir: str = ".drift_cache"

    _graph: BitemporalGraph = field(init=False, repr=False)
    _policy: Policy = field(init=False, repr=False)
    _provider: BaseProvider = field(init=False, repr=False)

    def __post_init__(self) -> None:
        fp = self.functional_predicates
        if isinstance(fp, (list, tuple, set)):
            fp = set(fp)
        self._graph = BitemporalGraph(make_embedder(self.embedder),
                                      functional_predicates=fp)
        self._policy = make_policy(self.policy)
        self._provider = make_provider(self.provider, self.cache_dir)

    # ------------------------------------------------------------------ write

    def observe(self, lines: list[str], when: float,
                provenance: str = "conversation") -> dict:
        """Record what the agent just saw and run the policy's maintenance pass.

        `lines` are "Speaker: utterance" strings. `when` is the epoch time the
        content became true, which is the valid-time the substrate reasons over;
        pass the real event time rather than the ingestion time when they
        differ, since that distinction is the point of a bitemporal store.
        `provenance` tags the writer, which is what makes cross-writer
        invalidation auditable when several agents share one memory.

        Returns {"extracted": int, "written": int}. The gap between the two is
        how many writes the policy rejected.
        """
        facts = extract_facts(self._provider, lines)
        written = 0
        for f in facts:
            if self._policy.on_write(f, self._graph):
                self._graph.add_fact(f["subject"], f["predicate"], f["object"],
                                     f["text"], t_event=when, provenance=provenance)
                written += 1
        self._policy.after_session(self._graph, self._provider, now=when)
        return {"extracted": len(facts), "written": written}

    def remember(self, subject: str, predicate: str, object_: str,
                 when: float, text: str | None = None,
                 provenance: str = "system") -> Fact | None:
        """Write one fact directly, bypassing LLM extraction.

        Use this when your agent already has structured state to record. The
        write gate still applies, so a policy that rejects near-duplicates will
        reject this too; the return is None in that case.
        """
        f = {"subject": subject, "predicate": predicate, "object": object_,
             "text": text or f"{subject} {predicate} {object_}"}
        if not self._policy.on_write(f, self._graph):
            return None
        return self._graph.add_fact(subject, predicate, object_, f["text"],
                                    t_event=when, provenance=provenance)

    # ------------------------------------------------------------------- read

    def recall(self, query: str, k: int = 8, now: float | None = None) -> list[Fact]:
        """Retrieve the facts the agent should be told about `query`.

        Hybrid retrieval (embedding cosine, lexical overlap, recency prior) is
        followed by the policy's retrieval filter. Under P2 that filter drops
        facts whose valid-time window has closed, which is the mechanism that
        keeps a superseded value from reaching the model.
        """
        retrieved = self._graph.search(query, k=k, now=now)
        return self._policy.on_retrieve(retrieved, now or 0.0)

    def context(self, query: str, k: int = 8, now: float | None = None,
                show_supersession: bool = False) -> str:
        """`recall` rendered as a memory block ready to paste into a prompt.

        Each line is prefixed with the date the fact became true, which is what
        lets a model reason about currency. `show_supersession` additionally
        labels closed facts; it is off by default because telling the model
        which facts are superseded hands the policy's job to the model and
        makes every policy look alike.
        """
        from drift.pipeline import render_fact  # local: keeps import graph flat

        facts = self.recall(query, k=k, now=now)
        if not facts:
            return "(no relevant memory)"
        return "\n".join(render_fact(f, show_supersession) for f in facts)

    # ------------------------------------------------------------- inspection

    def stats(self) -> dict:
        """Counts of total, active, superseded-but-present, pruned and rejected."""
        return self._graph.stats()

    def facts(self, include_pruned: bool = False) -> list[Fact]:
        return [f for f in self._graph.facts.values()
                if include_pruned or f.active]

    def snapshot(self) -> list[dict]:
        """Serialisable memory state.

        Every fact carries `t_ingested`, `t_invalid_at` and `t_pruned`, so this
        is a complete event log rather than a final state: it can be replayed
        through `analysis/timeline.py` to see how memory evolved.
        """
        return [f.to_dict() for f in self._graph.facts.values()]

    @property
    def graph(self) -> BitemporalGraph:
        """The underlying substrate, for anything this facade does not cover."""
        return self._graph
