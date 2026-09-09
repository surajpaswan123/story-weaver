import io
import json
from pathlib import Path

import httpx
import pytest
from anthropic import Anthropic
from fastapi.testclient import TestClient

import main
from openai_compat import MessagesClient, MessagesTextStream, OpenCodeClient, resolve_openai_endpoint
from test_responses import configured_user
from test_model_discovery import catalog_api, save_connection


MODEL = "provider-story-model"
TEXT = "The lantern glowed beside the quiet river."
MESSAGES = [{"role": "system", "content": "Keep the full manuscript."},
            {"role": "user", "content": "Continue the story."}]


def message_body(text=TEXT, **overrides):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": MODEL,
            "content": [{"type": "thinking", "thinking": "Planning", "signature": "sig"},
                        {"type": "text", "text": text}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 12, "output_tokens": 20}, **overrides}


def message_events(text=TEXT, reason="end_turn"):
    return [
        {"type": "message_start", "message": message_body(content=[], stop_reason=None)},
        {"type": "ping"},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Planning"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": text[:4]}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": text[4:]}},
        {"type": "content_block_stop", "index": 1},
        {"type": "message_delta", "delta": {"stop_reason": reason, "stop_sequence": None}, "usage": {"output_tokens": 20}},
        {"type": "message_stop"},
    ]


