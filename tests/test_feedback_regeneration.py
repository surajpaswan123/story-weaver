import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from regeneration import RegenerationContext, extract_model_thoughts, with_regeneration_feedback
from test_responses import configured_user


STORY = "feedback-story"
ORIGINAL_PROMPT = "Let Mira answer the stranger."
ORIGINAL_TURN = "Mira trusted the stranger at once."
THOUGHTS = "<thought>She might trust him.</thought>"
FEEDBACK = "Keep the conversation, but make Mira less trusting."


@pytest.fixture
def feedback_app(configured_user, monkeypatch):
    monkeypatch.setattr(main, "_active_story_turns", {})
    monkeypatch.setattr(main, "_stop_requests", {})
    monkeypatch.setattr(main, "has_any_generation_provider", lambda *args: True)
    monkeypatch.setattr(main, "BATCH_SIZE", 999)
    monkeypatch.setattr(main, "MAX_TRANSIENT_RETRIES", 0)
    main.save_user_keys(configured_user["uid"], {"openai_api_key": "test-key"})
    main.app.dependency_overrides[main.get_current_user_info] = lambda: configured_user
    main.app.dependency_overrides[main.get_current_user_id] = lambda: configured_user["uid"]
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: configured_user
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()


def seed_turn(user, thoughts=THOUGHTS):
    uid = user["uid"]
    folder = Path(main.get_story_dir(STORY, uid=uid))
    main.append_chat_entry(STORY, "user", "Begin the story.", uid=uid)
    main.commit_ai_turn(STORY, "A stranger arrived.", "test", uid=uid)
    (folder / "characters.md").write_text("Mira is cautious.", encoding="utf-8")
    main.save_snapshot(STORY, uid=uid)
    main.append_chat_entry(STORY, "user", ORIGINAL_PROMPT, uid=uid)
    main.commit_ai_turn(STORY, ORIGINAL_TURN, "test", uid=uid, model_thoughts=thoughts)
    (folder / "characters.md").write_text("Mira trusts the stranger.", encoding="utf-8")
    return folder


def prepare(client):
    response = client.post(f"/story/{STORY}/undo", json={"feedback": FEEDBACK})
    assert response.status_code == 200, response.text
    return response.json()


def generate(client, context=None):
    return client.post("/generate", json={
        "story_id": STORY, "user_input": ORIGINAL_PROMPT,
        "provider": "openai", "model": "test-model", "skip_rules_check": True,
        "regeneration": context,
    })


def test_feedback_undo_captures_turn_thoughts_and_original_prompt_before_restoring_snapshot(feedback_app, configured_user):
    folder = seed_turn(configured_user)
    result = prepare(feedback_app)
    assert result["restored_prompt"] == ORIGINAL_PROMPT
    assert result["regeneration"] == {
        "turn_to_replace": ORIGINAL_TURN, "model_thoughts": THOUGHTS, "feedback": FEEDBACK,
    }
    assert (folder / "story.md").read_text(encoding="utf-8") == "A stranger arrived."
    assert (folder / "characters.md").read_text(encoding="utf-8") == "Mira is cautious."
    pending = main.read_pending_retry(STORY, configured_user["uid"])
    assert pending["regeneration"] == result["regeneration"]
    assert pending["prompt"] == ORIGINAL_PROMPT


def test_end_to_end_feedback_is_labelled_and_saved_story_contains_only_replacement(feedback_app, configured_user, monkeypatch):
    folder = seed_turn(configured_user)
    context = prepare(feedback_app)["regeneration"]
    requests = []
    replacement = "Mira listened, keeping her distance."
    new_thoughts = "<thought>She should stay cautious.</thought>"
    def stream(system, user, **kwargs):
        requests.append((system, user))
        return iter([main.GenericChunk(new_thoughts), main.GenericChunk(replacement)]), "test-model", False
    monkeypatch.setattr(main, "stream_with_fallback", stream)
    response = generate(feedback_app, context)
    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert len(requests) == 1
    system, user = requests[0]
    assert "Mira is cautious." in system
    assert ORIGINAL_TURN not in system
    assert ORIGINAL_PROMPT in user
    for label, value in [("Turn to replace:", ORIGINAL_TURN), ("Model thoughts:", THOUGHTS), ("Feedback:", FEEDBACK)]:
        assert label in user and value in user
    saved = (folder / "story.md").read_text(encoding="utf-8")
    assert saved == "A stranger arrived.\n\n" + replacement
    entries = json.loads((folder / "chat_log.json").read_text(encoding="utf-8"))
    assert entries[-2]["text"] == ORIGINAL_PROMPT
    assert entries[-1]["text"] == replacement
    assert entries[-1]["model_thoughts"] == new_thoughts
    assert main.read_pending_retry(STORY, configured_user["uid"]) is None


def test_failed_feedback_generation_retains_context_for_retry_after_reload(feedback_app, configured_user, monkeypatch):
    folder = seed_turn(configured_user)
    context = prepare(feedback_app)["regeneration"]
    def fail(*args, **kwargs):
        raise RuntimeError("Provider is unavailable")
    monkeypatch.setattr(main, "stream_with_fallback", fail)
    response = generate(feedback_app, context)
    assert '"type": "error"' in response.text
    pending = feedback_app.get(f"/story/{STORY}/chat").json()["pending_retry"]
    assert pending["regeneration"] == context
    retried = feedback_app.post(f"/story/{STORY}/retry").json()
    assert retried["regeneration"] == context
    assert retried["prompt"] == ORIGINAL_PROMPT
    assert (folder / "story.md").read_text(encoding="utf-8") == "A stranger arrived."


