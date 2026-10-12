"""Regression tests for preserving paired prompts in bounded chat history."""
import json
from pathlib import Path

from runtime_support import read_chat_page


def _history(tmp_path: Path, entries):
    path = tmp_path / "chat_log.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return str(path)


def test_oversized_reply_keeps_its_prompt(tmp_path):
    path = _history(tmp_path, [
        {"role": "user", "text": "an older prompt"},
        {"role": "ai", "text": "an older reply"},
        {"role": "user", "text": "Luna's latest instruction " * 1200},
        {"role": "ai", "text": "final chapter", "model_thoughts": "thinking" * 60000},
    ])
    page = read_chat_page(path, last=40, max_chars=256_000)
    assert [entry["role"] for entry in page["messages"]] == ["user", "ai"]
    assert page["messages"][0]["text"].startswith("Luna's latest instruction")
    assert page["messages"][1]["text"] == "final chapter"
    assert page["start_index"] == 2
    assert page["total_entries"] == 4


def test_in_progress_user_prompt_remains_visible(tmp_path):
    path = _history(tmp_path, [
        {"role": "user", "text": "previous"},
        {"role": "ai", "text": "reply", "model_thoughts": "reasoning" * 40000},
        {"role": "user", "text": "the current prompt"},
    ])
    page = read_chat_page(path, last=40, max_chars=256_000)
    assert page["messages"][-1]["role"] == "user"
    assert page["messages"][-1]["text"] == "the current prompt"


def test_explicit_single_message_page_remains_single(tmp_path):
    path = _history(tmp_path, [
        {"role": "user", "text": "an instruction"},
        {"role": "ai", "text": "a lengthy response" * 200},
    ])
    page = read_chat_page(path, last=1, max_chars=100)
    assert len(page["messages"]) == 1
    assert page["messages"][0]["role"] == "ai"