@pytest.fixture
def messages_sdk(monkeypatch):
    clients, requests, responses = [], [], []
    monkeypatch.setattr(main, "_MESSAGES_MODEL_LIMITS", {})

    def make(*, events=None, body=None, status=200, base="https://example.com/gateway/v1"):
        def handle(request):
            requests.append(request)
            if events is None:
                response = httpx.Response(status, json=body if body is not None else message_body())
            else:
                data = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
                response = httpx.Response(status, text=data, headers={"content-type": "text/event-stream"})
            responses.append(response)
            return response
        sdk = Anthropic(api_key="test-key", base_url=base, max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        clients.append(sdk)
        return sdk, requests, responses

    yield make
    for sdk in clients:
        sdk.close()


@pytest.mark.parametrize("url,mode,base", [
    ("https://example.com/v1/messages/", "auto", "https://example.com/v1"),
    ("https://example.com/gateway/v1/messages", "auto", "https://example.com/gateway/v1"),
    ("https://example.com/api/messages", "auto", "https://example.com/api"),
    ("https://example.com/v1", "messages", "https://example.com/v1"),
    ("https://api.anthropic.com/v1", "auto", "https://api.anthropic.com/v1"),
])
def test_messages_endpoint_resolution(url, mode, base):
    assert resolve_openai_endpoint(url, mode) == (base, "messages")


def test_messages_wire_format_preserves_system_and_history(messages_sdk):
    sdk, requests, _ = messages_sdk()
    messages = MESSAGES[:1] + [{"role": "developer", "content": "Keep names."}] + MESSAGES[1:] + [
        {"role": "user", "content": [{"type": "text", "text": "Feedback: slower pacing."}]},
        {"role": "assistant", "content": "Earlier story text."}, {"role": "user", "content": "Continue."},
    ]
    result = MessagesClient(sdk).chat.completions.create(
        model=MODEL, messages=messages, temperature=1, top_p=0.9,
        reasoning_effort="xhigh", max_completion_tokens=131072, stop="THE END")
    assert result.choices[0].message.content == TEXT
    request = requests[0]
    assert request.url.path == "/gateway/v1/messages"
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in request.headers
    body = json.loads(request.content)
    assert body["system"] == [{"type": "text", "text": "Keep the full manuscript."}, {"type": "text", "text": "Keep names."}]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert len(body["messages"][0]["content"]) == 2
    assert body["max_tokens"] == 131072
    assert body["stop_sequences"] == ["THE END"]
    assert not {"input", "reasoning", "reasoning_effort", "temperature", "top_p", "store"} & body.keys()


def test_messages_stream_text_once_and_close(messages_sdk):
    sdk, _, responses = messages_sdk(events=message_events())
    stream = MessagesClient(sdk).chat.completions.create(model=MODEL, messages=MESSAGES, stream=True)
    assert "".join(main._safe_chunk_text(c) for c in stream) == TEXT
    assert responses[0].is_closed


@pytest.mark.parametrize("events,match", [
    (message_events()[:-1], "before message_stop"),
    (message_events(reason="max_tokens"), "reply-token limit"),
    (message_events(reason="refusal"), "refused"),
    (message_events(reason="tool_use"), "did not complete"),
    (message_events(reason="model_context_window_exceeded"), "did not complete"),
    (message_events(reason=None), "missing stop reason"),
    (message_events(text=""), "no visible text"),
    (message_events()[:8] + message_events()[9:], "incomplete content"),
])
def test_incomplete_streams_are_failures(events, match, messages_sdk):
    sdk, _, responses = messages_sdk(events=events)
    with pytest.raises(RuntimeError, match=match):
        list(MessagesClient(sdk).chat.completions.create(model=MODEL, messages=MESSAGES, stream=True))
    assert responses[0].is_closed


@pytest.mark.parametrize("body,match", [
    (message_body(stop_reason="max_tokens"), "reply-token limit"),
    (message_body(stop_reason=None), "missing stop reason"),
    (message_body(content=[]), "no visible text"),
    (message_body(stop_reason="refusal"), "refused"),
    (message_body(stop_details={"type": "refusal"}), "refused"),
])
def test_incomplete_nonstream_messages_are_failures(body, match, messages_sdk):
    sdk, _, _ = messages_sdk(body=body)
    with pytest.raises(RuntimeError, match=match):
        MessagesClient(sdk).chat.completions.create(model=MODEL, messages=MESSAGES)


def test_stream_error_after_text_does_not_complete(messages_sdk):
    sdk, _, responses = messages_sdk(events=message_events()[:8] + [
        {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}])
    with pytest.raises(Exception, match="Overloaded|overloaded"):
        list(MessagesClient(sdk).chat.completions.create(model=MODEL, messages=MESSAGES, stream=True))
    assert responses[0].is_closed


def test_windows_socket_failure_closes_messages_stream():
    class Broken:
        closed = False
        def __iter__(self):
            yield from message_events()[:8]
            raise OSError(9, "Bad file descriptor")
        def close(self):
            self.closed = True
    source = Broken()
    with pytest.raises(RuntimeError, match="interrupted"):
        list(MessagesTextStream(source))
    assert source.closed


@pytest.mark.parametrize("status", [400, 401, 403, 429, 503])
def test_messages_preserve_http_status(status, messages_sdk):
    sdk, _, _ = messages_sdk(status=status, body={"type": "error", "error": {"type": "api_error", "message": "Provider reason"}})
    with pytest.raises(Exception) as error:
        MessagesClient(sdk).chat.completions.create(model=MODEL, messages=MESSAGES)
    assert error.value.status_code == status
    assert "Provider reason" in str(error.value)


@pytest.mark.parametrize("pipeline", ["story", "configured_story", "background", "rules"])
def test_all_hosted_pipelines_use_messages(pipeline, configured_user, monkeypatch, messages_sdk):
    sdk, requests, _ = messages_sdk(events=message_events() if pipeline != "background" else None)
    monkeypatch.setattr(main, "Anthropic", lambda **kwargs: sdk)
    main.save_user_keys(configured_user["uid"], {
        "openai_api_key": "test-key", "openai_base_url": "https://example.com/gateway/v1/messages",
        **{field: f"openai::{MODEL}" for field in ("story_model", "background_model", "rules_model")},
    })
    if pipeline == "background":
        text, _ = main.run_user_task_completion("Write.", "Continue.", configured_user, label="BA/test")
    elif pipeline == "rules":
        text = "".join(main.refine_with_rules_stream("A story.", "Keep names.", "Plain prose.", configured_user))
    else:
        selection = {"selected_provider": "openai", "selected_model": MODEL} if pipeline == "story" else {}
        stream, _, _ = main.stream_with_fallback("Write.", "Continue.", user_info=configured_user, **selection)
        text = "".join(main._safe_chunk_text(c) for c in stream)
    assert text == TEXT
    assert len(requests) == 1
    assert requests[0].url.path == "/gateway/v1/messages"
    assert json.loads(requests[0].content)["max_tokens"] == 131072


@pytest.mark.parametrize("reason", ["end_turn", "max_tokens", "interrupted"])
def test_generation_saves_only_completed_messages(reason, configured_user, monkeypatch, messages_sdk):
    events = message_events(reason=reason)
    if reason == "interrupted":
        events = events[:8]
    sdk, requests, _ = messages_sdk(events=events)
    monkeypatch.setattr(main, "Anthropic", lambda **kwargs: sdk)
    monkeypatch.setattr(main, "background_analysis", lambda *args, **kwargs: None)
    main.save_user_keys(configured_user["uid"], {"openai_api_key": "test-key", "openai_base_url": "https://example.com/gateway/v1/messages"})
    story = Path(main.get_story_path("message-story", uid=configured_user["uid"]))
    original = "The traveler arrived.\n"
    story.write_text(original, encoding="utf-8")
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: configured_user
    try:
        with TestClient(main.app) as app:
            result = app.post("/generate", json={"story_id": "message-story", "user_input": "Continue.",
                "provider": "openai", "model": MODEL, "skip_rules_check": True})
        events = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data: ")]
        assert events[-1]["type"] == ("done" if reason == "end_turn" else "error")
        if reason == "end_turn":
            assert story.read_text(encoding="utf-8").count(TEXT) == 1
        else:
            assert story.read_text(encoding="utf-8") == original
            assert not any(e["type"] in {"replace", "done"} for e in events)
        assert len(requests) == 1
    finally:
        main.app.dependency_overrides.clear()


def test_messages_discovery_pagination_and_advertised_maximum(catalog_api, monkeypatch, configured_user, messages_sdk):
    sdk, sent, _ = messages_sdk()
    monkeypatch.setattr(main, "Anthropic", lambda **kwargs: sdk)
    requests = []
    def discover(request, **kwargs):
        requests.append(request)
        second = "after_id=" in request.full_url
        return io.BytesIO(json.dumps({"data": [{"id": MODEL if not second else "second-model",
                    "created_at": "2026-09-01T00:00:00Z", "max_tokens": 262144}],
                    "has_more": not second, "last_id": MODEL}).encode())
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api, key="test-key", url="https://example.com/gateway/v1/messages")
    data = catalog_api.get("/api/providers-models").json()["providers"]["openai"]
    assert data["name"] == "Anthropic Messages (Custom API)"
    assert set(data["models"]) == {MODEL, "second-model"}
    assert requests[0].full_url == "https://example.com/gateway/v1/models"
    assert requests[1].full_url.endswith("/models?after_id=" + MODEL)
    assert requests[0].get_header("X-api-key") == "test-key"
    assert requests[0].get_header("Anthropic-version") == "2023-06-01"
    assert requests[0].get_header("Authorization") is None
    client = main.get_effective_ai_clients(configured_user)["openai_client"]
    client.chat.completions.create(model=MODEL, messages=MESSAGES)
    assert json.loads(sent[-1].content)["max_tokens"] == 262144
    assert catalog_api.post("/api/user/settings", json={"openai_max_output_tokens": "400000"}).status_code == 200
    main.get_effective_ai_clients(configured_user)["openai_client"].chat.completions.create(model=MODEL, messages=MESSAGES)
    assert json.loads(sent[-1].content)["max_tokens"] == 262144
    assert catalog_api.post("/api/user/settings", json={"openai_max_output_tokens": "64000"}).status_code == 200
    main.get_effective_ai_clients(configured_user)["openai_client"].chat.completions.create(model=MODEL, messages=MESSAGES)
    assert json.loads(sent[-1].content)["max_tokens"] == 64000


