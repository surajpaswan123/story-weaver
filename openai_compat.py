"""Adapt Responses and Anthropic Messages to Story Weaver's text interface."""

from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

from anthropic import Stream
from anthropic.types import Message, RawMessageStreamEvent

API_FORMATS = {"auto", "chat_completions", "responses", "messages"}
REASONING_EFFORTS = {"", "none", "minimal", "low", "medium", "high", "xhigh"}


def is_opencode_zen(url):
    parsed = urlsplit(str(url))
    return (parsed.scheme == "https" and parsed.hostname == "opencode.ai"
            and parsed.port in (None, 443) and parsed.path.rstrip("/") == "/zen/v1")


def opencode_model_format(model):
    """Zen publishes endpoint formats by model family, not in GET /models.

    Source: https://opencode.ai/docs/zen/#endpoints. This only controls routing;
    available model IDs still come from the live authenticated model catalog.
    """
    name = model.lower()
    if name.startswith(("muse-spark-", "gpt-", "grok-")):
        return "responses"
    if name.startswith(("claude-", "qwen")):
        return "messages"
    if name.startswith("gemini-"):
        return "google"
    return "chat_completions"


def resolve_openai_endpoint(url, api_format="auto"):
    """Accept either an API base URL or a complete generation endpoint."""
    api_format = api_format or "auto"
    if api_format not in API_FORMATS:
        raise ValueError("API format must be auto, chat_completions, responses, or messages")
    parsed = urlsplit(url.strip())
    path = parsed.path.rstrip("/")
    detected = "messages" if parsed.hostname == "api.anthropic.com" else "chat_completions"
    for suffix, protocol in (("/chat/completions", "chat_completions"), ("/responses", "responses"), ("/messages", "messages")):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            detected = protocol
            break
    base_url = urlunsplit(parsed._replace(path=path))
    return base_url, detected if api_format == "auto" else api_format


def _get(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _check_response(response):
    status = _get(response, "status")
    error = _get(response, "error")
    if error or status in {"failed", "incomplete", "cancelled"}:
        detail = _get(error, "message") or _get(_get(response, "incomplete_details"), "reason") or status
        raise RuntimeError(f"Responses API did not complete: {detail}")


def _output_parts(response):
    _check_response(response)
    parts = {}
    for output_index, item in enumerate(_get(response, "output", []) or []):
        if _get(item, "type") != "message":
            continue
        for content_index, part in enumerate(_get(item, "content", []) or []):
            if _get(part, "type") == "refusal":
                raise RuntimeError("Responses API refused the request")
            if _get(part, "type") == "output_text":
                parts[(output_index, content_index)] = _get(part, "text", "") or ""
    return parts


def _chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text), finish_reason=None,
    )])


class ResponsesTextStream:
    """Yield visible text once; fail on incomplete or interrupted responses."""

    def __init__(self, stream):
        self.stream = stream

    def close(self):
        self.stream.close()

    def __iter__(self):
        emitted = {}

        def remaining(key, text):
            previous = emitted.get(key, "")
            if not text.startswith(previous):
                raise RuntimeError("Responses API final text disagrees with streamed text")
            emitted[key] = text
            return text[len(previous):]

        try:
            for event in self.stream:
                kind = _get(event, "type")
                key = (_get(event, "output_index", 0), _get(event, "content_index", 0))
                if kind == "response.output_text.delta":
                    text = _get(event, "delta", "") or ""
                    emitted[key] = emitted.get(key, "") + text
                    if text:
                        yield _chunk(text)
                elif kind == "response.output_text.done":
                    text = remaining(key, _get(event, "text", "") or "")
                    if text:
                        yield _chunk(text)
                elif kind == "response.completed":
                    response = _get(event, "response")
                    for part_key, final_text in _output_parts(response).items():
                        text = remaining(part_key, final_text)
                        if text:
                            yield _chunk(text)
                    if not any(text.strip() for text in emitted.values()):
                        raise RuntimeError("Responses API returned no visible text")
                    return
                elif kind in {"response.failed", "response.incomplete", "response.cancelled"}:
                    _check_response(_get(event, "response"))
                    raise RuntimeError(f"Responses API did not complete: {kind}")
                elif kind == "error":
                    raise RuntimeError(f"Responses API error: {_get(event, 'message', 'Unknown error')}")
                elif kind in {"response.refusal.delta", "response.refusal.done"}:
                    raise RuntimeError("Responses API refused the request")
            raise RuntimeError("Responses API stream ended before response.completed")
        except OSError as exc:
            # The story route has a legacy partial-save path for Windows socket
            # errors. A broken Responses stream must retain failure semantics.
            raise RuntimeError("Responses API stream was interrupted") from exc
        finally:
            self.close()


