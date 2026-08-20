import json
import asyncio
import base64
import threading
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main


@pytest.fixture
def isolated_stories(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORIES_DIR", str(tmp_path))
    return tmp_path


def test_default_user_never_treats_a_user_namespace_as_a_legacy_story(isolated_stories):
    user_namespace = isolated_stories / "alice"
    user_namespace.mkdir()
    (user_namespace / "user_keys.json").write_text("{}", encoding="utf-8")

    resolved = Path(main.get_story_dir("alice", uid="default_user", create=False))

    assert resolved == isolated_stories / "default_user" / "alice"


def test_real_legacy_story_is_still_readable(isolated_stories):
    legacy_story = isolated_stories / "old-adventure"
    legacy_story.mkdir()
    (legacy_story / "story.md").write_text("Once upon a time", encoding="utf-8")

    resolved = Path(main.get_story_dir("old-adventure", uid="default_user", create=False))

    assert resolved == legacy_story


def test_snapshot_restores_all_reference_markdown_and_removes_new_files(isolated_stories):
    story_dir = Path(main.get_story_dir("snapshot-test", uid="user-1"))
    originals = {
        "summary.md": "old summary",
        "consistency.md": "old consistency",
        "relationships.md": "old relationships",
    }
    for name, content in originals.items():
        (story_dir / name).write_text(content, encoding="utf-8")

    main.save_snapshot("snapshot-test", uid="user-1")

    for name in originals:
        (story_dir / name).write_text("changed", encoding="utf-8")
    (story_dir / "new-category.md").write_text("created during analysis", encoding="utf-8")

    main.restore_snapshot("snapshot-test", uid="user-1")

    for name, content in originals.items():
        assert (story_dir / name).read_text(encoding="utf-8") == content
    assert not (story_dir / "new-category.md").exists()


def test_concurrent_chat_appends_do_not_drop_entries(isolated_stories):
    count = 40
    threads = [
        threading.Thread(
            target=main.append_chat_entry,
            args=("concurrent-story", "user", f"message-{index}"),
            kwargs={"uid": "user-1"},
        )
        for index in range(count)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    path = Path(main.get_chat_log_path("concurrent-story", uid="user-1"))
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert len(entries) == count
    assert {entry["text"] for entry in entries} == {f"message-{index}" for index in range(count)}


def test_ai_turn_commit_rolls_story_back_if_chat_write_fails(isolated_stories, monkeypatch):
    story_path = Path(main.get_story_path("rollback-story", uid="user-1"))
    story_path.write_text("original story", encoding="utf-8")
    main.append_chat_entry("rollback-story", "user", "continue", uid="user-1")

    def fail_chat_write(_path, _value, **_kwargs):
        raise OSError("simulated chat write failure")

    monkeypatch.setattr(main, "_atomic_write_json", fail_chat_write)

    with pytest.raises(OSError):
        main.commit_ai_turn("rollback-story", "new response", "test-model", uid="user-1")

    assert story_path.read_text(encoding="utf-8") == "original story"
    chat_path = Path(main.get_chat_log_path("rollback-story", uid="user-1"))
    entries = json.loads(chat_path.read_text(encoding="utf-8"))
    assert [entry["role"] for entry in entries] == ["user"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/v1",
        "https://localhost/v1",
        "https://10.0.0.5/v1",
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:password@example.com/v1",
    ],
)
def test_server_side_openai_base_url_blocks_private_or_unsafe_targets(url):
    with pytest.raises(ValueError):
        main.validate_openai_base_url(url)


def test_official_openai_base_url_is_allowed():
    assert main.validate_openai_base_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"


def test_custom_openai_client_does_not_follow_redirects():
    client = main._clients_from_keys({
        "openai_api_key": "not-a-real-key",
        "openai_base_url": "https://api.openai.com/v1",
    })["openai_client"]

    assert client is not None
    assert client._client.follow_redirects is False


def test_proxy_identity_uses_cloudflare_header_or_rightmost_forwarded_address(monkeypatch):
    class Client:
        host = "10.0.0.8"

    class Request:
        client = Client()

        def __init__(self, headers):
            self.headers = headers

    monkeypatch.setattr(main, "TRUST_PROXY_HEADERS", True)

    assert main._get_client_ip(Request({"x-forwarded-for": "1.2.3.4, 203.0.113.10"})) == "203.0.113.10"
    assert main._get_client_ip(Request({
        "x-forwarded-for": "1.2.3.4, 203.0.113.10",
        "cf-connecting-ip": "198.51.100.25",
    })) == "198.51.100.25"


def test_hosted_runtime_detection_fails_closed_for_local_auth_fallbacks(monkeypatch):
    assert main._is_public_deployment_environment({"RENDER_SERVICE_ID": "srv-example"}) is True
    assert main._is_public_deployment_environment({"PORT": "10000"}) is True
    assert main._is_public_deployment_environment({}) is False

    monkeypatch.setenv("ALLOW_LOCAL_SUPER_ADMIN", "true")
    monkeypatch.setattr(main, "IS_PUBLIC_DEPLOYMENT", True)
    hosted = main.get_current_user_info(authorization=None)
    assert hosted["is_guest"] is True
    assert hosted["is_super_admin"] is False

    monkeypatch.setattr(main, "IS_PUBLIC_DEPLOYMENT", False)
    local = main.get_current_user_info(authorization=None)
    assert local["is_guest"] is False
    assert local["is_super_admin"] is True


def test_forged_admin_jwt_is_treated_as_guest_when_firebase_is_active(monkeypatch):
    forged_payload = base64.urlsafe_b64encode(json.dumps({
        "sub": "attacker",
        "email": main.SUPER_ADMIN_EMAIL,
    }).encode()).decode().rstrip("=")
    forged_token = f"header.{forged_payload}.signature"

    class FirebaseAuth:
        @staticmethod
        def verify_id_token(_token):
            raise ValueError("invalid signature")

    monkeypatch.setattr(main, "firebase_initialized", True)
    monkeypatch.setattr(main, "ALLOW_UNVERIFIED_JWT", False)
    monkeypatch.setattr(main, "auth", FirebaseAuth())

    result = main.get_current_user_info(authorization=f"Bearer {forged_token}")

    assert result["is_guest"] is True
    assert result["is_super_admin"] is False
    assert result["email"] == ""


def test_provider_availability_uses_the_requesting_users_clients(monkeypatch):
    marker = object()
    monkeypatch.setattr(main, "get_effective_ai_clients", lambda _: {"openai_client": marker})

    assert main.has_any_generation_provider({"uid": "user-1", "is_super_admin": False})


def test_media_analysis_does_not_fall_back_to_global_admin_clients(monkeypatch):
    called = {"global": False}

    class ShouldNotRun:
        class Models:
            def generate_content(self, **_kwargs):
                called["global"] = True
                raise RuntimeError("global/admin client was used for a standard user")

        models = Models()

    monkeypatch.setattr(main, "clients", [ShouldNotRun()])
    monkeypatch.setattr(main, "nokey_client", ShouldNotRun())
    monkeypatch.setattr(main, "get_effective_ai_clients", lambda _: {"genai_clients": [], "nokey_client": None})

    result = main.analyze_media_only(
        b"not-real-audio",
        "audio/wav",
        "sample.wav",
        user_info={"uid": "standard-user", "is_super_admin": False},
    )

    assert result.startswith("[Media analysis unavailable")
    assert called["global"] is False


def test_rules_editor_discards_partial_output_before_fallback(monkeypatch):
    class Chunk:
        class Choice:
            class Delta:
                content = "partial-broken-output"

            delta = Delta()

        choices = [Choice()]

    class BrokenStream:
        def __iter__(self):
            yield Chunk()
            raise RuntimeError("provider disconnected")

    class Completions:
        @staticmethod
        def create(**_kwargs):
            return BrokenStream()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    monkeypatch.setattr(
        main,
        "get_effective_ai_clients",
        lambda _: {
            "is_super_admin": False,
            "genai_clients": [],
            "nvidia_client": Client(),
            "nokey_client": None,
        },
    )
    monkeypatch.setattr(main, "load_user_keys", lambda _uid: {"rules_model": "configured-model"})
    monkeypatch.setattr(main, "run_user_task_completion", lambda **_kwargs: ("clean-fallback", "Fallback/model"))

    output = "".join(
        main.refine_with_rules_stream(
            "original story",
            "rule text",
            "style text",
            user_info={"uid": "standard-user", "is_super_admin": False},
        )
    )

    assert output == "clean-fallback"


def test_logs_are_super_admin_only(monkeypatch):
    monkeypatch.setattr(main, "firebase_initialized", True)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.get_server_logs({"uid": "user-1", "is_super_admin": False, "is_guest": False}))
    assert exc.value.status_code == 403


