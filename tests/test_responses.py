import json
import io
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

import main
from openai_compat import OpenCodeClient, ResponsesClient, resolve_openai_endpoint


MODEL = "muse-spark-1.3-contributor-free"
MESSAGES = [{"role": "system", "content": "Write a story."}, {"role": "user", "content": "Continue."}]


def response_body(text="Hello from the story.", **overrides):
    return {
        "id": "resp_test", "object": "response", "created_at": 1,
        "status": "completed", "model": MODEL,
        "output": [
            {"type": "reasoning", "id": "rs_test", "summary": [{"type": "summary_text", "text": "Private planning"}]},
            {"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": text, "annotations": []}]},
        ],
        **overrides,
    }


def events_for(text="Hello from the story."):
    return [
        {"type": "response.created", "response": response_body(output=[], status="in_progress")},
        {"type": "response.reasoning_summary_text.delta", "delta": "Private planning"},
        {"type": "response.output_text.delta", "output_index": 1, "content_index": 0, "delta": text[:5]},
        {"type": "response.output_text.delta", "output_index": 1, "content_index": 0, "delta": text[5:]},
        {"type": "response.output_text.done", "output_index": 1, "content_index": 0, "text": text},
        {"type": "response.completed", "response": response_body(text)},
    ]


@pytest.fixture
def transport_client():
    resources = []

    def make(*, events=None, body=None, effort="xhigh"):
        requests = []
        responses = []

        def handle(request):
            requests.append(request)
            if events is not None:
                data = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
                result = httpx.Response(200, text=data, headers={"content-type": "text/event-stream"})
            else:
                result = httpx.Response(200, json=body or response_body())
            responses.append(result)
            return result

        sdk = OpenAI(api_key="test-key", base_url="https://opencode.ai/zen/v1",
                     http_client=httpx.Client(transport=httpx.MockTransport(handle)), max_retries=0)
        resources.append(sdk)
        return ResponsesClient(sdk, effort), requests, responses

    yield make
    for client in resources:
        client.close()


@pytest.mark.parametrize("url,mode,base,expected", [
    ("https://opencode.ai/zen/v1/responses/", "auto", "https://opencode.ai/zen/v1", "responses"),
    ("https://opencode.ai/zen/v1", "responses", "https://opencode.ai/zen/v1", "responses"),
    ("https://api.openai.com/v1", "auto", "https://api.openai.com/v1", "chat_completions"),
    ("https://example.com/v1/chat/completions", "auto", "https://example.com/v1", "chat_completions"),
    ("https://example.com/v1/responses", "chat_completions", "https://example.com/v1", "chat_completions"),
])
def test_endpoint_resolution(url, mode, base, expected):
    assert resolve_openai_endpoint(url, mode) == (base, expected)


def test_responses_request_and_nonstream_output(transport_client):
    client, requests, _ = transport_client()
    result = client.chat.completions.create(model=MODEL, messages=MESSAGES, temperature=1.0, max_tokens=123)
    assert result.choices[0].message.content == "Hello from the story."
    assert str(requests[0].url) == "https://opencode.ai/zen/v1/responses"
    assert json.loads(requests[0].content) == {
        "model": MODEL, "input": MESSAGES, "reasoning": {"effort": "xhigh"},
        "max_output_tokens": 123, "store": False, "stream": False,
    }


def test_provider_default_omits_reasoning(transport_client):
    client, requests, _ = transport_client(effort="")
    client.chat.completions.create(model=MODEL, messages=MESSAGES)
    assert "reasoning" not in json.loads(requests[0].content)


@pytest.mark.parametrize("events", [events_for(), [events_for()[-1]], events_for()[0:4] + events_for()[-1:]])
def test_stream_reads_visible_text_once_and_closes(events, transport_client):
    client, _, responses = transport_client(events=events)
    chunks = client.chat.completions.create(model=MODEL, messages=MESSAGES, stream=True)
    assert "".join(main._safe_chunk_text(c) for c in chunks) == "Hello from the story."
    assert responses[0].is_closed