@pytest.mark.parametrize("feedback", ["", "   \n\t", "x" * 100_001], ids=["empty", "whitespace", "too-long"])
def test_invalid_feedback_cannot_undo_a_turn(feedback_app, configured_user, feedback):
    folder = seed_turn(configured_user)
    before = {name: (folder / name).read_bytes() for name in ("story.md", "chat_log.json", "characters.md")}
    assert feedback_app.post(f"/story/{STORY}/undo", json={"feedback": feedback}).status_code == 422
    assert all((folder / name).read_bytes() == content for name, content in before.items())


def test_feedback_refuses_dangling_prompt_or_active_turn(feedback_app, configured_user):
    folder = seed_turn(configured_user)
    uid = configured_user["uid"]
    token = main.begin_story_turn(STORY, uid)
    assert feedback_app.post(f"/story/{STORY}/undo", json={"feedback": FEEDBACK}).status_code == 409
    main.end_story_turn(STORY, uid, token)
    main.append_chat_entry(STORY, "user", "Unanswered prompt", uid=uid)
    assert feedback_app.post(f"/story/{STORY}/undo", json={"feedback": FEEDBACK}).status_code == 409
    assert ORIGINAL_TURN in (folder / "story.md").read_text(encoding="utf-8")


def test_feedback_requires_authentication(configured_user, monkeypatch):
    main.app.dependency_overrides[main.get_current_user_info] = lambda: {"uid": "guest", "is_guest": True}
    try:
        with TestClient(main.app) as client:
            assert client.post(f"/story/{STORY}/undo", json={"feedback": FEEDBACK}).status_code == 403
    finally:
        main.app.dependency_overrides.clear()


def test_plain_regenerate_still_uses_plain_undo_without_feedback(feedback_app, configured_user):
    seed_turn(configured_user)
    response = feedback_app.post(f"/story/{STORY}/undo")
    assert response.status_code == 200
    assert response.json()["restored_prompt"] == ORIGINAL_PROMPT
    assert "regeneration" not in response.json()
    assert main.read_pending_retry(STORY, configured_user["uid"]) is None


@pytest.mark.parametrize("tag", ["thought", "think", "thoughts", "thaughts", "THOUGHT"])
def test_thought_tags_are_preserved_separately_without_polluting_story(configured_user, tag):
    raw = f'<{tag}>Consider the character.\nKeep her cautious.</{tag}>'
    folder = Path(main.get_story_dir(STORY, uid=configured_user["uid"]))
    main.commit_ai_turn(STORY, raw + ORIGINAL_TURN, uid=configured_user["uid"])
    assert (folder / "story.md").read_text(encoding="utf-8") == ORIGINAL_TURN
    entry = json.loads((folder / "chat_log.json").read_text(encoding="utf-8"))[-1]
    assert entry["model_thoughts"] == raw
    assert extract_model_thoughts(raw + ORIGINAL_TURN) == raw


def test_no_saved_thoughts_are_not_invented(feedback_app, configured_user):
    seed_turn(configured_user, thoughts="")
    context = RegenerationContext(**prepare(feedback_app)["regeneration"])
    message = with_regeneration_feedback("normal context", context)
    assert "Model thoughts:" in message
    assert "No model thoughts were saved" in message
    assert with_regeneration_feedback("normal context", None) == "normal context"


def test_local_generation_gets_same_feedback_and_persists_returned_thoughts(feedback_app, configured_user):
    folder = seed_turn(configured_user)
    context = prepare(feedback_app)["regeneration"]
    begin = feedback_app.post(f"/story/{STORY}/local-begin", json={"user_input": ORIGINAL_PROMPT, "regeneration": context})
    assert begin.status_code == 200
    data = begin.json()
    assert ORIGINAL_TURN not in data["system_msg"]
    for value in ("Turn to replace:", ORIGINAL_TURN, "Model thoughts:", THOUGHTS, "Feedback:", FEEDBACK):
        assert value in data["user_msg"]
    finish = feedback_app.post(f"/story/{STORY}/local-finish", json={
        "turn_token": data["turn_token"], "text": "Mira waited for an explanation.",
        "user_input": ORIGINAL_PROMPT, "model": "local-model", "regeneration": context,
        "model_thoughts": "<thought>Take time to decide.</thought>",
    })
    assert finish.json()["saved"] is True
    entry = json.loads((folder / "chat_log.json").read_text(encoding="utf-8"))[-1]
    assert entry["model_thoughts"] == "<thought>Take time to decide.</thought>"
    assert FEEDBACK not in (folder / "story.md").read_text(encoding="utf-8")


def test_local_failure_preserves_feedback(feedback_app, configured_user):
    seed_turn(configured_user)
    context = prepare(feedback_app)["regeneration"]
    data = feedback_app.post(f"/story/{STORY}/local-begin", json={"user_input": ORIGINAL_PROMPT, "regeneration": context}).json()
    result = feedback_app.post(f"/story/{STORY}/local-finish", json={
        "turn_token": data["turn_token"], "user_input": ORIGINAL_PROMPT,
        "error": "Local model unavailable", "regeneration": context,
    })
    assert result.json()["saved"] is False
    assert main.read_pending_retry(STORY, configured_user["uid"])["regeneration"] == context
