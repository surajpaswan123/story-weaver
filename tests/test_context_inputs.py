import json
from pathlib import Path

import pytest

import main
from test_responses import configured_user
from test_feedback_regeneration import feedback_app


DIAGNOSTIC = "DIAGNOSTIC_ONLY_Contradictions_are_not_story_canon"
INCIDENT = "CANON_EVENT_Mira_reached_the_river"
MANUSCRIPT = "MANUSCRIPT_BEGIN\n" + ("The river carried her voice.\n" * 4000) + "MANUSCRIPT_END"


def seed(user):
    folder = Path(main.get_story_dir("context-test", uid=user["uid"]))
    for name, text in {"consistency.md": DIAGNOSTIC, "Consistency.md": DIAGNOSTIC,
                       "incidents.md": INCIDENT, "story.md": MANUSCRIPT,
                       "summary.md": "SUMMARY_MARKER", "factions.md": "CUSTOM_CATEGORY_MARKER"}.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def assert_context(prompt):
    assert DIAGNOSTIC not in prompt
    assert "CONSISTENCY NOTES" not in prompt
    assert INCIDENT in prompt
    assert MANUSCRIPT in prompt
    assert "SUMMARY_MARKER" in prompt
    assert "CUSTOM_CATEGORY_MARKER" in prompt


@pytest.mark.parametrize("flow", ["local", "hosted", "audio"])
def test_writer_flows_exclude_diagnostics_and_keep_full_context(flow, feedback_app, configured_user, monkeypatch):
    folder = seed(configured_user)
    captured = []
    def stream(system, user, **kwargs):
        captured.append(system + "\n" + user)
        return iter([main.GenericChunk("Mira followed the river.")]), "mock-model", False
    monkeypatch.setattr(main, "stream_with_fallback", stream)
    monkeypatch.setattr(main, "analyze_media_only", lambda *a, **kw: "An instrumental song.")
    monkeypatch.setattr(main, "background_analysis", lambda *a, **kw: None)
    if flow == "local":
        result = feedback_app.post("/story/context-test/local-begin", json={"user_input": "Continue."})
        assert result.status_code == 200
        data = result.json()
        captured.append(data["system_msg"] + "\n" + data["user_msg"])
        assert feedback_app.post("/story/context-test/local-turn-end", json={"turn_token": data["turn_token"]}).status_code == 200
    elif flow == "hosted":
        result = feedback_app.post("/generate", json={"story_id": "context-test", "user_input": "Continue.",
            "provider": "openai", "model": "mock-model", "skip_rules_check": True})
    else:
        result = feedback_app.post("/generate-audio", data={"story_id": "context-test", "user_input": "Continue.", "skip_rules_check": "true"},
                                  files={"audio": ("test.mp3", b"mock audio", "audio/mpeg")})
    assert result.status_code == 200
    assert len(captured) == 1
    assert_context(captured[0])
    assert (folder / "consistency.md").read_text(encoding="utf-8") == DIAGNOSTIC
    # Keep the user's diagnostic log accessible in the file editor.
    files = feedback_app.get("/story/context-test/files").json()
    assert "consistency.md" in json.dumps(files)


def test_category_discovery_and_background_inputs_exclude_diagnostics(configured_user, monkeypatch):
    folder = seed(configured_user)
    captured = []
    def complete(system_prompt, user_prompt, **kwargs):
        captured.append(user_prompt)
        return "[]", "mock-model"
    monkeypatch.setattr(main, "run_user_task_completion", complete)
    categories = main._discover_custom_categories("context-test", configured_user["uid"])
    assert "consistency" not in [c.casefold() for c in categories]
    assert main.auto_spawn_categories(str(folder), "New excerpt.", set(categories), user_info=configured_user) == []
    assert_context(captured[0])
    prompt = main._build_background_analysis_prompt("context-test", configured_user["uid"], MANUSCRIPT, "New excerpt.", categories)
    assert DIAGNOSTIC not in prompt
    assert INCIDENT in prompt
    assert MANUSCRIPT in prompt
