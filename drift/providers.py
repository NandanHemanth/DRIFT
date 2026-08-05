"""LLM provider layer: OpenAI-compatible clients, rate limiting, disk cache.

Supported free providers (set env var, pick a model):
  - Groq        GROQ_API_KEY        https://api.groq.com/openai/v1
  - Cerebras    CEREBRAS_API_KEY    https://api.cerebras.ai/v1
  - NVIDIA NIM  NVIDIA_API_KEY      https://integrate.api.nvidia.com/v1
  - Google      GEMINI_API_KEY      https://generativelanguage.googleapis.com/v1beta/openai
  - OpenRouter  OPENROUTER_API_KEY  https://openrouter.ai/api/v1

`MockProvider` is a deterministic offline provider used by the test suite
and the smoke benchmark, so the whole pipeline runs with zero API calls.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

def load_dotenv(path: str | Path = ".env") -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (stdlib-only).

    Real environment variables take precedence: a key already set in the
    shell is never overwritten. Searches the given path, then the repo root
    (parent of this package), so it works from any working directory.
    """
    candidates = [Path(path), Path(__file__).resolve().parent.parent / ".env"]
    for p in candidates:
        if not p.is_file():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and value and key not in os.environ:
                os.environ[key] = value
        return  # first file found wins


load_dotenv()

PROVIDER_PRESETS = {
    # Local Ollama server (`ollama serve`), OpenAI-compatible endpoint. No API
    # key needed -- unlimited, free, zero rate limit beyond your own hardware.
    # rpm is set high since the real pacing constraint is local inference
    # throughput (which Ollama's own request queue already manages), not a
    # remote quota.
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": "OLLAMA_API_KEY", "rpm": 300, "requires_key": False},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY", "rpm": 25},
    "cerebras": {"base_url": "https://api.cerebras.ai/v1", "key_env": "CEREBRAS_API_KEY", "rpm": 25},
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY", "rpm": 35},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
        "rpm": 8,
    },
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY", "rpm": 15},
    # Extra free-tier headroom (verified working July 2026; see STORY.md "top 5"
    # note). Free-model slugs on OpenRouter rotate — check openrouter.ai/models
    # if one 404s and swap the model name in your config.
    "mistral": {"base_url": "https://api.mistral.ai/v1", "key_env": "MISTRAL_API_KEY", "rpm": 4},
    "hf": {"base_url": "https://router.huggingface.co/v1", "key_env": "HUGGINGFACE_API_KEY", "rpm": 8},
    # Second headroom batch added after the first real-all run exhausted
    # Gemini's daily judge quota (see FallbackProvider in this module).
    # Verified working July 2026 with a trial key. (Kimi/Moonshot and the
    # aimlapi.com aggregator were also tried but both trial keys came back
    # "insufficient balance/funds" -- those are metered, not free, so they
    # were dropped rather than added as dead weight.)
    "cohere": {"base_url": "https://api.cohere.com/compatibility/v1", "key_env": "COHERE_API_KEY", "rpm": 15},
}


@dataclass
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class DiskCache:
    """Content-addressed response cache: identical prompts are never re-sent."""

    def __init__(self, cache_dir: str | Path = ".drift_cache"):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    DEFAULT_MAX_TOKENS = 1024

    @staticmethod
    def key(provider: str, model: str, prompt: str, temperature: float,
            max_tokens: int | None = None) -> str:
        """Content-address a completion request.

        max_tokens participates in the key because it materially changes the
        response: a reasoning model given 32 tokens returns a truncated thought
        trace, and given 512 returns the actual answer. Omitting it meant those
        two requests collided, so raising a token budget silently replayed the
        response generated under the old one -- which is exactly how a fixed
        annotator kept returning the broken output it was supposed to fix.

        It is folded in only when it differs from DEFAULT_MAX_TOKENS, so keys
        for the overwhelming majority of calls (extraction, answering, judging,
        which all use the default) are unchanged and existing caches stay warm.
        """
        payload = [provider, model, prompt, temperature]
        if max_tokens is not None and max_tokens != DiskCache.DEFAULT_MAX_TOKENS:
            payload.append({"max_tokens": max_tokens})
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        if p.exists():
            return json.loads(p.read_text())
        return None

    def put(self, key: str, value: dict) -> None:
        self._path(key).write_text(json.dumps(value))


