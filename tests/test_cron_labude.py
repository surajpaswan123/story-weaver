"""Small cron-job.org endpoint regressions without importing the app."""
import ast
import asyncio
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Request, Response


def _load_handler():
    source = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    node = next(
        n for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "cron_labude"
    )
    # The route decorator requires initializing FastAPI; isolate the handler.
    function = copy.deepcopy(node)
    function.decorator_list = []
    namespace = {"Request": Request, "Response": Response}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
         namespace)
    return namespace["cron_labude"], node


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_cron_labude_is_tiny_success_not_actual_http_504(method):
    handler, route = _load_handler()
    response = asyncio.run(handler(SimpleNamespace(method=method)))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.media_type == "text/plain"
    expected = "504 लबुडे".encode("utf-8") if method == "GET" else b""
    assert response.body == expected
    assert int(response.headers["content-length"]) == len(expected)
    assert len(response.body) < 100
    assert any(isinstance(d, ast.Call) for d in route.decorator_list)


def test_original_ping_endpoint_is_not_changed():
    source = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    ping = next(
        n for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "ping"
    )
    text = ast.get_source_segment(source.read_text(encoding="utf-8"), ping)
    assert 'content="OK" if request.method == "GET"' in text
    assert '"Content-Length": "2"' in text
