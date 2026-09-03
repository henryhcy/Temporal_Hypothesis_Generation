"""Model-provider client for the LLM stages (S1 prompted extraction, S2 text-to-SQL).

WHAT: one tiny ``Provider`` interface -- ``complete(messages, schema=, model=)``
-> ``Completion`` -- with a local Ollama backend over stdlib ``urllib`` and a
content-addressed disk cache. WHY: the harness must run on a local GPU with no
API keys and no new Python dependencies (plan 11 §3), every call must be
reproducible (temperature 0 + cache keyed on the exact prompt), and the
OpenAI/Anthropic adapters that come later must drop in behind the same interface
without touching ``llm.py`` / ``llm_sql.py``.

Ollama's native ``/api/chat`` is used rather than the OpenAI-compatible route
because it accepts a JSON *schema* as ``format`` (constrained decoding), which is
what makes the flat claim schema and the ``{"arms": [...]}`` shape reliable on a
7B model. The cache stores the whole ``Completion`` as JSON under
``results/cache/<sha256>.json``; a hit returns it with ``cached=True`` and costs
no tokens, so re-running an evaluation only pays for new prompts.
"""

from __future__ import annotations

import hashlib
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CACHE_DIR = _REPO_ROOT / "results" / "cache"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


# ---------------------------------------------------------------------------
# the interface
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Completion:
    """One model reply. ``cached`` marks a disk-cache hit (no tokens were spent)."""

    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    ms: float
    cached: bool


class Provider(Protocol):
    """Anything that turns a chat transcript into a ``Completion``."""

    def complete(self, messages: list[dict], *, schema: dict | None, model: str,
                 temperature: float = 0.0, max_tokens: int = 800) -> Completion: ...


class ProviderError(RuntimeError):
    """The backend could not be reached or returned an unusable reply."""


# ---------------------------------------------------------------------------
# disk cache
# ---------------------------------------------------------------------------

