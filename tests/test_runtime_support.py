import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from runtime_support import HistoryChanged, heartbeat_stream, read_chat_page, relay_stream


def transcript(path, count=125):
    entries = [{"role": "ai" if i % 2 else "user", "text": f"{i}: हिन्दी 🐉 " + "x" * (i % 11 * 100),
                "model_thoughts": "Saved thoughts" if i % 2 else ""} for i in range(count)]
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return entries


def test_recent_page_preserves_absolute_turn_numbers_and_prompt(tmp_path):
    path = tmp_path / "chat_log.json"
    entries = transcript(path)
    page = read_chat_page(path)
    assert len(page["messages"]) == 40
    assert (page["start_index"], page["end_index"], page["total_entries"], page["total_turns"]) == (85, 125, 125, 62)
    assert page["last_user_prompt"] == entries[-1]["text"]
    for i, entry in enumerate(page["messages"], 85):
        assert entry == dict(entries[i], turn_index=i // 2)


@pytest.mark.parametrize("direction", ["before", "after"])
def test_pages_cover_every_complete_entry_with_no_gaps(tmp_path, direction):
    path = tmp_path / "chat_log.json"
    original = transcript(path)
    result = []
    cursor = {} if direction == "before" else {"after": 0}
    while True:
        page = read_chat_page(path, last=10, max_chars=1400, **cursor)
        assert 1 <= len(page["messages"]) <= 10
        batch = [{k: v for k, v in entry.items() if k != "turn_index"} for entry in page["messages"]]
        if direction == "before":
            result = batch + result
            if page["start_index"] == 0:
                break
            cursor = {"before": page["start_index"], "revision": page["revision"]}
        else:
            result += batch
            if page["end_index"] == page["total_entries"]:
                break
            cursor = {"after": page["end_index"], "revision": page["revision"]}
    assert result == original


def test_one_oversized_entry_remains_intact_and_page_size_is_capped(tmp_path):
    path = tmp_path / "chat_log.json"
    transcript(path, 150)
    assert len(read_chat_page(path, last=9999)["messages"]) == 100
    text = "x" * 400000
    path.write_text(json.dumps([{"role": "ai", "text": text}]), encoding="utf-8")
    assert read_chat_page(path)["messages"][0]["text"] == text


def test_replaced_history_invalidates_paging_revision(tmp_path):
    path = tmp_path / "chat_log.json"
    transcript(path)
    revision = read_chat_page(path)["revision"]
    replacement = tmp_path / "replacement.json"
    transcript(replacement, 100)
    replacement.replace(path)
    with pytest.raises(HistoryChanged):
        read_chat_page(path, before=80, revision=revision)


@pytest.mark.parametrize("content", ['{}', '[', '[{"role":"ai","text":4}]', '[{"role":"system","text":"x"}]'])
def test_bad_transcript_does_not_look_like_empty_history(tmp_path, content):
    path = tmp_path / "chat_log.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_chat_page(path)


@pytest.fixture
def chat_api(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORIES_DIR", str(tmp_path))
    monkeypatch.setattr(main, "db_conn_str", "")
    monkeypatch.setattr(main, "db_firestore", None)
    main.app.dependency_overrides[main.get_current_user_id] = lambda: "paging-user"
    folder = Path(main.get_story_dir("test", uid="paging-user"))
    path = folder / "chat_log.json"
    transcript(path)
    with TestClient(main.app) as client:
        yield client, path
    main.app.dependency_overrides.clear()


def test_chat_api_bounded_no_store_and_revision_conflict(chat_api):
    client, path = chat_api
    response = client.get("/story/test/chat")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()["messages"]) == 40
    revision = response.json()["revision"]
    transcript(path, 150)
    assert client.get(f"/story/test/chat?before=85&revision={revision}").status_code == 409
    assert client.get("/story/test/chat?before=-1").status_code == 422
    assert client.get("/story/test/chat?before=1&after=1").status_code == 422
    path.write_text("bad json", encoding="utf-8")
    failed = client.get("/story/test/chat")
    assert failed.status_code == 422 and "chat_log.json" in failed.json()["detail"]


def test_relay_applies_backpressure_but_finishes_saving_after_disconnect():
    produced, saved = [], threading.Event()
    def provider():
        for i in range(100):
            produced.append(i)
            yield i
        saved.set()
    stream = relay_stream(provider(), max_queue=2)
    assert next(stream) == 0
    time.sleep(0.15)
    assert len(produced) <= 4
    stream.close()
    assert saved.wait(2), "Detached reader must not prevent the worker's final save"
    assert len(produced) == 100


def test_heartbeat_close_unblocks_full_queue_and_closes_provider():
    closed = threading.Event()
    def provider():
        try:
            for i in range(100000):
                yield i
        finally:
            closed.set()
    stream = heartbeat_stream(provider(), "heartbeat", interval=0.02, max_queue=2)
    assert next(stream) == 0
    time.sleep(0.15)
    stream.close()
    assert closed.wait(2)


@pytest.mark.parametrize("wrapper", [lambda gen: relay_stream(gen), lambda gen: heartbeat_stream(gen, "heartbeat")])
def test_stream_errors_reach_consumer(wrapper):
    def provider():
        yield "text"
        raise RuntimeError("provider failed")
    stream = wrapper(provider())
    assert next(stream) == "text"
    with pytest.raises(RuntimeError, match="provider failed"):
        next(stream)


def test_heartbeat_keeps_slow_provider_alive():
    ready = threading.Event()
    def provider():
        ready.wait(2)
        yield "text"
    stream = heartbeat_stream(provider(), "heartbeat", interval=0.01)
    try:
        assert next(stream) == "heartbeat"
        ready.set()
        assert next(stream) == "text"
    finally:
        ready.set()
        stream.close()
