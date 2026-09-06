import io
import json
import time
import urllib.error

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

import main
from test_responses import configured_user


@pytest.fixture
def catalog_api(configured_user, monkeypatch):
    monkeypatch.setattr(main, "DYNAMIC_PROVIDER_MODELS", {
        "openai": {"name": "Old OpenCode", "models": ["muse-spark-1.3-contributor-free"]},
    })
    main.app.dependency_overrides[main.get_current_user_info] = lambda: configured_user
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()


def model_response(models):
    return io.BytesIO(json.dumps({"data": [{"id": model} for model in models]}).encode())


def save_connection(client, key="new-test-key", url="https://example.com/v1", **overrides):
    response = client.post("/api/user/settings", json={
        "openai_api_key": key, "openai_base_url": url, **overrides,
    })
    assert response.status_code == 200


def test_switch_url_and_key_uses_current_catalog_every_time(catalog_api, monkeypatch):
    requests = []
    def discover(request, **kwargs):
        requests.append((request.full_url, request.get_header("Authorization")))
        return model_response(["new-provider-model"] if "example.com" in request.full_url else ["old-model"])
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api, "old-test-key", "https://opencode.ai/zen/v1")
    assert catalog_api.get("/api/providers-models").json()["providers"]["openai"]["models"] == ["old-model"]
    save_connection(catalog_api)
    for _ in range(2):
        result = catalog_api.get("/api/providers-models").json()
        assert result["providers"]["openai"]["models"] == ["new-provider-model"]
        assert result["errors"] == {}
    assert requests == [
        ("https://opencode.ai/zen/v1/models", "Bearer old-test-key"),
        ("https://example.com/v1/models", "Bearer new-test-key"),
        ("https://example.com/v1/models", "Bearer new-test-key"),
    ]
    assert "openai" not in main.DYNAMIC_PROVIDER_MODELS


def test_empty_catalog_does_not_reuse_opencode_models(catalog_api, monkeypatch):
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", lambda *args, **kwargs: model_response([]))
    save_connection(catalog_api)
    result = catalog_api.get("/api/providers-models").json()
    assert result["providers"]["openai"]["models"] == []
    assert result["providers"]["openai"]["configured"] is True
    assert result["providers"]["openai"]["discovery_status"] == "empty"
    assert "returned no models" in result["errors"]["openai"]
    assert "muse-spark" not in json.dumps(result)


@pytest.mark.parametrize("status,expected", [(401, "API key"), (403, "access"), (404, "/v1"), (429, "rate limiting"), (503, "connection")])
def test_discovery_http_errors_clear_stale_models_and_do_not_echo_secrets(catalog_api, monkeypatch, status, expected):
    def discover(request, **kwargs):
        raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(b'new-test-key secret body'))
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api)
    result = catalog_api.get("/api/providers-models").json()
    assert result["providers"]["openai"]["models"] == []
    assert result["providers"]["openai"]["discovery_status"] == "error"
    assert f"HTTP {status}" in result["errors"]["openai"]
    assert expected in result["errors"]["openai"]
    assert "new-test-key" not in json.dumps(result)


@pytest.mark.parametrize("body", [b"<html>New API</html>", b'{}', b'null', b'{"data":{}}'])
def test_html_or_malformed_catalog_is_reported(catalog_api, monkeypatch, body):
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", lambda *args, **kwargs: io.BytesIO(body))
    save_connection(catalog_api)
    result = catalog_api.get("/api/providers-models").json()
    assert result["providers"]["openai"]["models"] == []
    assert "valid model list" in result["errors"]["openai"]


def test_network_failure_is_not_reported_as_an_empty_success(catalog_api, monkeypatch):
    def discover(*args, **kwargs):
        raise TimeoutError("new-test-key should not be displayed")
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api)
    result = catalog_api.get("/api/providers-models").json()
    assert result["providers"]["openai"]["models"] == []
    assert "Could not reach" in result["errors"]["openai"]
    assert "new-test-key" not in json.dumps(result)


def test_key_only_change_can_remove_all_models(catalog_api, monkeypatch):
    def discover(request, **kwargs):
        models = ["old-model"] if request.get_header("Authorization") == "Bearer old-test-key" else []
        return model_response(models)
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api, "old-test-key")
    assert catalog_api.get("/api/providers-models").json()["providers"]["openai"]["models"] == ["old-model"]
    save_connection(catalog_api)
    assert catalog_api.get("/api/providers-models").json()["providers"]["openai"]["models"] == []


def test_failed_provider_does_not_hide_other_current_providers(catalog_api, monkeypatch):
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", lambda *args, **kwargs: model_response([]))
    monkeypatch.setattr(main, "fetch_groq_live_models", lambda key: ("groq", [{"id": "groq-model"}]))
    save_connection(catalog_api, groq_api_key="groq-test-key")
    result = catalog_api.get("/api/providers-models").json()
    assert set(result["providers"]) == {"openai", "groq"}
    assert set(result["errors"]) == {"openai"}


def test_no_key_user_cannot_inherit_custom_connection_catalog(catalog_api, monkeypatch):
    monkeypatch.setattr(main, "LAST_DYNAMIC_FETCH", time.time())
    assert catalog_api.get("/api/providers-models").json()["providers"] == {}


