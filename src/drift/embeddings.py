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


class CachedEmbedder:
    """Memoise another embedder in memory and on disk.

    An embedding depends only on (model, text), and every cell of a matrix embeds
    the same facts and questions again: 35 cells x 3 runs re-sent each text to
    the local Ollama server, which handles one request at a time. The cache
    returns the vector Ollama produced the first time, so results are unchanged
    and only repeated work is skipped. Writes go to a temporary file and are
    renamed into place, so parallel runs never read a half-written entry.
    """

    def __init__(self, inner, cache_dir: str = ".drift_cache/emb"):
        import os
        import threading
        self.inner = inner
        self.name = getattr(inner, "name", "embedder")
        self.model = getattr(inner, "model", self.name)
        self.dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._mem: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _path(self, text: str) -> str:
        import os
        key = hashlib.sha256(json.dumps([self.name, self.model, text]).encode()).hexdigest()
        return os.path.join(self.dir, key[:2], key + ".json")

    def embed(self, text: str) -> list[float]:
        import os
        import uuid
        with self._lock:
            hit = self._mem.get(text)
        if hit is not None:
            return hit
        path = self._path(text)
        try:
            with open(path) as fh:
                vec = json.load(fh)
        except (OSError, ValueError):
            vec = self.inner.embed(text)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
            with open(tmp, "w") as fh:
                json.dump(vec, fh)
            os.replace(tmp, path)
        with self._lock:
            self._mem[text] = vec
        return vec


def make_embedder(spec: str, cache: bool = True):
    if spec == "hashing":
        return HashingEmbedder()
    if spec.startswith("ollama"):
        model = spec.split(":", 1)[1] if ":" in spec else "nomic-embed-text"
        emb = OllamaEmbedder(model)
        return CachedEmbedder(emb) if cache else emb
    raise ValueError(f"Unknown embedder: {spec}")