def test_explicit_messages_format_and_key_url_changes_clear_catalog(catalog_api, monkeypatch):
    seen = []
    def discover(request, **kwargs):
        seen.append((request.full_url, request.get_header("X-api-key")))
        return io.BytesIO(json.dumps({"data": [{"id": seen[-1][1]}]}).encode())
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api, key="first-test-key", openai_api_format="messages")
    assert catalog_api.get("/api/providers-models").json()["providers"]["openai"]["models"] == ["first-test-key"]
    save_connection(catalog_api, key="second-test-key", url="https://another.example.com/prefix/v1", openai_api_format="messages")
    result = catalog_api.get("/api/providers-models").json()["providers"]["openai"]
    assert result["models"] == ["second-test-key"]
    assert seen[-1] == ("https://another.example.com/prefix/v1/models", "second-test-key")


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "1e6", "oops", "2147483648"])
def test_invalid_reply_limits_rejected(catalog_api, value):
    assert catalog_api.post("/api/user/settings", json={"openai_max_output_tokens": value}).status_code == 422


def test_messages_settings_roundtrip_cache_and_redirects(catalog_api, configured_user, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "unrelated-server-token")
    save_connection(catalog_api, url="https://example.com/v1/messages", openai_max_output_tokens="200000")
    settings = catalog_api.get("/api/user/settings").json()["masked_keys"]
    assert settings["openai_max_output_tokens"] == "200000"
    assert settings["openai_base_url"] == "https://example.com/v1/messages"
    client = main.get_effective_ai_clients(configured_user)["openai_client"]
    assert isinstance(client, MessagesClient)
    assert client._client.follow_redirects is False
    assert not client.auth_token
    assert main.get_effective_ai_clients(configured_user)["openai_client"] is client
    assert catalog_api.post("/api/user/settings", json={"openai_api_format": "chat_completions"}).status_code == 200
    assert not isinstance(main.get_effective_ai_clients(configured_user)["openai_client"], MessagesClient)


@pytest.mark.parametrize("model", ["claude-custom", "qwen-custom"])
def test_opencode_messages_routing(model, configured_user, monkeypatch, messages_sdk):
    sdk, requests, _ = messages_sdk(base="https://opencode.ai/zen/v1")
    monkeypatch.setattr(main, "Anthropic", lambda **kwargs: sdk)
    client = main._clients_from_keys({"openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1/responses"})["openai_client"]
    assert isinstance(client, OpenCodeClient)
    assert client.chat.completions.create(model=model, messages=MESSAGES).choices[0].message.content == TEXT
    assert requests[0].url.path == "/zen/v1/messages"


def test_messages_keeps_images_and_rejects_unsupported_audio(messages_sdk):
    sdk, requests, _ = messages_sdk()
    client = MessagesClient(sdk)
    image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,dGVzdA=="}}
    client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": [image]}])
    assert json.loads(requests[0].content)["messages"][0]["content"][0] == {
        "type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "dGVzdA=="}}
    with pytest.raises(ValueError, match="input_audio"):
        client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "dGVzdA=="}}]}])
    assert len(requests) == 1
