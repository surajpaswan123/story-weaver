import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

import main
from openai_compat import OpenCodeClient, is_opencode_zen
from test_responses import MODEL, MESSAGES, configured_user, response_body, events_for


CHAT_MODEL = "mimo-v2.5-free"


def sse(events):
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
                          text="".join(f"data: {json.dumps(event)}\n\n" for event in events))


def reply(request):
    payload = json.loads(request.content)
    if request.url.path.endswith("/responses"):
        return sse(events_for()) if payload.get("stream") else httpx.Response(200, json=response_body())
    if payload.get("stream"):
        return sse([{"choices": [{"delta": {"content": "Chat story text."}, "finish_reason": None}]}])
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Chat story text."}}]})


@pytest.mark.parametrize("suffix", ["", "/responses", "/chat/completions"])
@pytest.mark.parametrize("saved_format", ["auto", "responses", "chat_completions"])
def test_one_saved_connection_switches_protocol_per_model(suffix, saved_format, configured_user, monkeypatch):
    seen = []
    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return reply(request)
    with OpenAI(api_key="test-key", base_url="https://opencode.ai/zen/v1", max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handler))) as sdk:
        monkeypatch.setattr(main, "OpenAI", lambda **kwargs: sdk)
        client = main._clients_from_keys({
            "openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1" + suffix,
            "openai_api_format": saved_format, "openai_reasoning_effort": "xhigh",
        })["openai_client"]
        assert isinstance(client, OpenCodeClient)
        for model in (MODEL, CHAT_MODEL, MODEL):
            assert client.chat.completions.create(model=model, messages=MESSAGES, temperature=1).choices[0].message.content
    assert [path for path, _ in seen] == ["/zen/v1/responses", "/zen/v1/chat/completions", "/zen/v1/responses"]
    assert seen[0][1]["input"] == MESSAGES
    assert seen[0][1]["reasoning"] == {"effort": "xhigh"}
    assert "temperature" not in seen[0][1]
    assert seen[1][1]["messages"] == MESSAGES
    assert seen[1][1]["temperature"] == 1
    assert "reasoning" not in seen[1][1]


@pytest.mark.parametrize("url", ["https://example.com/zen/v1", "https://opencode.ai.evil.example/zen/v1", "https://opencode.ai/other/v1"])
def test_opencode_routing_is_scoped_to_exact_service(url):
    assert not is_opencode_zen(url)


def test_mixed_story_background_and_rules_models(configured_user, monkeypatch):
    seen = []
    def handler(request):
        seen.append(request.url.path)
        return reply(request)
    with OpenAI(api_key="test-key", base_url="https://opencode.ai/zen/v1", max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handler))) as sdk:
        monkeypatch.setattr(main, "OpenAI", lambda **kwargs: sdk)
        main.save_user_keys(configured_user["uid"], {
            "openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1/responses",
            "openai_api_format": "responses", "openai_reasoning_effort": "xhigh",
            "story_model": "openai::" + MODEL, "background_model": "openai::" + CHAT_MODEL,
            "rules_model": "openai::" + CHAT_MODEL,
        })
        stream, _, _ = main.stream_with_fallback("Write.", "Continue.", user_info=configured_user)
        assert "".join(main._safe_chunk_text(c) for c in stream) == "Hello from the story."
        assert main.run_user_task_completion("Write.", "Continue.", configured_user, label="BA/test")[0] == "Chat story text."
        assert "".join(main.refine_with_rules_stream("A story.", "Keep names.", "Plain prose.", configured_user)) == "Chat story text."
    assert seen == ["/zen/v1/responses", "/zen/v1/chat/completions", "/zen/v1/chat/completions"]


@pytest.mark.parametrize("failure_status", [429, 503, 401, 404])
def test_selected_provider_preserves_http_errors(failure_status, configured_user, monkeypatch):
    with OpenAI(api_key="test-key", base_url="https://opencode.ai/zen/v1", max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
                    failure_status, json={"error": {"message": "Original provider reason"}}
                )))) as sdk:
        monkeypatch.setattr(main, "get_effective_ai_clients", lambda user: {"openai_client": OpenCodeClient(sdk)})
        with pytest.raises(Exception) as exc:
            main.stream_with_fallback("Write.", "Continue.", selected_provider="openai", selected_model=MODEL, user_info=configured_user)
    assert exc.value.status_code == failure_status
    assert "Original provider reason" in str(exc.value)
    assert main.is_transient_error(exc.value) == (failure_status in {429, 503})


def test_generate_retries_rate_limit_then_saves_success(configured_user, monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(429, json={"error": {"type": "FreeUsageLimitError", "message": "Rate limit exceeded. Please try again later."}})
        return reply(request)
    with OpenAI(api_key="test-key", base_url="https://opencode.ai/zen/v1", max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handler))) as sdk:
        monkeypatch.setattr(main, "OpenAI", lambda **kwargs: sdk)
        monkeypatch.setattr(main, "_transient_delay", lambda attempt: 0)
        monkeypatch.setattr(main, "MAX_TRANSIENT_RETRIES", 1)
        monkeypatch.setattr(main, "background_analysis", lambda *a, **kw: None)
        main.save_user_keys(configured_user["uid"], {"openai_api_key": "test-key", "openai_base_url": "https://opencode.ai/zen/v1"})
        path = Path(main.get_story_path("rate-limit-test", uid=configured_user["uid"]))
        path.write_text("The traveler arrived.\n", encoding="utf-8")
        main.app.dependency_overrides[main.require_authenticated_user] = lambda: configured_user
        try:
            with TestClient(main.app) as app:
                result = app.post("/generate", json={"story_id": "rate-limit-test", "user_input": "Continue.", "provider": "openai", "model": MODEL, "skip_rules_check": True})
            events = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data: ")]
            retry = next(event for event in events if event["type"] == "retrying")
            assert "free-model usage limit" in retry["message"]
            assert "429" in retry["message"]
            assert events[-1]["type"] == "done"
            assert path.read_text(encoding="utf-8").count("Hello from the story.") == 1
            assert len(seen) == 2
            assert all(request.url.path == "/zen/v1/responses" for request in seen)
        finally:
            main.app.dependency_overrides.clear()


@pytest.mark.parametrize("model", ["claude-opus-4-8", "qwen3.6-plus", "gemini-3.8-flash"])
def test_other_protocols_explain_the_requirement_without_sending(model):
    class MustNotSend:
        def __getattr__(self, name):
            raise AssertionError("An unsupported protocol must not send an invalid request")
    with pytest.raises(ValueError, match="requires"):
        OpenCodeClient(MustNotSend()).chat.completions.create(model=model, messages=MESSAGES)
