import json

import httpx
from anthropic import Anthropic

from openai_compat import MessagesClient


def test_messages_client_normalizes_empty_anthropic_auth_token():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "provider-story-model",
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    sdk = Anthropic(
        api_key="test-key",
        auth_token="",
        base_url="https://example.com/gateway/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    try:
        result = MessagesClient(sdk).chat.completions.create(
            model="provider-story-model",
            messages=[{"role": "user", "content": "Say hello."}],
        )
        assert result.choices[0].message.content == "Hello!"
        assert sdk.auth_token is None
        assert len(requests) == 1
        assert requests[0].headers["x-api-key"] == "test-key"
        assert "authorization" not in requests[0].headers
        assert json.loads(requests[0].content)["model"] == "provider-story-model"
    finally:
        sdk.close()
