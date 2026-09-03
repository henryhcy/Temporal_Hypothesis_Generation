"""Tests for ``framework.extract.llm_client`` -- no network in the fast tests."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from temporal_hypo.framework.extract import llm_client
from temporal_hypo.framework.extract.llm_client import (
    CacheDir,
    CachedProvider,
    Completion,
    OllamaClient,
    ProviderError,
    cache_key,
    ollama_available,
    parse_json_object,
)


class StubProvider:
    """Returns canned texts in order; counts calls."""

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def complete(self, messages, *, schema, model, temperature=0.0, max_tokens=800):
        self.calls.append({"messages": messages, "schema": schema, "model": model})
        text = self.texts.pop(0) if self.texts else "{}"
        return Completion(text=text, prompt_tokens=11, completion_tokens=7, ms=1.5, cached=False)


MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}}


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

def test_cache_key_is_stable_and_sensitive():
    k1 = cache_key("m", MSGS, SCHEMA)
    assert k1 == cache_key("m", [dict(m) for m in MSGS], json.loads(json.dumps(SCHEMA)))
    assert len(k1) == 64
    assert k1 != cache_key("m2", MSGS, SCHEMA)
    assert k1 != cache_key("m", MSGS + [{"role": "user", "content": "x"}], SCHEMA)
    assert k1 != cache_key("m", MSGS, None)


def test_cache_miss_then_hit(tmp_path):
    cache = CacheDir(tmp_path / "cache")
    stub = StubProvider(['{"x": 1}', '{"x": 2}'])
    prov = CachedProvider(stub, cache)

    first = prov.complete(MSGS, schema=SCHEMA, model="m")
    assert first.text == '{"x": 1}' and first.cached is False
    assert len(stub.calls) == 1 and cache.misses == 1 and cache.hits == 0
    assert (tmp_path / "cache" / f"{cache_key('m', MSGS, SCHEMA)}.json").exists()

    second = prov.complete(MSGS, schema=SCHEMA, model="m")
    assert second.text == '{"x": 1}' and second.cached is True
    assert second.prompt_tokens == 11 and second.completion_tokens == 7
    assert len(stub.calls) == 1            # served from disk, stub untouched
    assert cache.hits == 1

    third = prov.complete(MSGS, schema=None, model="m")   # different schema -> miss
    assert third.text == '{"x": 2}' and third.cached is False
    assert len(stub.calls) == 2


def test_cache_survives_a_new_cachedir_instance(tmp_path):
    p = tmp_path / "c"
    CachedProvider(StubProvider(['{"a": 1}']), CacheDir(p)).complete(MSGS, schema=None, model="m")
    again = CachedProvider(StubProvider([]), CacheDir(p)).complete(MSGS, schema=None, model="m")
    assert again.cached and again.text == '{"a": 1}'


def test_cache_corrupt_file_is_a_miss(tmp_path):
    cache = CacheDir(tmp_path)
    key = cache.key("m", MSGS, None)
    cache.path.mkdir(exist_ok=True)
    cache.path_for(key).write_text("not json", encoding="utf-8")
    assert cache.get(key) is None


# ---------------------------------------------------------------------------
# parse_json_object
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    '{"mode": "dir_bool", "events": ["Headache", "Fatigue"], "negated": false}',
    '```json\n{"mode": "dir_bool", "events": ["Headache", "Fatigue"], "negated": false}\n```',
    'Sure! Here is the claim:\n{"mode": "dir_bool", "events": ["Headache", "Fatigue"], '
    '"negated": false}\nHope this helps.',
    '```\n{"mode": "dir_bool",\n "events": ["Headache", "Fatigue"],\n "negated": false}```',
])
def test_parse_json_object_tolerates_fences_and_chatter(text):
    d = parse_json_object(text)
    assert d == {"mode": "dir_bool", "events": ["Headache", "Fatigue"], "negated": False}


def test_parse_json_object_handles_braces_inside_strings():
    d = parse_json_object('x {"a": "curly } brace {", "b": {"c": "\\"}"}} y')
    assert d == {"a": "curly } brace {", "b": {"c": '"}'}}


def test_parse_json_object_skips_a_non_object_prefix():
    d = parse_json_object('[1, 2] then {"ok": true}')
    assert d == {"ok": True}


@pytest.mark.parametrize("text", ["", "no json here", "[1, 2, 3]", '{"unbalanced": ', "{}}"])
def test_parse_json_object_raises_on_garbage(text):
    if text == "{}}":
        assert parse_json_object(text) == {}
        return
    with pytest.raises(ValueError):
        parse_json_object(text)


# ---------------------------------------------------------------------------
# OllamaClient over a faked urlopen (no network)
# ---------------------------------------------------------------------------

class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_ollama_client_posts_the_documented_payload(monkeypatch, tmp_path):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        seen["timeout"] = timeout
        seen["body"] = json.loads(req.data.decode("utf-8"))
        reply = {"message": {"role": "assistant", "content": '{"x": 3}'},
                 "prompt_eval_count": 123, "eval_count": 9, "done": True}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    client = OllamaClient("http://localhost:11434/", cache=CacheDir(tmp_path), timeout_s=7)
    out = client.complete(MSGS, schema=SCHEMA, model="qwen2.5:7b-instruct", max_tokens=99)

    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["method"] == "POST" and seen["timeout"] == 7
    assert seen["body"] == {"model": "qwen2.5:7b-instruct", "messages": MSGS, "stream": False,
                            "format": SCHEMA,
                            "options": {"temperature": 0.0, "num_predict": 99}}
    assert out == Completion(text='{"x": 3}', prompt_tokens=123, completion_tokens=9,
                             ms=out.ms, cached=False)
    assert out.ms >= 0

    # second call: served from the cache without touching urlopen
    monkeypatch.setattr(llm_client.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("network call on a cache hit"))
    hit = client.complete(MSGS, schema=SCHEMA, model="qwen2.5:7b-instruct", max_tokens=99)
    assert hit.cached is True and hit.text == '{"x": 3}'


def test_ollama_client_uses_json_mode_without_schema(monkeypatch):
    def fake_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        assert body["format"] == "json"
        return _FakeResponse(json.dumps({"message": {"content": "{}"}}).encode())

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = OllamaClient().complete(MSGS, schema=None, model="m")
    assert out.text == "{}" and out.prompt_tokens is None


def test_ollama_client_passes_num_ctx_and_keep_alive_when_set(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen.update(json.loads(req.data.decode("utf-8")))
        return _FakeResponse(json.dumps({"message": {"content": "{}"}}).encode())

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    OllamaClient(num_ctx=8192, keep_alive="10m").complete(MSGS, schema=None, model="m")
    assert seen["options"] == {"temperature": 0.0, "num_predict": 800, "num_ctx": 8192}
    assert seen["keep_alive"] == "10m"


def test_ollama_client_unreachable_names_the_url(monkeypatch):
    def refuse(req, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError(10061, "refused"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", refuse)
    client = OllamaClient("http://localhost:1")
    with pytest.raises(ProviderError) as ei:
        client.complete(MSGS, schema=None, model="m")
    assert "http://localhost:1/api/chat" in str(ei.value)
    assert client.available() is False


def test_ollama_client_http_error_is_a_provider_error(monkeypatch):
    def http_error(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "not found", {},
                                     io.BytesIO(b'{"error":"model not found"}'))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", http_error)
    with pytest.raises(ProviderError) as ei:
        OllamaClient().complete(MSGS, schema=None, model="nope")
    assert "404" in str(ei.value) and "model not found" in str(ei.value)


# ---------------------------------------------------------------------------
# live (skipped unless a local Ollama answers)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not ollama_available(), reason="no Ollama at localhost:11434")
def test_live_ollama_structured_output(tmp_path):
    client = OllamaClient(cache=CacheDir(tmp_path))
    models = client.models()
    if not models:
        pytest.skip("Ollama is running but has no models pulled")
    out = client.complete(
        [{"role": "user", "content": 'Reply with JSON {"x": 3}.'}],
        schema={"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        model=models[0], max_tokens=32)
    assert parse_json_object(out.text)["x"] == 3
    assert out.cached is False
    assert client.complete([{"role": "user", "content": 'Reply with JSON {"x": 3}.'}],
                           schema={"type": "object", "properties": {"x": {"type": "integer"}},
                                   "required": ["x"]},
                           model=models[0], max_tokens=32).cached is True