def test_main_entrypoint_is_after_all_route_definitions():
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert source.rfind('if __name__ == "__main__":') > source.rfind('@app.get("/api/logs")')


def test_live_probe_failures_are_rejected_at_the_api_boundary(isolated_stories, monkeypatch):
    monkeypatch.setattr(main, "firebase_initialized", True)
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "postgres_active", False)
    client = TestClient(main.app)

    assert client.get("/api/logs").status_code == 403
    assert client.post("/api/user/settings", json={"openai_base_url": "http://127.0.0.1/v1"}).status_code == 403
    assert client.post("/stories/create", json={"name": "guest-probe"}).status_code == 403
    assert client.delete("/story/guest-probe").status_code == 403
    assert client.post("/story/guest-probe/undo").status_code == 403
    assert client.post("/story/guest-probe/retry").status_code == 403
    assert client.put("/story/guest-probe/rules", json={"text": "guest write"}).status_code == 403

    signed_user = {"uid": "signed-user", "email": "user@example.com", "is_guest": False, "is_super_admin": False}
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: signed_user
    try:
        created = client.post("/stories/create", json={"name": "codex-api-probe"})
        duplicate = client.post("/stories/create", json={"name": "codex-api-probe"})
        oversized = client.post("/stories/create", json={"name": "x" * 600})
        unsafe_settings = client.post("/api/user/settings", json={
            "openai_api_key": "not-a-real-key",
            "openai_base_url": "http://127.0.0.1/v1",
        })
        huge_key = client.post("/api/user/settings", json={"openai_api_key": "k" * 5000})
    finally:
        main.app.dependency_overrides.clear()

    assert created.status_code == 200
    assert duplicate.status_code == 409
    assert oversized.status_code == 422
    assert unsafe_settings.status_code == 422
    assert huge_key.status_code == 422


