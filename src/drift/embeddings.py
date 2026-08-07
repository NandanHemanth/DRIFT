"""Embedding backends.

HashingEmbedder: deterministic, dependency-free feature-hashing embedder used
for tests/offline runs. OllamaEmbedder: local embeddings on Apple Silicon via
Ollama (e.g. `ollama pull nomic-embed-text`).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class HashingEmbedder:
    """Feature-hashing bag-of-words embedding. Deterministic and offline.

    Not semantically deep, but preserves lexical similarity structure well
    enough for unit tests and pipeline smoke benchmarks.
    """

    name = "hashing-256"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        grams = tokens + [" ".join(p) for p in zip(tokens, tokens[1:])]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class OllamaEmbedder:
    name = "ollama"

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def embed(self, text: str) -> list[float]:
        req = urllib.request.Request(
            f"{self.base_url}/api/embeddings",
            data=json.dumps({"model": self.model, "prompt": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["embedding"]


def make_embedder(spec: str):
    if spec == "hashing":
        return HashingEmbedder()
    if spec.startswith("ollama"):
        model = spec.split(":", 1)[1] if ":" in spec else "nomic-embed-text"
        return OllamaEmbedder(model)
    raise ValueError(f"Unknown embedder: {spec}")