class RateLimiter:
    """Simple thread-safe requests-per-minute limiter (runs at ~80% of stated limits)."""

    def __init__(self, rpm: int):
        self.min_interval = 60.0 / max(1, rpm)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class BaseProvider:
    name: str = "base"

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 1024) -> Completion:
        raise NotImplementedError


class OpenAICompatProvider(BaseProvider):
    """Minimal OpenAI-compatible chat-completions client (stdlib only)."""

    def __init__(self, preset: str, model: str, cache: DiskCache | None = None, max_retries: int = 4):
        cfg = PROVIDER_PRESETS[preset]
        self.name = preset
        self.model = model
        self.base_url = cfg["base_url"]
        self.api_key = os.environ.get(cfg["key_env"], "")
        if not self.api_key:
            if cfg.get("requires_key", True):
                raise RuntimeError(f"Missing env var {cfg['key_env']} for provider '{preset}'")
            # Local servers (e.g. Ollama) don't check the Authorization header
            # at all; send a harmless placeholder rather than an empty value.
            self.api_key = "not-needed"
        self.cache = cache or DiskCache()
        self.limiter = RateLimiter(cfg["rpm"])
        self.max_retries = max_retries

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 1024) -> Completion:
        ckey = DiskCache.key(self.name, self.model, system + "\n" + prompt, temperature,
                             max_tokens=max_tokens)
        hit = self.cache.get(ckey)
        if hit is not None:
            return Completion(hit["text"], hit["pt"], hit["ct"], cached=True)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps(
            {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        ).encode()

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            self.limiter.wait()
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    # Cloudflare-fronted APIs (Cerebras, Groq) may 403 the
                    # default Python-urllib user agent as a bot.
                    "User-Agent": "drift-memory/0.1 (research; +https://github.com/NandanHemanth/DRIFT)",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                msg = data["choices"][0]["message"]
                # Reasoning models (gpt-oss, GLM, MiniMax) may return empty
                # content when the token budget is consumed by reasoning.
                text = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
                usage = data.get("usage", {})
                pt = usage.get("prompt_tokens", estimate_tokens(system + prompt))
                ct = usage.get("completion_tokens", estimate_tokens(text))
                self.cache.put(ckey, {"text": text, "pt": pt, "ct": ct})
                return Completion(text, pt, ct)
            except Exception as e:  # noqa: BLE001 - retry any transport/429 error with backoff
                last_err = e
                time.sleep(2**attempt * 2)
        raise RuntimeError(f"Provider {self.name} failed after {self.max_retries} retries: {last_err}")


class FallbackProvider(BaseProvider):
    """Tries each provider in order; on failure, falls through to the next.

    A fixed round-robin assignment (one provider per conversation index) has
    no resilience: if that one provider's daily quota is exhausted, every
    cell that touches it fails outright, even though the other providers in
    the list are perfectly healthy. This wraps an ordered list of providers
    so a dead/exhausted one is skipped rather than fatal -- the *first*
    provider in the list is still the "preferred" one (so load-spreading
    behaviour from round-robin ordering is preserved), it just isn't a
    single point of failure anymore.

    Circuit breaker: a provider that just failed is put on a cooldown
    (default 5 minutes, shared across every FallbackProvider instance in the
    process via a class-level dict keyed by provider name) so subsequent
    calls skip straight past it instead of re-paying its full retry/backoff
    cost -- observed in practice as a ~45s tax per call (rate-limiter waits
    plus exponential backoff across OpenAICompatProvider's own retries) on
    every single question, thousands of times over a campaign, when one
    provider's daily quota is already exhausted for the day. If *every*
    provider in the list is on cooldown, they're all tried anyway (paying
    the tax once more is better than hard-failing the call).
    """

    _cooldown_until: dict[str, float] = {}
    COOLDOWN_SECONDS = 300.0

    def __init__(self, providers: list[BaseProvider], cooldown_seconds: float | None = None):
        if not providers:
            raise ValueError("FallbackProvider needs at least one provider")
        self.providers = providers
        self.name = "+".join(p.name for p in providers)
        self.cooldown_seconds = self.COOLDOWN_SECONDS if cooldown_seconds is None else cooldown_seconds

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 1024) -> Completion:
        now = time.monotonic()
        candidates = [p for p in self.providers if FallbackProvider._cooldown_until.get(p.name, 0.0) <= now]
        if not candidates:
            candidates = self.providers  # everyone's on cooldown -- try anyway rather than give up

        last_err: Exception | None = None
        for p in candidates:
            try:
                return p.complete(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
            except Exception as e:  # noqa: BLE001 - fall through to the next provider
                last_err = e
                FallbackProvider._cooldown_until[p.name] = time.monotonic() + self.cooldown_seconds
                continue
        raise RuntimeError(f"All providers failed: {last_err}")


class MockProvider(BaseProvider):
    """Deterministic offline provider for tests and smoke benchmarks.

    Behaviour:
      - extraction prompts  -> returns one triple per input line (JSON list)
      - judge prompts       -> returns CORRECT iff gold answer tokens appear in the answer
      - consolidation       -> returns 'KEEP' for every fact id it is shown
      - QA prompts          -> answers with the highest-overlap memory line
    """

    name = "mock"
    model = "mock-1"

    def __init__(self):
        self.calls = 0

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 1024) -> Completion:
        self.calls += 1
        pt = estimate_tokens(system + prompt)
        if "TASK:EXTRACT" in prompt:
            text = self._extract(prompt)
        elif "TASK:JUDGE" in prompt:
            text = self._judge(prompt)
        elif "TASK:CONSOLIDATE" in prompt:
            text = self._consolidate(prompt)
        else:
            text = self._answer(prompt)
        return Completion(text, pt, estimate_tokens(text))

    @staticmethod
    def _section(prompt: str, header: str) -> str:
        m = re.search(rf"{header}:\n(.*?)(?:\n[A-Z_]+:|\Z)", prompt, re.S)
        return m.group(1).strip() if m else ""

    def _extract(self, prompt: str) -> str:
        text = self._section(prompt, "TEXT")
        triples = []
        for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
            speaker = line.split(":", 1)[0].strip() if ":" in line else "speaker"
            content = line.split(":", 1)[1].strip() if ":" in line else line
            triples.append({"subject": speaker, "predicate": "stated", "object": content, "text": line})
        return json.dumps(triples)

    def _judge(self, prompt: str) -> str:
        gold = self._section(prompt, "GOLD").lower()
        answer = self._section(prompt, "ANSWER").lower()
        gold_tokens = {t for t in re.findall(r"[a-z0-9]+", gold) if len(t) > 2}
        if not gold_tokens:
            return "INCORRECT"
        hit = sum(1 for t in gold_tokens if t in answer)
        return "CORRECT" if hit / len(gold_tokens) >= 0.5 else "INCORRECT"

    def _consolidate(self, prompt: str) -> str:
        ids = re.findall(r"\[fact:(\w+)\]", prompt)
        return json.dumps({"keep": ids, "drop": []})

    def _answer(self, prompt: str) -> str:
        mem = self._section(prompt, "MEMORY")
        question = self._section(prompt, "QUESTION").lower()
        q_tokens = {t for t in re.findall(r"[a-z0-9]+", question) if len(t) > 2}
        best, best_score = "I don't know.", 0
        for line in mem.splitlines():
            l_tokens = {t for t in re.findall(r"[a-z0-9]+", line.lower()) if len(t) > 2}
            score = len(q_tokens & l_tokens)
            if score > best_score:
                best, best_score = line, score
        return best


def make_provider(spec: str, cache_dir: str = ".drift_cache", max_retries: int = 4) -> BaseProvider:
    """spec format: 'mock' or '<preset>:<model>' e.g. 'groq:llama-3.3-70b-versatile'.

    max_retries defaults to 4 (each attempt = one rate-limiter wait + one
    request + exponential backoff sleep). Callers building a FallbackProvider
    chain should pass a smaller value (e.g. 1-2): the chain itself is what
    provides resilience across providers, so each individual provider doesn't
    also need to burn a full retry-and-backoff cycle against a provider
    that's already confirmed dead for the day -- that's what turns a single
    exhausted free-tier quota into a ~45-second tax on every question.
    """
    if spec == "mock":
        return MockProvider()
    preset, model = spec.split(":", 1)
    return OpenAICompatProvider(preset, model, cache=DiskCache(cache_dir), max_retries=max_retries)
