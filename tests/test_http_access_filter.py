"""Regression coverage for suppressing routine HTTP access traffic.

Main must not be imported here: doing so initializes providers and storage.
The interceptor class itself is compiled from the production source.
"""
import ast
import io
import time
from collections import deque
from pathlib import Path

import pytest

from http_access_filter import is_routine_access_log


@pytest.mark.parametrize(
    "line, suppressed",
    [
        ('INFO:     172.16.3.250:41840 - "GET /api/logs HTTP/1.1" 200 OK', True),
        ('INFO:     127.0.0.1:43566 - "GET /ping HTTP/1.1" 200 OK', True),
        ('INFO:     127.0.0.1:43566 - "POST /story/id/generate HTTP/1.1" 202 Accepted', True),
        ('INFO:     127.0.0.1:43566 - "GET / HTTP/1.1" 304 Not Modified', True),
        ('\x1b[32mINFO:\x1b[0m     127.0.0.1:43566 - "GET /api/logs HTTP/1.1" \x1b[32m200 OK\x1b[0m', True),
        ('INFO:     127.0.0.1:43566 - "GET /api/logs HTTP/1.1" 401 Unauthorized', False),
        ('INFO:     127.0.0.1:43566 - "GET /api/logs HTTP/1.1" 403 Forbidden', False),
        ('INFO:     127.0.0.1:43566 - "GET /api/logs HTTP/1.1" 429 Too Many Requests', False),
        ('INFO:     127.0.0.1:43566 - "GET /api/logs HTTP/1.1" 503 Service Unavailable', False),
        ('[RulesEditor] Streamed successfully via NVIDIA/z-ai/glm-5.3', False),
        ('DEBUG: Stream finished. Full len: 200000', False),
        ('[20:38:31] INFO: 172.16.3.250:41840 - "GET /api/logs HTTP/1.1" 200 OK', False),
        ('INFO: Important diagnostic: GET /api/logs HTTP/1.1 succeeded', False),
        ('Traceback (most recent call last):', False),
        ('WARNING: NVIDIA returned HTTP 504', False),
    ],
)
def test_filters_only_successful_uvicorn_access_records(line, suppressed):
    assert is_routine_access_log(line) is suppressed


def _real_interceptor():
    """Load only the LogInterceptor class, with no application startup."""
    source = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LogInterceptor")
    captured = deque(maxlen=500)
    ns = {"is_routine_access_log": is_routine_access_log,
          "SERVER_LOGS": captured, "time": time}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), ns)
    return ns["LogInterceptor"], captured


def test_log_capture_preserves_every_application_line_and_http_errors():
    interceptor_type, captured = _real_interceptor()
    terminal = io.StringIO()
    stream = interceptor_type(terminal)
    stream.write(
        'DEBUG: Starting GLM-5.3\n'
        'INFO:     172.16.3.250:41840 - "GET /api/logs HTTP/1.1" 200 OK\n'
        '[RulesEditor] Applying consistency updates\n'
        'INFO:     172.16.3.250:41841 - "GET /ping HTTP/1.1" 304 Not Modified\n'
        'INFO:     172.16.3.250:41842 - "POST /story/id/generate HTTP/1.1" 503 Service Unavailable\n'
        'DEBUG: Writer finished. Full len: 200000\n'
    )
    expected = (
        'DEBUG: Starting GLM-5.3\n'
        '[RulesEditor] Applying consistency updates\n'
        'INFO:     172.16.3.250:41842 - "POST /story/id/generate HTTP/1.1" 503 Service Unavailable\n'
        'DEBUG: Writer finished. Full len: 200000\n'
    )
    assert terminal.getvalue() == expected
    assert len(captured) == 4
    assert all("GET /api/logs" not in line for line in captured)
    assert any("[RulesEditor]" in line for line in captured)
    assert any("503 Service Unavailable" in line for line in captured)


def test_capture_capacity_is_not_consumed_by_successful_poll_requests():
    interceptor_type, captured = _real_interceptor()
    stream = interceptor_type(io.StringIO())
    stream.write("Important GLM state\n")
    for _ in range(700):
        stream.write('INFO:     172.16.3.250:41840 - "GET /api/logs HTTP/1.1" 200 OK\n')
    assert len(captured) == 1
    assert "Important GLM state" in captured[0]


def test_interceptor_stream_compatibility_and_truncation():
    interceptor_type, captured = _real_interceptor()
    stream = interceptor_type(io.StringIO())
    assert stream.isatty() is False
    assert isinstance(stream.fileno(), int)
    stream.write("X" * 4500 + "\n")
    assert len(captured) == 1
    assert captured[0].endswith(" [truncated]")
    assert len(captured[0]) < 4200
