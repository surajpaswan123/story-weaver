import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from test_responses import configured_user


@pytest.fixture
def editor(configured_user, monkeypatch):
    monkeypatch.setattr(main, "_active_story_turns", {})
    main.app.dependency_overrides[main.get_current_user_id] = lambda: configured_user["uid"]
    main.app.dependency_overrides[main.get_current_user_info] = lambda: configured_user
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: configured_user
    folder = Path(main.get_story_dir("editor", uid=configured_user["uid"]))
    main.append_chat_entry("editor", "user", "Continue.", uid=configured_user["uid"])
    main.commit_ai_turn("editor", "Mira waited.", uid=configured_user["uid"], model_thoughts="<thought>Wait.</thought>")
    try:
        with TestClient(main.app) as client:
            yield client, folder
    finally:
        main.app.dependency_overrides.clear()


URL = "/story/editor/file/chat_log.json"


def test_list_read_edit_and_reload_preserves_thoughts_metadata_and_manuscript(editor, monkeypatch):
    client, folder = editor
    (folder / "pending_retry.json").write_text('{"prompt":"private retry"}', encoding="utf-8")
    files = client.get("/story/editor/files").json()["files"]
    chat = next(item for item in files if item["name"] == "chat_log.json")
    assert chat["label"] == "Chat history" and chat["owner"] == "app"
    assert not any(item["name"] == "pending_retry.json" for item in files)
    original = client.get(URL).json()["text"]
    entries = json.loads(original)
    entries[0]["text"] = 'Continue with "मीरा".\nKeep the pace.'
    entries[1]["model_thoughts"] = "<thought>Let her decide.</thought>"
    entries[1]["annotation"] = {"reviewed": True}
    edited = json.dumps(entries, ensure_ascii=False, indent=4) + "\n"
    synced = []
    monkeypatch.setattr(main, "sync_story_directory_to_firestore", lambda *args: synced.append(args))
    result = client.put(URL, json={"text": edited, "expected_text": original})
    assert result.status_code == 200, result.text
    assert result.json()["chars"] == len(edited)
    assert client.get(URL).json()["text"] == edited
    assert client.get("/story/editor/chat").json()["messages"] == [dict(entry, turn_index=0) for entry in entries]
    assert (folder / "story.md").read_text(encoding="utf-8") == "Mira waited."
    assert synced == [("responses-test", "editor")]


@pytest.mark.parametrize("text,reason", [
    ('[{"role":"ai",}]', "line 1, column"),
    ('{"role":"ai","text":"story"}', "JSON array"),
    ('[null]', "Chat entry 1"),
    ('[{"role":"assistant","text":"story"}]', 'role "user" or "ai"'),
    ('[{"role":"ai","text":42}]', "text string"),
    ('[{"role":"ai","text":"story","model_thoughts":{}}]', "model_thoughts must be a string"),
    ('[{"role":"ai","text":"story","extra":NaN}]', "valid JSON"),
])
def test_invalid_edits_leave_saved_history_untouched(editor, text, reason):
    client, folder = editor
    before = (folder / "chat_log.json").read_bytes()
    response = client.put(URL, json={"text": text})
    assert response.status_code == 422
    assert reason in response.json()["detail"]
    assert (folder / "chat_log.json").read_bytes() == before


def test_stale_editor_cannot_overwrite_a_new_turn(editor, configured_user):
    client, folder = editor
    original = client.get(URL).json()["text"]
    main.append_chat_entry("editor", "user", "Another turn.", uid=configured_user["uid"])
    latest = (folder / "chat_log.json").read_bytes()
    response = client.put(URL, json={"text": "[]", "expected_text": original})
    assert response.status_code == 409
    assert "changed since you opened" in response.json()["detail"]
    assert (folder / "chat_log.json").read_bytes() == latest


def test_active_generation_and_delete_cannot_replace_history(editor, configured_user):
    client, folder = editor
    before = (folder / "chat_log.json").read_bytes()
    token = main.begin_story_turn("editor", configured_user["uid"])
    assert client.put(URL, json={"text": "[]"}).status_code == 409
    main.end_story_turn("editor", configured_user["uid"], token)
    assert client.delete(URL).status_code == 400
    assert (folder / "chat_log.json").read_bytes() == before


def test_only_chat_json_is_exposed_and_markdown_remains_editable(editor, configured_user):
    client, _ = editor
    for name in ("pending_retry.json", "user_keys.json", "chatlog.json", "../chat_log.json", "chat_log.json:secret"):
        with pytest.raises(main.HTTPException) as error:
            main._resolve_story_file("editor", name, configured_user["uid"])
        assert error.value.status_code == 400
    response = client.put("/story/editor/file/characters.md", json={"text": "Mira is patient."})
    assert response.status_code == 200
    assert client.get("/story/editor/file/characters.md").json()["text"] == "Mira is patient."


def test_guest_cannot_edit_chat_history(editor):
    client, folder = editor
    before = (folder / "chat_log.json").read_bytes()
    del main.app.dependency_overrides[main.require_authenticated_user]
    main.app.dependency_overrides[main.get_current_user_info] = lambda: {"uid": "guest", "is_guest": True}
    assert client.put(URL, json={"text": "[]"}).status_code == 403
    assert (folder / "chat_log.json").read_bytes() == before


def test_large_transcript_revision_saves_every_thought_and_refreshes_token(editor):
    client, folder = editor
    opened = client.get(URL).json()
    entries = [{"role": "user", "text": "Continue. हिन्दी 🐉"},
               {"role": "ai", "text": "The complete story.",
                "model_thoughts": "A full saved thought. " * 430000,
                "annotation": {"reviewed": True}}]
    edited = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    assert len(edited) > 9_000_000
    response = client.put(URL, json={"text": edited, "expected_revision": opened["revision"]})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["revision"] != opened["revision"]
    assert saved["chars"] == len(edited)
    assert (folder / "chat_log.json").read_bytes() == edited.encode("utf-8")
    reopened = client.get(URL).json()
    assert reopened["text"] == edited and reopened["revision"] == saved["revision"]
    assert client.get("/story/editor/chat").json()["messages"][-1]["model_thoughts"] == entries[-1]["model_thoughts"]
    assert (folder / "story.md").read_text(encoding="utf-8") == "Mira waited."
    # A second save uses the returned token; a stale first token still conflicts.
    assert client.put(URL, json={"text": "[]", "expected_revision": opened["revision"]}).status_code == 409
    assert client.put(URL, json={"text": edited, "expected_revision": saved["revision"]}).status_code == 200


def test_revision_rejects_same_length_replacement_and_missing_history(editor):
    client, folder = editor
    opened = client.get(URL).json()
    main._atomic_write_text(str(folder / "chat_log.json"), opened["text"].replace("Mira", "Luna"))
    latest = (folder / "chat_log.json").read_bytes()
    assert client.put(URL, json={"text": "[]", "expected_revision": opened["revision"]}).status_code == 409
    assert (folder / "chat_log.json").read_bytes() == latest
    (folder / "chat_log.json").unlink()
    assert client.put(URL, json={"text": "[]", "expected_revision": opened["revision"]}).status_code == 409
    assert not (folder / "chat_log.json").exists()


def test_invalid_large_input_returns_small_error_without_echoing_content(editor):
    client, folder = editor
    before = (folder / "chat_log.json").read_bytes()
    response = client.put(URL, json={"text": {"private_text": "x" * 3_000_000}})
    assert response.status_code == 422
    assert len(response.content) < 1000
    assert "private_text" not in response.text
    assert (folder / "chat_log.json").read_bytes() == before
