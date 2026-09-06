"""Adapt Responses endpoints to the text interface used by Story Weaver."""

from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit


API_FORMATS = {"auto", "chat_completions", "responses"}
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
        raise ValueError("OpenAI API format must be auto, chat_completions, or responses")
    parsed = urlsplit(url.strip())
    path = parsed.path.rstrip("/")
    detected = "chat_completions"
    for suffix, protocol in (("/chat/completions", "chat_completions"), ("/responses", "responses")):
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


class OpenCodeCompletions:
    """Choose the wire format on every call, including pipeline overrides."""

    def __init__(self, client, reasoning_effort=""):
        self.client = client
        self.reasoning_effort = reasoning_effort
        self.responses = ResponsesCompletions(client, reasoning_effort)

    def create(self, *, model, messages, stream=False, **kwargs):
        protocol = opencode_model_format(model)
        if protocol == "responses":
            return self.responses.create(model=model, messages=messages, stream=stream, **kwargs)
        if protocol != "chat_completions":
            endpoint = "/messages" if protocol == "messages" else "the Google Generative AI API"
            raise ValueError(f"OpenCode model {model} requires {endpoint}. "
                             "This connection supports Chat Completions and Responses models.")
        return self.client.chat.completions.create(model=model, messages=messages, stream=stream, **kwargs)


class OpenCodeClient:
    def __init__(self, client, reasoning_effort=""):
        self.client = client
        self.chat = SimpleNamespace(completions=OpenCodeCompletions(client, reasoning_effort))

    def __getattr__(self, name):
        return getattr(self.client, name)