def test_guest_settings_never_return_saved_secrets(isolated_stories, monkeypatch):
    monkeypatch.setattr(main, "firebase_initialized", True)
    guest_uid = main._ip_to_guest_uid("testclient")
    key_file = Path(main.get_user_keys_file(guest_uid))
    key_file.write_text(json.dumps({"local_api_key": "should-never-leak"}), encoding="utf-8")
    client = TestClient(main.app)

    response = client.get("/api/user/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_guest"] is True
    assert payload["masked_keys"] == {}
    assert payload["local_api_key_full"] == ""


def test_api_keys_are_preserved_on_blank_update_and_only_removed_explicitly(isolated_stories, monkeypatch):
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "postgres_active", False)

    main.save_user_keys("user-1", {"openai_api_key": "secret-value"})
    preserved = main.save_user_keys("user-1", {"openai_api_key": ""})
    cleared = main.save_user_keys("user-1", {}, clear_keys=["openai_api_key"])

    assert preserved["openai_api_key"] == "secret-value"
    assert cleared["openai_api_key"] == ""


def test_local_audio_upload_has_size_and_media_type_limits(isolated_stories, monkeypatch):
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "postgres_active", False)
    monkeypatch.setattr(main, "MAX_AUDIO_BYTES", 8)
    signed_user = {"uid": "signed-user", "email": "user@example.com", "is_guest": False, "is_super_admin": False}
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: signed_user
    client = TestClient(main.app)
    try:
        too_large = client.post(
            "/story/audio-probe/local-audio-begin",
            files={"audio": ("sample.wav", b"123456789", "audio/wav")},
            data={"user_input": "listen"},
        )
        wrong_type = client.post(
            "/story/audio-probe/local-audio-begin",
            files={"audio": ("sample.txt", b"text", "text/plain")},
            data={"user_input": "listen"},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert too_large.status_code == 413
    assert wrong_type.status_code == 415


def test_windows_reserved_upload_name_is_made_safe():
    assert main.sanitize_filename("CON.wav") == "upload-CON.wav"


def test_newer_cloud_revision_replaces_stale_cache_but_not_new_local_work(isolated_stories, monkeypatch):
    class DocumentSnapshot:
        exists = True

        @staticmethod
        def to_dict():
            return {"updated_at": 20.0, "files": {"story_md": "new cloud story"}}

    class FirestoreChain:
        def collection(self, _name):
            return self

        def document(self, _name):
            return self

        @staticmethod
        def get():
            return DocumentSnapshot()

    monkeypatch.setattr(main, "db_firestore", FirestoreChain())
    monkeypatch.setattr(main, "postgres_active", False)

    story_dir = Path(main.get_story_dir("cloud-story", uid="user-1"))
    (story_dir / "story.md").write_text("stale cache", encoding="utf-8")
    main._write_story_sync_timestamp(str(story_dir), 10.0)

    main.restore_story_directory_from_firestore("user-1", "cloud-story")
    assert (story_dir / "story.md").read_text(encoding="utf-8") == "new cloud story"

    (story_dir / "story.md").write_text("new unsynced local work", encoding="utf-8")
    main.restore_story_directory_from_firestore("user-1", "cloud-story")
    assert (story_dir / "story.md").read_text(encoding="utf-8") == "new unsynced local work"


def test_cloud_sync_replaces_file_map_so_undone_files_do_not_reappear(isolated_stories, monkeypatch):
    state = {
        "updated_at": 1.0,
        "files": {"story_md": "old", "created_during_analysis_md": "stale"},
    }

    class Snapshot:
        exists = True

    class FirestoreDocument:
        def collection(self, _name):
            return self

        def document(self, _name):
            return self

        @staticmethod
        def get():
            return Snapshot()

        @staticmethod
        def update(payload):
            state.update(payload)

        @staticmethod
        def set(payload):
            state.clear()
            state.update(payload)

    monkeypatch.setattr(main, "db_firestore", FirestoreDocument())
    monkeypatch.setattr(main, "postgres_active", False)
    story_dir = Path(main.get_story_dir("cloud-cleanup", uid="user-1"))
    (story_dir / "story.md").write_text("current story", encoding="utf-8")
    (story_dir / "summary.md").write_text("current summary", encoding="utf-8")

    main.sync_story_directory_to_firestore("user-1", "cloud-cleanup")

    assert set(state["files"]) == {"story_md", "summary_md"}


def test_manual_analysis_preserves_not_found_status(isolated_stories):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.trigger_analysis(
            "missing-story",
            {"uid": "signed-user", "is_guest": False, "is_super_admin": False},
        ))
    assert exc.value.status_code == 404


