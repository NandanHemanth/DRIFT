"""The embedding cache returns the first vector and never re-asks the backend."""
from drift.embeddings import CachedEmbedder


class Counting:
    name, model = "fake", "fake-1"

    def __init__(self):
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        return [float(len(text)), float(self.calls)]


def test_cache_hits_memory_and_disk(tmp_path):
    inner = Counting()
    a = CachedEmbedder(inner, str(tmp_path))
    v1 = a.embed("hello")
    assert a.embed("hello") == v1 and inner.calls == 1
    b = CachedEmbedder(Counting(), str(tmp_path))     # new process, same disk cache
    assert b.embed("hello") == v1 and b.inner.calls == 0
    assert a.embed("other") != v1 and inner.calls == 2