class ResponsesCompletions:
    def __init__(self, client, reasoning_effort=""):
        self.client = client
        self.reasoning_effort = reasoning_effort

    def create(self, *, model, messages, stream=False, **kwargs):
        # Pipeline temperatures are app defaults. Omit them because many
        # reasoning endpoints reject sampling controls altogether.
        kwargs.pop("temperature", None)
        kwargs.pop("top_p", None)
        kwargs.pop("stream_options", None)
        effort = kwargs.pop("reasoning_effort", None) or self.reasoning_effort
        max_tokens = kwargs.pop("max_completion_tokens", None)
        legacy_max = kwargs.pop("max_tokens", None)
        if max_tokens is not None or legacy_max is not None:
            kwargs["max_output_tokens"] = max_tokens if max_tokens is not None else legacy_max
        if effort:
            kwargs["reasoning"] = {"effort": effort}
        kwargs.setdefault("store", False)
        response = self.client.responses.create(model=model, input=messages, stream=stream, **kwargs)
        if stream:
            return ResponsesTextStream(response)
        text = "".join(_output_parts(response).values())
        if not text.strip():
            raise RuntimeError("Responses API returned no visible text")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class ResponsesClient:
    """Keep models, transport, and other SDK resources on the original client."""

    def __init__(self, client, reasoning_effort=""):
        self.client = client
        self.chat = SimpleNamespace(completions=ResponsesCompletions(client, reasoning_effort))

    def __getattr__(self, name):
        return getattr(self.client, name)