@pytest.mark.parametrize("update", [
    {"openai_api_key": "replacement-test-key"},
    {"openai_base_url": "https://other.example.com/v1"},
    {"clear_keys": ["openai_api_key"]},
])
def test_changed_connection_clears_resubmitted_old_pipeline_choices(catalog_api, update):
    old = "openai::old-model"
    save_connection(catalog_api, story_model=old, background_model=old, rules_model="groq::keep-this", audio_model=old)
    assert catalog_api.post("/api/user/settings", json={"story_model": old, "background_model": old, **update}).status_code == 200
    saved = catalog_api.get("/api/user/settings").json()["masked_keys"]
    assert saved["story_model"] == saved["background_model"] == saved["audio_model"] == ""
    assert saved["rules_model"] == "groq::keep-this"


def test_unchanged_connection_preserves_pipeline_choices_and_new_choices_are_accepted(catalog_api):
    save_connection(catalog_api, story_model="openai::old-model")
    save_connection(catalog_api, key="", openai_api_format="responses")
    assert catalog_api.get("/api/user/settings").json()["masked_keys"]["story_model"] == "openai::old-model"
    save_connection(catalog_api, key="replacement-test-key", story_model="openai::new-model")
    assert catalog_api.get("/api/user/settings").json()["masked_keys"]["story_model"] == "openai::new-model"


def test_discovery_splits_multiple_keys_and_tries_next_key(configured_user, monkeypatch):
    headers = []
    def discover(request, **kwargs):
        headers.append(request.get_header("Authorization"))
        if len(headers) == 1:
            raise urllib.error.HTTPError(request.full_url, 401, "denied", {}, io.BytesIO())
        return model_response(["new-model"])
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    assert main.fetch_openai_live_models("bad-key\ngood-key", "https://example.com/v1")[1][0]["id"] == "new-model"
    assert headers == ["Bearer bad-key", "Bearer good-key"]


def test_automatic_candidates_come_from_current_connection(configured_user, monkeypatch):
    seen = []
    def discover(request, **kwargs):
        seen.append(request.full_url)
        return model_response(["new-story-model", "text-embedding-3-small"])
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    monkeypatch.setattr(main, "DYNAMIC_PROVIDER_MODELS", {"openai": {"models": ["old-model"]}})
    assert main._user_openai_models({"openai_api_key": "test-key", "openai_base_url": "https://example.com/v1"}) == ["new-story-model"]
    assert seen == ["https://example.com/v1/models"]


@pytest.mark.parametrize("provider,key_field,fetcher", [
    ("google", "gemini_api_key", "fetch_google_live_models"),
    ("nvidia", "nvidia_api_key", "fetch_nvidia_live_models"),
    ("openai", "openai_api_key", "fetch_openai_live_models"),
    ("openrouter", "openrouter_api_key", "fetch_openrouter_live_models"),
    ("groq", "groq_api_key", "fetch_groq_live_models"),
])
@pytest.mark.parametrize("empty", [True, False])
def test_every_configured_provider_remains_selectable_without_models(catalog_api, monkeypatch, provider, key_field, fetcher, empty):
    monkeypatch.setattr(main, fetcher, lambda *args, **kwargs: (provider, []) if empty else None)
    assert catalog_api.post("/api/user/settings", json={key_field: "provider-test-key"}).status_code == 200
    data = catalog_api.get("/api/providers-models").json()
    assert set(data["providers"]) == {provider}
    connection = data["providers"][provider]
    assert connection["configured"] is True
    assert connection["models"] == []
    assert connection["discovery_status"] == ("empty" if empty else "error")
    assert connection["discovery_error"] == data["errors"][provider]


def test_saved_openai_key_with_blank_url_uses_official_url_not_server_default(catalog_api, configured_user, monkeypatch):
    requests = []
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unrelated.example.com/v1")
    def discover(request, **kwargs):
        requests.append(request.full_url)
        return model_response(["official-model"])
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", discover)
    save_connection(catalog_api, url="")
    provider = catalog_api.get("/api/providers-models").json()["providers"]["openai"]
    assert provider["base_url"] == "https://api.openai.com/v1"
    assert requests == ["https://api.openai.com/v1/models"]
    sdk = main.get_effective_ai_clients(configured_user)["openai_client"]
    assert str(sdk.base_url) == "https://api.openai.com/v1/"


@pytest.mark.parametrize("api_format", ["chat_completions", "responses"])
def test_known_manual_model_generates_when_provider_catalog_is_empty(catalog_api, configured_user, monkeypatch, api_format):
    from test_responses import events_for

    requests = []
    story_text = "The river was quiet."
    def handle(request):
        requests.append(request)
        if api_format == "responses":
            events = events_for(story_text)
            body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        else:
            body = 'data: ' + json.dumps({"choices": [{"delta": {"content": story_text}, "index": 0}]}) + '\n\ndata: [DONE]\n\n'
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    sdk = OpenAI(api_key="test-key", base_url="https://example.com/v1",
                 http_client=httpx.Client(transport=httpx.MockTransport(handle)), max_retries=0)
    monkeypatch.setattr(main, "OpenAI", lambda **kwargs: sdk)
    monkeypatch.setattr(main._NO_REDIRECT_OPENER, "open", lambda *args, **kwargs: model_response([]))
    save_connection(catalog_api, key="test-key", openai_api_format=api_format)
    assert catalog_api.get("/api/providers-models").json()["providers"]["openai"]["models"] == []
    stream, _, _ = main.stream_with_fallback("Write.", "Continue.", user_info=configured_user,
                                            selected_provider="openai", selected_model="provider-known-model")
    assert "".join(main._safe_chunk_text(chunk) for chunk in stream) == story_text
    assert len(requests) == 1
    assert json.loads(requests[0].content)["model"] == "provider-known-model"
    assert requests[0].url.path == ("/v1/responses" if api_format == "responses" else "/v1/chat/completions")
