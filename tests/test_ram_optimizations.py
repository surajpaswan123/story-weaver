import json
import asyncio
import gc
import threading
import weakref
from pathlib import Path

from fastapi.testclient import TestClient

import main
from test_responses import configured_user


def test_generate_analysis_and_undo_survive_memory_release(configured_user, monkeypatch):
    uid = configured_user["uid"]
    story_id = "ram-story"
    monkeypatch.setattr(main, "db_conn_str", "")
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "_active_story_turns", {})
    monkeypatch.setattr(main, "_stop_requests", {})
    monkeypatch.setattr(main, "BATCH_SIZE", 1)
    monkeypatch.setattr(main, "MAX_TRANSIENT_RETRIES", 0)
    monkeypatch.setattr(main, "has_any_generation_provider", lambda *args, **kwargs: True)
    main.save_user_keys(uid, {"openai_api_key": "test-key"})

    folder = Path(main.get_story_dir(story_id, uid=uid))
    story_path = folder / "story.md"
    story_path.write_text("Original story.", encoding="utf-8")
    (folder / "characters.md").write_text("Mira: dark hair", encoding="utf-8")

    captured = {}

    def fake_stream(system_msg, user_msg, **kwargs):
        captured["system_msg"] = system_msg
        captured["user_msg"] = user_msg
        return iter([main.GenericChunk("Fresh turn.")]), "Fake/writer", False

    def fake_analysis(story, full_story, new_text, user_id, user_info, *args, **kwargs):
        captured["analysis_story_id"] = story
        captured["analysis_full_story"] = full_story
        captured["analysis_new_text"] = new_text

    monkeypatch.setattr(main, "stream_with_fallback", fake_stream)
    monkeypatch.setattr(main, "background_analysis", fake_analysis)
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: configured_user
    try:
        with TestClient(main.app) as client:
            response = client.post("/generate", json={
                "story_id": story_id,
                "user_input": "Continue.",
                "provider": "openai",
                "model": "fake-model",
                "skip_rules_check": True,
            })
            assert response.status_code == 200
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            assert events[-1]["type"] == "done"
            assert any(event == {"type": "replace", "text": "Fresh turn."} for event in events)

            assert "Original story." in captured["system_msg"]
            assert captured["analysis_story_id"] == story_id
            assert captured["analysis_full_story"] == "Original story.\n\nFresh turn."
            assert captured["analysis_new_text"] == "Fresh turn."
            assert story_path.read_text(encoding="utf-8") == "Original story.\n\nFresh turn."

            undo = client.post(f"/story/{story_id}/undo")
            assert undo.status_code == 200, undo.text
            assert undo.json()["restored_prompt"] == "Continue."
            assert story_path.read_text(encoding="utf-8") == "Original story."
            assert (folder / "characters.md").read_text(encoding="utf-8") == "Mira: dark hair"
    finally:
        main.app.dependency_overrides.clear()


def test_background_analysis_prompt_keeps_full_story_and_new_text(configured_user, monkeypatch):
    uid = configured_user["uid"]
    story_id = "analysis-ram"
    folder = Path(main.get_story_dir(story_id, uid=uid))
    (folder / "story.md").write_text("The complete manuscript.\nSecond paragraph.", encoding="utf-8")
    (folder / "characters.md").write_text("Mira: dark hair", encoding="utf-8")
    (folder / "summary.md").write_text("Earlier summary.", encoding="utf-8")
    (folder / "rules.md").write_text("Mira cannot fly.", encoding="utf-8")

    captured = {}
    monkeypatch.setattr(main, "auto_spawn_categories", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "update_inventory", lambda story, new_text, **kwargs: captured.setdefault("inventory_new_text", new_text))

    def fake_completion(*, system_prompt, user_prompt, user_info, label, temperature):
        captured["analysis_prompt"] = user_prompt
        return "## Summary\nNo new events.\n## Consistency\nNo issues found.", "Fake/analysis"

    monkeypatch.setattr(main, "run_user_task_completion", fake_completion)
    full_story = "The complete manuscript.\nSecond paragraph."
    new_text = "A precise latest addition."
    main.background_analysis(
        story_id,
        full_story,
        new_text,
        user_id=uid,
        user_info=configured_user,
        analysis_mode="manual",
    )

    prompt = captured["analysis_prompt"]
    assert f"FULL STORY TEXT:\n{full_story}\n\n" in prompt
    assert f"NEW TEXT (latest addition — focus on this for new entries):\n{new_text}" in prompt
    assert captured["inventory_new_text"] == new_text


def test_idle_story_locks_release_but_waiters_keep_the_same_lock(monkeypatch):
    monkeypatch.setattr(main, "_story_locks", weakref.WeakValueDictionary())
    lock = main.get_story_lock("story", "u")
    ref = weakref.ref(lock)
    waiting, entered = threading.Event(), threading.Event()

    def waiter():
        same = main.get_story_lock("story", "u")
        assert same is ref()
        waiting.set()
        with same:
            entered.set()

    with lock:
        thread = threading.Thread(target=waiter)
        thread.start()
        assert waiting.wait(2)
        assert not entered.is_set()
        assert main.get_story_lock("story", "u") is lock
    thread.join(2)
    assert entered.is_set() and not thread.is_alive()
    del lock
    gc.collect()
    assert ref() is None and len(main._story_locks) == 0
    for index in range(1000):
        with main.get_story_lock(str(index), "u"):
            pass
    gc.collect()
    assert len(main._story_locks) == 0


def test_stopping_turns_does_not_retain_prompt_frames(configured_user, monkeypatch):
    monkeypatch.setattr(main, "db_conn_str", "")
    monkeypatch.setattr(main, "_active_story_turns", {})
    main.save_user_keys(configured_user["uid"], {"openai_api_key": "test-key"})
    monkeypatch.setattr(main, "has_any_generation_provider", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "stop_requested", lambda *args: True)
    monkeypatch.setattr(main, "stream_with_fallback", lambda *args, **kwargs:
                        (iter([main.GenericChunk("Uncommitted text.")]), "Fake/writer", False))

    async def stopped_turn(index):
        payload = main.StoryInput(story_id=f"stop-ram-{index}", user_input="Full prompt. " * 7000,
                                  provider="openai", model="fake", skip_rules_check=True)
        ref = weakref.ref(payload)
        response = await main.generate_story(payload, main.BackgroundTasks(), configured_user)
        events = [event async for event in response.body_iterator]
        assert any('"type": "stopped"' in event for event in events)
        assert not any('"type": "error"' in event or '"type": "replace"' in event for event in events)
        return ref

    refs = [asyncio.run(stopped_turn(index)) for index in range(3)]
    gc.collect()
    assert all(ref() is None for ref in refs)
