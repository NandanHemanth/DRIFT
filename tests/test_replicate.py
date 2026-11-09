"""Replicate runs: run 1 keeps the existing cache keys, later runs make fresh calls."""
import json

from drift.providers import DiskCache, OpenAICompatProvider
from drift.runner import configure_provider


class FakeResp:
    def __init__(self, text):
        self._b = json.dumps({"choices": [{"message": {"content": text}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _provider(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    p = OpenAICompatProvider("openrouter", "m", cache=DiskCache(tmp_path))
    p.limiter.min_interval = 0
    return p


def test_replicate_zero_keeps_keys_and_others_call_again(tmp_path, monkeypatch):
    calls = []

    def fake_open(req, timeout=0):
        calls.append(1)
        return FakeResp(f"answer {len(calls)}")

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    p = _provider(tmp_path, monkeypatch)
    a1 = p.complete("q").text
    assert p.complete("q").cached                     # run 1 replays from cache
    configure_provider(p, "openrouter:m", {"replicate": 2})
    assert p.replicate == 2
    a2 = p.complete("q")
    assert not a2.cached and len(calls) == 2          # run 2 is a fresh call
    assert p.complete("q").cached                     # and run 2 caches under its own key
    configure_provider(p, "openrouter:m", {})         # no replicate key: untouched (stays 2)
    p.replicate = 0
    assert p.complete("q").text == a1                 # run 1 answer still there
