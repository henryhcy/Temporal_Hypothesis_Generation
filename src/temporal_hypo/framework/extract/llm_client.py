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
# API backends (Anthropic / OpenAI) -- decisions.md 2026-09-02: the S2
# text-to-SQL stage runs on frontier API models. Same ``Provider`` interface,
# same disk cache, still stdlib-only (the ``llm`` extra stays optional).
# ---------------------------------------------------------------------------

DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com"
DEFAULT_OPENAI_URL = "https://api.openai.com"
_ANTHROPIC_VERSION = "2023-06-01"
_STRUCTURED_TOOL = "structured_output"
_RETRYABLE_HTTP = (429, 500, 502, 503, 529)
API_MIN_MAX_TOKENS = 8192  # API models spend thinking/reasoning tokens from the
# same cap the Provider contract sized for visible output (Ollama num_predict);
# the adapters floor the budget so adaptive thinking cannot starve the reply.
_sleep = time.sleep  # module-level so tests can monkeypatch the backoff away


def _rejected_param(exc: Exception, payload: Mapping[str, Any], param: str) -> bool:
    """True iff ``exc`` is an HTTP 400 naming ``param`` and the request sent it."""
    s = str(exc)
    return param in payload and "HTTP 400" in s and param in s


def _post_json(url: str, payload: Mapping[str, Any], headers: Mapping[str, str], *,
               timeout_s: float, provider: str, retries: int = 3) -> dict:
    """POST JSON; exponential backoff on transient codes; ``ProviderError`` otherwise."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Accept": "application/json", **headers}
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, method="POST", headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:  # pragma: no cover - best effort only
                pass
            if exc.code in _RETRYABLE_HTTP and attempt < retries:
                _sleep(2.0 ** attempt)
                continue
            raise ProviderError(f"{provider} answered HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError,
                ConnectionError, OSError) as exc:
            if attempt < retries:
                _sleep(2.0 ** attempt)
                continue
            raise ProviderError(f"{provider} unreachable at {url} ({exc})") from exc
        try:
            return json.loads(body)
        except ValueError as exc:
            raise ProviderError(f"{provider} at {url} returned non-JSON: {body[:200]!r}") from exc
    raise ProviderError(f"{provider}: retries exhausted")  # pragma: no cover


class AnthropicClient:
    """``Provider`` over ``POST {base_url}/v1/messages`` (stdlib urllib).

    Structured output is a FORCED TOOL CALL: with a ``schema`` the request
    carries one tool whose ``input_schema`` IS the schema, plus
    ``tool_choice={"type": "tool", ...}``; the reply's ``tool_use.input`` is
    re-serialised as the completion text so callers parse the same JSON text
    every backend returns. Without a schema, text blocks are concatenated.
    """

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_ANTHROPIC_URL,
                 cache: CacheDir | None = None, timeout_s: float = 120.0,
                 min_max_tokens: int = API_MIN_MAX_TOKENS) -> None:
        if not api_key:
            raise ProviderError("AnthropicClient needs an api_key (set ANTHROPIC_API_KEY)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.cache = cache
        self.timeout_s = float(timeout_s)
        self.min_max_tokens = int(min_max_tokens)

    def complete(self, messages: list[dict], *, schema: dict | None, model: str,
                 temperature: float = 0.0, max_tokens: int = 800) -> Completion:
        key = None
        if self.cache is not None:
            key = self.cache.key(model, messages, schema)
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
        chat = [m for m in messages if m.get("role") != "system"]
        payload: dict[str, Any] = {"model": model,
                                   "max_tokens": max(int(max_tokens), self.min_max_tokens),
                                   "messages": chat, "temperature": float(temperature)}
        if system:
            payload["system"] = system
        if schema is not None:
            payload["tools"] = [{"name": _STRUCTURED_TOOL,
                                 "description": "Return the structured output.",
                                 "input_schema": schema}]
            payload["tool_choice"] = {"type": "tool", "name": _STRUCTURED_TOOL}
        url = f"{self.base_url}/v1/messages"
        hdrs = {"x-api-key": self.api_key, "anthropic-version": _ANTHROPIC_VERSION}
        t0 = time.perf_counter()
        try:
            d = _post_json(url, payload, hdrs, timeout_s=self.timeout_s, provider="Anthropic")
        except ProviderError as exc:
            # current Claude models reject sampling params outright (HTTP 400)
            if _rejected_param(exc, payload, "temperature"):
                payload.pop("temperature")
                d = _post_json(url, payload, hdrs, timeout_s=self.timeout_s,
                               provider="Anthropic")
            else:
                raise
        ms = (time.perf_counter() - t0) * 1000.0
        stop = d.get("stop_reason")
        if stop == "max_tokens":
            raise ProviderError(
                f"Anthropic reply truncated (stop_reason max_tokens at "
                f"{payload['max_tokens']}); raise the stage's max_tokens budget")
        if stop == "refusal":
            raise ProviderError(f"Anthropic refused the request: {str(d)[:200]!r}")
        blocks = d.get("content") or []
        tool = next((b for b in blocks if b.get("type") == "tool_use"), None)
        if schema is not None and tool is not None:
            text = json.dumps(tool.get("input") or {}, ensure_ascii=False)
        else:
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text:
            raise ProviderError(f"Anthropic reply has no usable content: {str(d)[:200]!r}")
        usage = d.get("usage") or {}
        out = Completion(text=text, prompt_tokens=usage.get("input_tokens"),
                         completion_tokens=usage.get("output_tokens"), ms=ms, cached=False)
        if self.cache is not None and key is not None:
            self.cache.put(key, out, meta={"model": model, "provider": "anthropic",
                                           "temperature": payload.get("temperature"),
                                           "max_tokens": payload["max_tokens"]})
        return out


class OpenAIClient:
    """``Provider`` over ``POST {base_url}/v1/chat/completions``.

    With a ``schema`` the request asks for ``response_format=json_schema``
    (non-strict -- ``llm.py``/``llm_sql.py`` already validate and run one repair
    retry). Models that reject a pinned ``temperature`` (the reasoning family)
    get ONE retry without it, so the flag works across model generations.
    """

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_OPENAI_URL,
                 cache: CacheDir | None = None, timeout_s: float = 120.0,
                 min_max_tokens: int = API_MIN_MAX_TOKENS) -> None:
        if not api_key:
            raise ProviderError("OpenAIClient needs an api_key (set OPENAI_API_KEY)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.cache = cache
        self.timeout_s = float(timeout_s)
        self.min_max_tokens = int(min_max_tokens)

    def complete(self, messages: list[dict], *, schema: dict | None, model: str,
                 temperature: float = 0.0, max_tokens: int = 800) -> Completion:
        key = None
        if self.cache is not None:
            key = self.cache.key(model, messages, schema)
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        payload: dict[str, Any] = {"model": model, "messages": list(messages),
                                   "max_completion_tokens": max(int(max_tokens),
                                                                self.min_max_tokens),
                                   "temperature": float(temperature)}
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": _STRUCTURED_TOOL, "schema": schema, "strict": False},
            }
        url = f"{self.base_url}/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {self.api_key}"}
        t0 = time.perf_counter()
        try:
            d = _post_json(url, payload, hdrs, timeout_s=self.timeout_s, provider="OpenAI")
        except ProviderError as exc:
            if _rejected_param(exc, payload, "temperature"):
                payload.pop("temperature")
                d = _post_json(url, payload, hdrs, timeout_s=self.timeout_s, provider="OpenAI")
            else:
                raise
        ms = (time.perf_counter() - t0) * 1000.0
        choice = (d.get("choices") or [{}])[0]
        fr = choice.get("finish_reason")
        if fr == "length":
            raise ProviderError(
                f"OpenAI reply truncated (finish_reason length at "
                f"{payload['max_completion_tokens']}); raise the stage's max_tokens budget")
        if fr == "content_filter":
            raise ProviderError(f"OpenAI content filter blocked the reply: {str(d)[:200]!r}")
        text = (choice.get("message") or {}).get("content")
        if not isinstance(text, str) or not text:
            raise ProviderError(f"OpenAI reply has no message content: {str(d)[:200]!r}")
        usage = d.get("usage") or {}
        out = Completion(text=text, prompt_tokens=usage.get("prompt_tokens"),
                         completion_tokens=usage.get("completion_tokens"), ms=ms, cached=False)
        if self.cache is not None and key is not None:
            self.cache.put(key, out, meta={"model": model, "provider": "openai",
                                           "temperature": payload.get("temperature"),
                                           "max_tokens": payload["max_completion_tokens"]})
        return out


PROVIDERS = ("ollama", "anthropic", "openai")


def client_for(provider: str, *, api_key: str | None = None, base_url: str | None = None,
               cache: CacheDir | None = None, timeout_s: float = 120.0,
               num_ctx: int | None = None, keep_alive: str | int | None = None) -> Provider:
    """Construct the backend for ``provider`` behind the one ``Provider`` interface."""
    if provider == "ollama":
        return OllamaClient(base_url or DEFAULT_OLLAMA_URL, cache=cache, timeout_s=timeout_s,
                            num_ctx=num_ctx, keep_alive=keep_alive)
    if provider == "anthropic":
        return AnthropicClient(api_key or "", base_url=base_url or DEFAULT_ANTHROPIC_URL,
                               cache=cache, timeout_s=timeout_s)
    if provider == "openai":
        return OpenAIClient(api_key or "", base_url=base_url or DEFAULT_OPENAI_URL,
                            cache=cache, timeout_s=timeout_s)
    raise ProviderError(f"unknown provider {provider!r}; expected one of {PROVIDERS}")


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