def _messages_content(content):
    """Convert the text/image content used by app pipelines without dropping data."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    blocks = []
    for part in content or []:
        kind = _get(part, "type")
        if kind == "text":
            blocks.append({"type": "text", "text": _get(part, "text", "")})
        elif kind == "image_url":
            url = _get(_get(part, "image_url"), "url", "")
            if url.startswith("data:image/") and ";base64," in url:
                metadata, data = url.split(";base64,", 1)
                source = {"type": "base64", "media_type": metadata[5:], "data": data}
            elif url.startswith("https://"):
                source = {"type": "url", "url": url}
            else:
                raise ValueError("Anthropic Messages images require an HTTPS URL or base64 image data")
            blocks.append({"type": "image", "source": source})
        else:
            raise ValueError(f"Anthropic Messages does not support this input type: {kind}. Select a provider that supports this media type.")
    return blocks


def _check_message_stop(reason, details=None):
    if reason == "refusal" or _get(details, "type") == "refusal":
        raise RuntimeError("Anthropic Messages refused the request")
    if reason == "max_tokens":
        raise RuntimeError("Anthropic Messages reached the reply-token limit before finishing. Increase Anthropic maximum output tokens in Settings and retry.")
    if reason not in {"end_turn", "stop_sequence"}:
        raise RuntimeError(f"Anthropic Messages did not complete: {reason or 'missing stop reason'}")


class MessagesTextStream:
    """Only accept visible text from a fully completed Messages stream."""

    def __init__(self, stream):
        self.stream = stream

    def close(self):
        self.stream.close()

    def __iter__(self):
        started, visible = False, False
        reason, details = None, None
        blocks = {}
        try:
            for event in self.stream:
                kind = _get(event, "type")
                if kind == "message_start":
                    started = True
                elif kind == "content_block_start":
                    block = _get(event, "content_block")
                    block_type = _get(block, "type")
                    if block_type in {"tool_use", "server_tool_use"}:
                        raise RuntimeError("Anthropic Messages requested a tool instead of completing the text")
                    blocks[_get(event, "index")] = block_type
                    if block_type == "text":
                        text = _get(block, "text", "") or ""
                        visible = visible or bool(text.strip())
                        if text:
                            yield _chunk(text)
                elif kind == "content_block_delta":
                    delta = _get(event, "delta")
                    if _get(delta, "type") == "text_delta":
                        if blocks.get(_get(event, "index")) != "text":
                            raise RuntimeError("Anthropic Messages sent text outside an open text block")
                        text = _get(delta, "text", "") or ""
                        visible = visible or bool(text.strip())
                        if text:
                            yield _chunk(text)
                elif kind == "content_block_stop":
                    blocks.pop(_get(event, "index"), None)
                elif kind == "message_delta":
                    delta = _get(event, "delta")
                    reason = _get(delta, "stop_reason") or reason
                    details = _get(delta, "stop_details") or details
                elif kind == "message_stop":
                    if not started or blocks:
                        raise RuntimeError("Anthropic Messages stream ended with incomplete content")
                    _check_message_stop(reason, details)
                    if not visible:
                        raise RuntimeError("Anthropic Messages returned no visible text")
                    return
                elif kind == "error":
                    raise RuntimeError(f"Anthropic Messages stream error: {_get(_get(event, 'error'), 'type', 'unknown')}")
            raise RuntimeError("Anthropic Messages stream ended before message_stop")
        except OSError as exc:
            # Avoid the story route's legacy Windows partial-save handling.
            raise RuntimeError("Anthropic Messages stream was interrupted") from exc
        finally:
            self.close()


class MessagesCompletions:
    def __init__(self, client, max_output_tokens=131072):
        self.client = client
        self.max_output_tokens = max_output_tokens

    def create(self, *, model, messages, stream=False, **kwargs):
        system, conversation = [], []
        for message in messages:
            role = _get(message, "role")
            content = _messages_content(_get(message, "content"))
            if role in {"system", "developer"}:
                if any(block["type"] != "text" for block in content):
                    raise ValueError("Anthropic Messages system instructions must be text")
                system.extend(content)
            elif role in {"user", "assistant"}:
                if content:
                    if conversation and conversation[-1]["role"] == role:
                        conversation[-1]["content"].extend(content)
                    else:
                        conversation.append({"role": role, "content": content})
            else:
                raise ValueError(f"Anthropic Messages does not support this message role: {role}")
        # These are defaults from the OpenAI-facing app interface. They are not
        # portable across Anthropic-compatible models, especially reasoning ones.
        for key in ("temperature", "top_p", "stream_options", "reasoning_effort"):
            kwargs.pop(key, None)
        limit = kwargs.pop("max_completion_tokens", None)
        legacy_limit = kwargs.pop("max_tokens", None)
        limit = limit if limit is not None else legacy_limit
        if limit is None:
            limit = self.max_output_tokens(model) if callable(self.max_output_tokens) else self.max_output_tokens
        stop = kwargs.pop("stop", None)
        if stop:
            kwargs["stop_sequences"] = [stop] if isinstance(stop, str) else stop
        body = dict(model=model, messages=conversation, max_tokens=limit, stream=stream, **kwargs)
        if system:
            body["system"] = system
        # The SDK's public custom-request API preserves arbitrary gateway path
        # prefixes. messages.create hardcodes /v1/messages and can duplicate /v1.
        response = self.client.post(
            "/messages", body=body, cast_to=Message,
            stream=stream, stream_cls=Stream[RawMessageStreamEvent],
        )
        if stream:
            return MessagesTextStream(response)
        _check_message_stop(_get(response, "stop_reason"), _get(response, "stop_details"))
        text = "".join(_get(block, "text", "") for block in _get(response, "content", [])
                       if _get(block, "type") == "text")
        if not text.strip():
            raise RuntimeError("Anthropic Messages returned no visible text")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class MessagesClient:
    def __init__(self, client, max_output_tokens=131072):
        self.client = client
        self.chat = SimpleNamespace(completions=MessagesCompletions(client, max_output_tokens))

    def __getattr__(self, name):
        return getattr(self.client, name)


class OpenCodeCompletions:
    """Choose the wire format on every call, including pipeline overrides."""

    def __init__(self, client, reasoning_effort="", messages_client=None, max_output_tokens=131072):
        self.client = client
        self.reasoning_effort = reasoning_effort
        self.responses = ResponsesCompletions(client, reasoning_effort)
        self.messages = MessagesCompletions(messages_client, max_output_tokens) if messages_client else None

    def create(self, *, model, messages, stream=False, **kwargs):
        protocol = opencode_model_format(model)
        if protocol == "responses":
            return self.responses.create(model=model, messages=messages, stream=stream, **kwargs)
        if protocol == "messages" and self.messages:
            return self.messages.create(model=model, messages=messages, stream=stream, **kwargs)
        if protocol != "chat_completions":
            endpoint = "/messages" if protocol == "messages" else "the Google Generative AI API"
            raise ValueError(f"OpenCode model {model} requires {endpoint}. "
                             "Select a supported endpoint for this model.")
        return self.client.chat.completions.create(model=model, messages=messages, stream=stream, **kwargs)


class OpenCodeClient:
    def __init__(self, client, reasoning_effort="", messages_client=None, max_output_tokens=131072):
        self.client = client
        self.messages_client = messages_client
        self.chat = SimpleNamespace(completions=OpenCodeCompletions(client, reasoning_effort, messages_client, max_output_tokens))

    def close(self):
        try:
            self.client.close()
        finally:
            if self.messages_client:
                self.messages_client.close()

    def __getattr__(self, name):
        return getattr(self.client, name)