def cache_key(model: str, messages: Sequence[Mapping[str, Any]],
              schema: Mapping[str, Any] | None) -> str:
    """sha256 over the canonical JSON of (model, messages, schema)."""
    payload = json.dumps({"model": model, "messages": list(messages), "schema": schema},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CacheDir:
    """Content-addressed store of ``Completion`` objects, one JSON file per key."""

    def __init__(self, path: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.path = Path(path)
        self.hits = 0
        self.misses = 0

    def key(self, model: str, messages: Sequence[Mapping[str, Any]],
            schema: Mapping[str, Any] | None) -> str:
        return cache_key(model, messages, schema)

    def path_for(self, key: str) -> Path:
        return self.path / f"{key}.json"

    def get(self, key: str) -> Completion | None:
        """The stored completion (with ``cached=True``) or None on a miss."""
        p = self.path_for(key)
        if not p.exists():
            self.misses += 1
            return None
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            c = Completion(text=d["text"], prompt_tokens=d.get("prompt_tokens"),
                           completion_tokens=d.get("completion_tokens"),
                           ms=float(d.get("ms", 0.0)), cached=True)
        except (OSError, ValueError, KeyError):
            # a torn or hand-edited file is a miss, not a crash
            self.misses += 1
            return None
        self.hits += 1
        return c

    def put(self, key: str, completion: Completion, *,
            meta: Mapping[str, Any] | None = None) -> Path:
        """Store ``completion`` (always with ``cached=False`` on disk)."""
        self.path.mkdir(parents=True, exist_ok=True)
        p = self.path_for(key)
        d = asdict(completion)
        d["cached"] = False
        if meta:
            d["meta"] = dict(meta)
        tmp = p.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        tmp.replace(p)
        return p


class CachedProvider:
    """Wrap any ``Provider`` with a ``CacheDir``; hits are returned without a call."""

    def __init__(self, provider: Provider, cache: CacheDir) -> None:
        self.provider = provider
        self.cache = cache

    def complete(self, messages: list[dict], *, schema: dict | None, model: str,
                 temperature: float = 0.0, max_tokens: int = 800) -> Completion:
        key = self.cache.key(model, messages, schema)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        out = self.provider.complete(messages, schema=schema, model=model,
                                     temperature=temperature, max_tokens=max_tokens)
        self.cache.put(key, out, meta={"model": model, "temperature": temperature,
                                       "max_tokens": max_tokens})
        return out


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

class OllamaClient:
    """``Provider`` over Ollama's native ``POST {base_url}/api/chat``.

    Request: ``{"model", "messages", "stream": false, "format": <schema | "json">,
    "options": {"temperature", "num_predict"}}``. Reply fields used:
    ``message.content``, ``prompt_eval_count``, ``eval_count``. With a ``cache``
    the client behaves like ``CachedProvider`` around itself.
    """

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, *,
                 cache: CacheDir | None = None, timeout_s: float = 120.0,
                 num_ctx: int | None = None, keep_alive: str | int | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache = cache
        self.timeout_s = float(timeout_s)
        # context window; Ollama's default (a few thousand tokens) truncates the
        # catalogue + few-shot prompt silently, so runs should set it explicitly
        self.num_ctx = int(num_ctx) if num_ctx is not None else None
        self.keep_alive = keep_alive

    # -- transport -----------------------------------------------------------

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None,
                 timeout_s: float | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s or self.timeout_s) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:  # pragma: no cover - best effort only
                pass
            raise ProviderError(f"Ollama at {url} answered HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError,
                ConnectionError, OSError) as exc:
            raise ProviderError(
                f"Ollama server unreachable at {url} ({exc}). Is `ollama serve` running?"
            ) from exc
        try:
            return json.loads(body)
        except ValueError as exc:
            raise ProviderError(f"Ollama at {url} returned non-JSON: {body[:200]!r}") from exc

    def available(self, timeout_s: float = 1.0) -> bool:
        """True iff ``GET /api/tags`` answers."""
        try:
            self._request("GET", "/api/tags", None, timeout_s=timeout_s)
            return True
        except ProviderError:
            return False

    def models(self) -> list[str]:
        """Names of the models the server has pulled."""
        d = self._request("GET", "/api/tags", None)
        return [m.get("name", "") for m in d.get("models", []) if m.get("name")]

    # -- the interface -------------------------------------------------------

    def complete(self, messages: list[dict], *, schema: dict | None, model: str,
                 temperature: float = 0.0, max_tokens: int = 800) -> Completion:
        key = None
        if self.cache is not None:
            key = self.cache.key(model, messages, schema)
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "stream": False,
            "format": schema if schema is not None else "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if self.num_ctx is not None:
            payload["options"]["num_ctx"] = self.num_ctx
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        t0 = time.perf_counter()
        d = self._request("POST", "/api/chat", payload)
        ms = (time.perf_counter() - t0) * 1000.0
        msg = d.get("message") or {}
        text = msg.get("content")
        if not isinstance(text, str):
            raise ProviderError(f"Ollama reply has no message.content: {str(d)[:200]!r}")
        out = Completion(text=text, prompt_tokens=d.get("prompt_eval_count"),
                         completion_tokens=d.get("eval_count"), ms=ms, cached=False)
        if self.cache is not None and key is not None:
            self.cache.put(key, out, meta={"model": model, "temperature": temperature,
                                           "max_tokens": max_tokens})
        return out


def ollama_available(base_url: str = DEFAULT_OLLAMA_URL, timeout_s: float = 0.5) -> bool:
    """Cheap liveness probe used to gate the live tests (never raises)."""
    try:
        return OllamaClient(base_url, timeout_s=timeout_s).available(timeout_s)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# reply parsing
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    """Remove ```lang ... ``` fences anywhere in the text (keep their content)."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            continue
        out.append(line)
    return "\n".join(out)


def _balanced_object(text: str, start: int) -> str | None:
    """The ``{...}`` substring starting at ``start`` with balanced braces, honouring strings."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_json_object(text: str) -> dict:
    """The first JSON object in a model reply, tolerant of fences and chatter.

    Raises ``ValueError`` when no balanced ``{...}`` parses to a dict -- the
    caller turns that into a repair retry.
    """
    if not isinstance(text, str):
        raise ValueError(f"expected str, got {type(text).__name__}")
    body = _strip_fences(text)
    pos = body.find("{")
    last_err: Exception | None = None
    while pos != -1:
        cand = _balanced_object(body, pos)
        if cand is None:
            break
        try:
            obj = json.loads(cand)
        except ValueError as exc:
            last_err = exc
        else:
            if isinstance(obj, dict):
                return obj
            last_err = ValueError(f"JSON value is {type(obj).__name__}, not an object")
        pos = body.find("{", pos + 1)
    raise ValueError(f"no JSON object in reply ({last_err}): {text[:200]!r}")