def test_story_turn_reservation_rejects_concurrent_generation():
    token = main.begin_story_turn("busy-story", "user-1")
    try:
        with pytest.raises(HTTPException) as exc:
            main.begin_story_turn("busy-story", "user-1")
        assert exc.value.status_code == 409
    finally:
        main.end_story_turn("busy-story", "user-1", token)


def test_story_turn_reservation_uses_canonical_story_id():
    token = main.begin_story_turn("same/story", "user-1")
    try:
        with pytest.raises(HTTPException) as exc:
            main.begin_story_turn("samestory", "user-1")
        assert exc.value.status_code == 409
    finally:
        main.end_story_turn("same/story", "user-1", token)


def test_local_turn_token_binds_finish_and_mutations_to_original_story(isolated_stories, monkeypatch):
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "postgres_active", False)
    signed_user = {"uid": "signed-user", "email": "user@example.com", "is_guest": False, "is_super_admin": False}
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: signed_user
    client = TestClient(main.app)
    try:
        begin = client.post("/story/original/local-begin", json={"user_input": "continue"})
        assert begin.status_code == 200
        token = begin.json()["turn_token"]

        assert client.post("/story/original/local-begin", json={"user_input": "second tab"}).status_code == 409
        wrong_story_finish = client.post("/story/different/local-finish", json={
            "text": "must not be saved",
            "user_input": "continue",
            "model": "local-test",
            "turn_token": token,
        })
        assert wrong_story_finish.status_code == 409
        assert client.delete("/story/original").status_code == 409
        assert client.put("/story/original/summary", json={"summary": "racing edit"}).status_code == 409

        finish = client.post("/story/original/local-finish", json={
            "text": "saved in the original story",
            "user_input": "continue",
            "model": "local-test",
            "turn_token": token,
        })
        assert finish.status_code == 200
        assert finish.json()["saved"] is True
        assert client.post("/story/original/local-turn-end", json={"turn_token": token}).status_code == 200
    finally:
        main.app.dependency_overrides.clear()
        main.end_story_turn("original", "signed-user", locals().get("token", ""))

    story_path = Path(main.get_story_path("original", uid="signed-user", create=False))
    assert "saved in the original story" in story_path.read_text(encoding="utf-8")
    wrong_path = Path(main.get_story_path("different", uid="signed-user", create=False))
    assert not wrong_path.exists()


def test_two_signed_accounts_with_same_story_name_remain_isolated(isolated_stories, monkeypatch):
    monkeypatch.setattr(main, "db_firestore", None)
    monkeypatch.setattr(main, "postgres_active", False)
    client = TestClient(main.app)

    def use_account(uid):
        user = {"uid": uid, "email": f"{uid}@example.com", "is_guest": False, "is_super_admin": False}
        main.app.dependency_overrides[main.require_authenticated_user] = lambda: user
        main.app.dependency_overrides[main.get_current_user_id] = lambda: uid

    try:
        use_account("account-one")
        assert client.post("/stories/create", json={"name": "shared-title"}).status_code == 200
        assert client.put("/story/shared-title/rules", json={"text": "account one rules"}).status_code == 200

        use_account("account-two")
        assert client.post("/stories/create", json={"name": "shared-title"}).status_code == 200
        assert client.put("/story/shared-title/rules", json={"text": "account two rules"}).status_code == 200
        assert client.get("/story/shared-title/rules").json()["text"] == "account two rules"

        use_account("account-one")
        assert client.get("/story/shared-title/rules").json()["text"] == "account one rules"
    finally:
        main.app.dependency_overrides.clear()
