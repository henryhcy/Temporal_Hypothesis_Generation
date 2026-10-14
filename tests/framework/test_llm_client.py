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


# ---------------------------------------------------------------------------
# API backends (Anthropic / OpenAI) -- no network; urlopen is monkeypatched
# ---------------------------------------------------------------------------

from temporal_hypo.framework.extract.llm_client import (  # noqa: E402
    AnthropicClient,
    OpenAIClient,
    client_for,
)


def test_anthropic_client_posts_forced_tool_and_parses_tool_use(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["key"] = req.get_header("X-api-key")
        seen["version"] = req.get_header("Anthropic-version")
        seen["payload"] = json.loads(req.data.decode("utf-8"))
        reply = {"content": [{"type": "tool_use", "name": "structured_output",
                              "input": {"x": 1}}],
                 "usage": {"input_tokens": 10, "output_tokens": 5}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = AnthropicClient("k-test", timeout_s=5.0).complete(MSGS, schema=SCHEMA, model="claude-x")
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["key"] == "k-test" and seen["version"] == "2023-06-01"
    pl = seen["payload"]
    # the system text goes as ONE block marked for prompt caching (a billing
    # hint: the text itself is unchanged, so the reply cannot differ)
    assert pl["system"] == [{"type": "text", "text": "s",
                             "cache_control": {"type": "ephemeral"}}]
    assert pl["messages"] == [{"role": "user", "content": "u"}]
    assert pl["tools"][0]["input_schema"] == SCHEMA
    assert pl["tool_choice"] == {"type": "tool", "name": "structured_output"}
    assert pl["max_tokens"] == 8192  # API_MIN_MAX_TOKENS floor (thinking headroom)
    assert json.loads(out.text) == {"x": 1}
    assert out.prompt_tokens == 10 and out.completion_tokens == 5 and out.cached is False


def test_anthropic_client_counts_cached_prefix_in_prompt_tokens(monkeypatch):
    """Cache hits are reported outside ``input_tokens``; prompt_tokens is the whole prompt."""
    def fake_urlopen(req, timeout=None):
        reply = {"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn",
                 "usage": {"input_tokens": 40, "output_tokens": 5,
                           "cache_read_input_tokens": 3000,
                           "cache_creation_input_tokens": 0}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    client = AnthropicClient("k-test", timeout_s=5.0)
    out = client.complete(MSGS, schema=None, model="claude-x")
    assert out.prompt_tokens == 3040
    assert client.cache_usage == {"uncached": 40, "cache_read": 3000, "cache_write": 0,
                                  "output": 5}


def test_native_schema_drops_length_keywords_but_not_property_names():
    s = {"type": "object", "additionalProperties": False, "required": ["format", "arms"],
         "properties": {"format": {"type": "string", "enum": ["a", "b"], "maxLength": 3},
                        "arms": {"type": "array", "minItems": 1, "maxItems": 2,
                                 "items": {"type": "string", "pattern": "x"}}}}
    out = llm_client._native_schema(s)
    assert out == {"type": "object", "additionalProperties": False, "required": ["format", "arms"],
                   "properties": {"format": {"type": "string", "enum": ["a", "b"]},
                                  "arms": {"type": "array", "items": {"type": "string"}}}}
    assert s["properties"]["arms"]["maxItems"] == 2  # input untouched


def test_anthropic_client_falls_back_to_output_config_when_forced_tool_rejected(monkeypatch):
    """Claude 5.5-era models 400 on tool_choice=tool: same schema via output_config, JSON as text."""
    payloads = []

    def fake_urlopen(req, timeout=None):
        pl = json.loads(req.data.decode("utf-8"))
        payloads.append(pl)
        if "tool_choice" in pl:
            raise llm_client.urllib.error.HTTPError(
                req.full_url, 400, "Bad Request", {},
                io.BytesIO(b'{"type":"error","error":{"type":"invalid_request_error",'
                           b'"message":"tool_choice: type \\"tool\\" and \\"any\\" are not '
                           b'supported for this model."}}'))
        reply = {"content": [{"type": "text", "text": '{"x": 7}'}], "stop_reason": "end_turn",
                 "usage": {"input_tokens": 10, "output_tokens": 3}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    client = AnthropicClient("k-test", timeout_s=5.0)
    out = client.complete(MSGS, schema=SCHEMA, model="claude-new")
    assert json.loads(out.text) == {"x": 7}
    assert len(payloads) == 2
    assert "tools" not in payloads[1] and "tool_choice" not in payloads[1]
    assert payloads[1]["output_config"] == {"format": {"type": "json_schema", "schema": llm_client._native_schema(SCHEMA)}}
    # the rejection is remembered: the next call goes straight to output_config
    client.complete([{"role": "user", "content": "again"}], schema=SCHEMA, model="claude-new")
    assert len(payloads) == 3 and "output_config" in payloads[2]


def test_anthropic_client_returns_text_blocks_without_schema(monkeypatch):
    def fake_urlopen(req, timeout=None):
        pl = json.loads(req.data.decode("utf-8"))
        assert "tools" not in pl and "tool_choice" not in pl
        reply = {"content": [{"type": "text", "text": '{"y": 2}'}], "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = AnthropicClient("k").complete(MSGS, schema=None, model="claude-x")
    assert out.text == '{"y": 2}'


def test_openai_client_posts_json_schema_and_parses_content(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        seen["payload"] = json.loads(req.data.decode("utf-8"))
        reply = {"choices": [{"message": {"content": '{"x": 3}'}}],
                 "usage": {"prompt_tokens": 9, "completion_tokens": 4}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = OpenAIClient("sk-test").complete(MSGS, schema=SCHEMA, model="gpt-x")
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    pl = seen["payload"]
    assert pl["response_format"]["type"] == "json_schema"
    assert pl["response_format"]["json_schema"]["schema"] == SCHEMA
    assert pl["response_format"]["json_schema"]["strict"] is False
    assert pl["max_completion_tokens"] == 8192 and pl["temperature"] == 0.0  # floored
    assert out.text == '{"x": 3}' and out.prompt_tokens == 9


def test_openai_client_drops_rejected_temperature(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        pl = json.loads(req.data.decode("utf-8"))
        calls.append(pl)
        if "temperature" in pl:
            raise urllib.error.HTTPError(
                req.full_url, 400, "bad", None,
                io.BytesIO(b'{"error": {"message": "Unsupported parameter: temperature"}}'))
        reply = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = OpenAIClient("sk").complete(MSGS, schema=None, model="o-x")
    assert len(calls) == 2 and "temperature" not in calls[1]
    assert out.text == "ok"


def test_api_retry_on_429_then_success(monkeypatch):
    events = []
    monkeypatch.setattr(llm_client, "_sleep", lambda s: events.append(("slept", s)))

    def fake_urlopen(req, timeout=None):
        events.append("call")
        if events.count("call") == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "rate", None,
                                         io.BytesIO(b"slow down"))
        reply = {"content": [{"type": "text", "text": "hi"}], "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = AnthropicClient("k").complete(MSGS, schema=None, model="claude-x")
    assert out.text == "hi" and events.count("call") == 2 and ("slept", 1.0) in events


def test_api_400_is_not_retried(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 400, "bad", None,
                                     io.BytesIO(b'{"error": {"message": "bad schema"}}'))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="HTTP 400"):
        AnthropicClient("k").complete(MSGS, schema=None, model="claude-x")
    assert len(calls) == 1


def test_api_client_uses_the_disk_cache(monkeypatch, tmp_path):
    n = {"calls": 0}

    def fake_urlopen(req, timeout=None):
        n["calls"] += 1
        reply = {"choices": [{"message": {"content": '{"x": 1}'}}], "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    c = OpenAIClient("sk", cache=CacheDir(tmp_path / "c"))
    a = c.complete(MSGS, schema=SCHEMA, model="gpt-x")
    b = c.complete(MSGS, schema=SCHEMA, model="gpt-x")
    assert n["calls"] == 1 and a.cached is False and b.cached is True and b.text == a.text


def test_client_for_builds_each_backend():
    assert isinstance(client_for("ollama"), OllamaClient)
    assert isinstance(client_for("anthropic", api_key="k"), AnthropicClient)
    assert isinstance(client_for("openai", api_key="k"), OpenAIClient)
    with pytest.raises(ProviderError, match="unknown provider"):
        client_for("azure")
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        client_for("anthropic")  # missing key fails fast, not at first call


def test_anthropic_client_drops_rejected_temperature(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        pl = json.loads(req.data.decode("utf-8"))
        calls.append(pl)
        if "temperature" in pl:
            raise urllib.error.HTTPError(
                req.full_url, 400, "bad", None,
                io.BytesIO(b'{"error": {"message": "temperature is not supported"}}'))
        reply = {"content": [{"type": "text", "text": "ok"}],
                 "stop_reason": "end_turn", "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    out = AnthropicClient("k").complete(MSGS, schema=None, model="claude-x")
    assert len(calls) == 2 and "temperature" not in calls[1] and out.text == "ok"


def _no_cache_files(root):
    return not root.exists() or not list(root.glob("*.json"))


def test_anthropic_truncated_reply_raises_and_is_not_cached(monkeypatch, tmp_path):
    def fake_urlopen(req, timeout=None):
        reply = {"content": [{"type": "text", "text": "partial"}],
                 "stop_reason": "max_tokens", "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    cache = CacheDir(tmp_path / "c")
    with pytest.raises(ProviderError, match="max_tokens"):
        AnthropicClient("k", cache=cache).complete(MSGS, schema=None, model="claude-x")
    assert _no_cache_files(tmp_path / "c")


def test_openai_truncated_reply_raises_and_is_not_cached(monkeypatch, tmp_path):
    def fake_urlopen(req, timeout=None):
        reply = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                 "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    cache = CacheDir(tmp_path / "c")
    with pytest.raises(ProviderError, match="length"):
        OpenAIClient("sk", cache=cache).complete(MSGS, schema=SCHEMA, model="gpt-x")
    assert _no_cache_files(tmp_path / "c")


def test_openai_fallback_meta_records_what_was_sent(monkeypatch, tmp_path):
    def fake_urlopen(req, timeout=None):
        pl = json.loads(req.data.decode("utf-8"))
        if "temperature" in pl:
            raise urllib.error.HTTPError(
                req.full_url, 400, "bad", None,
                io.BytesIO(b'{"error": {"message": "Unsupported parameter: temperature"}}'))
        reply = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                 "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    cache = CacheDir(tmp_path / "c")
    OpenAIClient("sk", cache=cache).complete(MSGS, schema=None, model="o-x")
    f = next((tmp_path / "c").glob("*.json"))
    meta = json.loads(f.read_text(encoding="utf-8"))["meta"]
    assert meta["temperature"] is None and meta["max_tokens"] == 8192


def test_temperature_rejection_is_remembered_per_model(monkeypatch):
    posts = []

    def fake_urlopen(req, timeout=None):
        pl = json.loads(req.data.decode("utf-8"))
        posts.append(pl)
        if "temperature" in pl:
            raise urllib.error.HTTPError(
                req.full_url, 400, "bad", None,
                io.BytesIO(b'{"error": {"message": "temperature is not supported"}}'))
        reply = {"content": [{"type": "text", "text": "ok"}],
                 "stop_reason": "end_turn", "usage": {}}
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    c = AnthropicClient("k")
    c.complete(MSGS, schema=None, model="claude-x")
    c.complete([{"role": "user", "content": "different"}], schema=None, model="claude-x")
    # first call pays the 400 + retry; the second drops temperature up front
    assert len(posts) == 3
    assert "temperature" in posts[0] and "temperature" not in posts[1]
    assert "temperature" not in posts[2]