@pytest.mark.parametrize("last_event,match", [
    ({"type": "response.failed", "response": response_body(status="failed", error={"message": "Provider failed"})}, "Provider failed"),
    ({"type": "response.incomplete", "response": response_body(status="incomplete", incomplete_details={"reason": "max_output_tokens"})}, "max_output_tokens"),
    ({"type": "error", "message": "Stream failed"}, "Stream failed"),
    ({"type": "response.refusal.done", "refusal": "Cannot comply"}, "refused"),
    (None, "before response.completed"),
])
def test_stream_failure_after_text_is_not_success(last_event, match, transport_client):
    events = events_for()[:4] + ([last_event] if last_event else [])
    client, _, responses = transport_client(events=events)
    with pytest.raises(RuntimeError, match=match):
        list(client.chat.completions.create(model=MODEL, messages=MESSAGES, stream=True))
    assert responses[0].is_closed


@pytest.mark.parametrize("body,match", [
    (response_body(output=[]), "no visible text"),
    (response_body(status="incomplete", incomplete_details={"reason": "max_output_tokens"}), "max_output_tokens"),
    (response_body(output=[{"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "No"}]}]), "refused"),
])
def test_nonstream_rejects_missing_incomplete_or_refused_output(body, match, transport_client):
    client, _, _ = transport_client(body=body)
    with pytest.raises(RuntimeError, match=match):
        client.chat.completions.create(model=MODEL, messages=MESSAGES)


@pytest.fixture
def configured_user(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORIES_DIR", str(tmp_path))
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "postgres_active", False)
    monkeypatch.setattr(main, "_USER_CLIENT_CACHE", {})
    monkeypatch.setattr(main.socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("8.8.8.8", 443))])
    user = {"uid": "responses-test", "email": "test@example.com", "is_super_admin": False, "is_guest": False}
    yield user
    for client in main._USER_CLIENT_CACHE.values():
        client.close()


def test_settings_api_round_trip_and_client_cache(configured_user):
    main.app.dependency_overrides[main.get_current_user_info] = lambda: configured_user
    try:
        with TestClient(main.app) as app:
            assert app.post("/api/user/settings", json={
                "openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1/responses",
                "openai_api_format": "auto", "openai_reasoning_effort": "xhigh",
            }).status_code == 200
            settings = app.get("/api/user/settings").json()["masked_keys"]
            assert settings["openai_api_format"] == "auto"
            assert settings["openai_reasoning_effort"] == "xhigh"
            assert settings["openai_api_key"] != "test-key"
            first = main.get_effective_ai_clients(configured_user)["openai_client"]
            assert isinstance(first, OpenCodeClient)
            assert str(first.base_url) == "https://opencode.ai/zen/v1/"
            assert first._client.follow_redirects is False
            assert main.get_effective_ai_clients(configured_user)["openai_client"] is first
            assert app.post("/api/user/settings", json={"openai_api_format": "invalid"}).status_code == 422
            assert app.post("/api/user/settings", json={"openai_reasoning_effort": "invalid"}).status_code == 422
            assert app.post("/api/user/settings", json={"openai_reasoning_effort": ""}).status_code == 200
            second = main.get_effective_ai_clients(configured_user)["openai_client"]
            assert second is not first
            assert second.chat.completions.reasoning_effort == ""
            assert app.post("/api/user/settings", json={"openai_api_format": "chat_completions"}).status_code == 200
            assert isinstance(main.get_effective_ai_clients(configured_user)["openai_client"], OpenCodeClient)
    finally:
        main.app.dependency_overrides.clear()


def test_full_endpoint_model_discovery_uses_base_models(configured_user, monkeypatch):
    seen = []

    # urllib's context manager only needs read(), so use a tiny byte stream.
    def open_request(request, **kwargs):
        seen.append(request.full_url)
        return io.BytesIO(json.dumps({"data": [{"id": MODEL}]}).encode())

    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", open_request)
    result = main.fetch_openai_live_models("test-key", "https://opencode.ai/zen/v1/responses")
    assert result[1][0]["id"] == MODEL
    assert seen == ["https://opencode.ai/zen/v1/models"]


@pytest.mark.parametrize("pipeline", ["story", "configured_story", "background", "rules"])
def test_all_openai_pipelines_send_responses(pipeline, configured_user, monkeypatch, transport_client):
    client, requests, _ = transport_client(events=events_for() if pipeline != "background" else None)
    monkeypatch.setattr(main, "OpenAI", lambda **kwargs: client.client)
    main.save_user_keys(configured_user["uid"], {
        "openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1/responses",
        "openai_reasoning_effort": "xhigh",
        "story_model": f"openai::{MODEL}", "background_model": f"openai::{MODEL}", "rules_model": f"openai::{MODEL}",
    })
    if pipeline == "background":
        text, _ = main.run_user_task_completion("Write.", "Continue.", configured_user, label="BA/test")
    elif pipeline == "rules":
        text = "".join(main.refine_with_rules_stream("A story.", "Keep the names.", "Plain prose.", configured_user))
    else:
        selection = {"selected_provider": "openai", "selected_model": MODEL} if pipeline == "story" else {}
        stream, _, _ = main.stream_with_fallback("Write.", "Continue.", user_info=configured_user, **selection)
        text = "".join(main._safe_chunk_text(c) for c in stream)
    assert text == "Hello from the story."
    assert len(requests) == 1
    assert requests[0].url.path == "/zen/v1/responses"
    assert json.loads(requests[0].content)["reasoning"] == {"effort": "xhigh"}


@pytest.mark.parametrize("completed", [True, False])
def test_generate_api_persists_only_completed_responses(completed, configured_user, monkeypatch, transport_client):
    text = "A lantern flickered beside the quiet river."
    events = events_for(text)
    client, requests, _ = transport_client(events=events if completed else events[:4])
    monkeypatch.setattr(main, "OpenAI", lambda **kwargs: client.client)
    monkeypatch.setattr(main, "background_analysis", lambda *args, **kwargs: None)
    main.save_user_keys(configured_user["uid"], {
        "openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1/responses",
        "openai_reasoning_effort": "xhigh",
    })
    story_path = Path(main.get_story_path("test-story", uid=configured_user["uid"]))
    original = "The traveler arrived.\n"
    story_path.write_text(original, encoding="utf-8")
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: configured_user
    try:
        with TestClient(main.app) as app:
            result = app.post("/generate", json={
                "user_input": "Continue.", "story_id": "test-story", "provider": "openai",
                "model": MODEL, "skip_rules_check": True,
            })
            status = app.get('/story/test-story/generation-status').json()
            assert status['active'] is False
            assert status['state'] == ('completed' if completed else 'failed')
        assert result.status_code == 200
        messages = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data: ")]
        if completed:
            assert messages[-1]["type"] == "done"
            assert any(item == {"type": "replace", "text": text} for item in messages)
            assert story_path.read_text(encoding="utf-8").count(text) == 1
        else:
            assert messages[-1]["type"] == "error"
            assert not any(item["type"] in {"done", "replace"} for item in messages)
            assert story_path.read_text(encoding="utf-8") == original
        assert len(requests) == 1
        assert requests[0].url.path == "/zen/v1/responses"
    finally:
        main.app.dependency_overrides.clear()


def test_existing_chat_completions_still_send_messages(configured_user, monkeypatch):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Hello"}}]})

    sdk = OpenAI(api_key="test-key", base_url="https://example.com/v1",
                 http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(main, "OpenAI", lambda **kwargs: sdk)
    client = main._clients_from_keys({"openai_api_key": "test-key", "openai_base_url": "https://example.com/v1"})["openai_client"]
    assert client.chat.completions.create(model="chat-model", messages=MESSAGES).choices[0].message.content == "Hello"
    assert requests[0].url.path == "/v1/chat/completions"
    assert json.loads(requests[0].content)["messages"] == MESSAGES


def test_windows_socket_error_is_a_responses_failure():
    from openai_compat import ResponsesTextStream
    class BrokenStream:
        closed = False
        def __iter__(self):
            yield events_for()[2]
            raise OSError(9, "Bad file descriptor")
        def close(self):
            self.closed = True
    source = BrokenStream()
    with pytest.raises(RuntimeError, match="interrupted"):
        list(ResponsesTextStream(source))
    assert source.closed
