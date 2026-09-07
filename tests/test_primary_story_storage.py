import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import main


class Postgres:
    """Transactional test double; unexpected SQL fails instead of hitting a service."""
    def __init__(self):
        self.rows = {}
        self.connections = []
        self.fail_connect = self.fail_commit = False

    def seed(self, name, text, timestamp=20.0, title=None, story="test"):
        self.rows[("storage-user", story, name)] = (text, timestamp, title)

    def connect(self, *args, **kwargs):
        if self.fail_connect:
            raise RuntimeError("Postgres unavailable")
        database = self
        class Connection:
            def __init__(self):
                self.rows = dict(database.rows)
                self.closed = False
                self.result = []
            def cursor(self):
                return self
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def execute(self, sql, params):
                sql = " ".join(sql.split())
                if "pg_advisory_xact_lock" in sql:
                    self.result = []
                elif sql.startswith("INSERT INTO user_stories"):
                    uid, story, name, text, timestamp, title = params
                    old = self.rows.get((uid, story, name), (None, None, None))
                    self.rows[(uid, story, name)] = (text, timestamp, title or old[2])
                elif sql.startswith("DELETE FROM user_stories"):
                    self.rows.pop(tuple(params), None)
                elif sql.startswith("SELECT story_id, MAX(title)"):
                    assert "OCTET_LENGTH(content)" in sql
                    groups = {}
                    for (uid, story, _), row in self.rows.items():
                        if uid == params[0]:
                            groups.setdefault(story, []).append(row)
                    self.result = [(story, next((r[2] for r in rows if r[2]), None), max(r[1] for r in rows),
                                    sum(len(r[0].encode("utf-8")) for r in rows)) for story, rows in groups.items()]
                elif sql.startswith("SELECT ") and "FROM user_stories" in sql:
                    rows = [(name, *value) for (uid, story, name), value in self.rows.items() if (uid, story) == params]
                    if sql.startswith("SELECT 1 "):
                        self.result = [(1,)] if rows else []
                    elif sql.startswith("SELECT file_name FROM"):
                        self.result = [(r[0],) for r in rows]
                    else:
                        self.result = rows
                else:
                    raise AssertionError(f"Unexpected SQL: {sql}")
            def executemany(self, sql, values):
                for params in values:
                    self.execute(sql, params)
            def fetchall(self):
                return self.result
            def fetchone(self):
                return self.result[0] if self.result else None
            def commit(self):
                if database.fail_commit:
                    raise RuntimeError("Commit failed")
                database.rows = dict(self.rows)
            def close(self):
                self.closed = True
        connection = Connection()
        self.connections.append(connection)
        return connection


class Firestore:
    def __init__(self):
        self.gets = 0
        self.lists = 0
        self.docs = {"test": {"updated_at": 9999999999.0, "title": "Old Firestore title", "files": {"story_md": "Old Firestore story"}}}
    def collection(self, _):
        return self
    def document(self, name):
        self.name = name
        return self
    def get(self):
        self.gets += 1
        data = self.docs.get(self.name)
        return SimpleNamespace(exists=data is not None, to_dict=lambda: data)
    def stream(self):
        self.lists += 1
        return [SimpleNamespace(id=name, to_dict=lambda data=data: data) for name, data in self.docs.items()]
    def set(self, *args, **kwargs):
        raise AssertionError("Configured Postgres must not write a Firestore story")
    update = set


@pytest.fixture
def storage(tmp_path, monkeypatch):
    pg, fs = Postgres(), Firestore()
    monkeypatch.setattr(main, "STORIES_DIR", str(tmp_path))
    monkeypatch.setattr(main, "db_conn_str", "test-postgres")
    monkeypatch.setattr(main, "postgres_active", False)  # A failed startup check must not change authority.
    monkeypatch.setattr(main, "db_firestore", fs)
    monkeypatch.setattr(main, "_active_story_turns", {})
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=pg.connect))
    folder = tmp_path / "storage-user" / "test"
    yield pg, fs, folder
    assert all(connection.closed for connection in pg.connections)


def test_large_complete_snapshot_saves_only_to_postgres_and_removes_stale_files(storage):
    pg, fs, folder = storage
    folder.mkdir(parents=True)
    text = "क" * 500_000  # More than Firestore's document limit in UTF-8 bytes.
    (folder / "story.md").write_text(text, encoding="utf-8")
    (folder / "chat_log.json").write_text(json.dumps([{"role": "ai", "text": "Turn", "model_thoughts": "<thought>Plan</thought>"}]), encoding="utf-8")
    for number in range(12):
        (folder / f"category_{number}.md").write_text("Reference", encoding="utf-8")
    pg.seed("removed.md", "stale")
    assert main.sync_story_directory_to_firestore("storage-user", "test") is True
    assert len(pg.rows) == 14
    assert pg.rows[("storage-user", "test", "story.md")][0] == text
    assert fs.gets == 0
    state = main._story_sync_state(str(folder))
    assert state["storage"] == "postgres" and not state.get("pending_upload")


def test_cold_restore_and_legacy_read_helper_use_postgres_even_with_newer_firestore(storage):
    pg, fs, folder = storage
    pg.seed("story.md", "Current Postgres story")
    pg.seed("chat_log.json", '[{"role":"ai","text":"Current","model_thoughts":"<thought>Saved</thought>"}]')
    assert main.get_story_from_firestore("storage-user", "test", "story.md") == "Current Postgres story"
    assert "Saved" in (folder / "chat_log.json").read_text(encoding="utf-8")
    assert fs.gets == 0


def test_old_firestore_cache_timestamp_cannot_block_primary_restore_or_resurrect_removed_files(storage):
    pg, fs, folder = storage
    folder.mkdir(parents=True)
    (folder / "story.md").write_text("Cached Firestore story", encoding="utf-8")
    (folder / "removed.md").write_text("stale", encoding="utf-8")
    main._write_story_sync_timestamp(str(folder), 9999999999.0)
    pg.seed("story.md", "Postgres owns this story", timestamp=10)
    main.restore_story_directory_from_firestore("storage-user", "test")
    assert (folder / "story.md").read_text(encoding="utf-8") == "Postgres owns this story"
    assert not (folder / "removed.md").exists()
    assert fs.gets == 0


@pytest.mark.parametrize("cached", [False, True])
def test_postgres_outage_never_falls_back_to_firestore(storage, cached):
    pg, fs, folder = storage
    pg.fail_connect = True
    if cached:
        folder.mkdir(parents=True)
        (folder / "story.md").write_text("Local work", encoding="utf-8")
        main.restore_story_directory_from_firestore("storage-user", "test")
        assert (folder / "story.md").read_text(encoding="utf-8") == "Local work"
    else:
        with pytest.raises(main.HTTPException) as error:
            main.restore_story_directory_from_firestore("storage-user", "test")
        assert error.value.status_code == 503
        assert not folder.exists()
    assert fs.gets == 0


def test_failed_transaction_keeps_new_local_work_and_retry_saves_it(storage):
    pg, fs, folder = storage
    folder.mkdir(parents=True)
    pg.seed("story.md", "Old saved story")
    pg.seed("removed.md", "Still remote until commit succeeds")
    original_rows = dict(pg.rows)
    (folder / "story.md").write_text("New unsynced work", encoding="utf-8")
    pg.fail_commit = True
    assert main.sync_story_directory_to_firestore("storage-user", "test") is False
    assert pg.rows == original_rows
    assert main._story_sync_state(str(folder))["pending_upload"] is True
    main.restore_story_directory_from_firestore("storage-user", "test")
    assert (folder / "story.md").read_text(encoding="utf-8") == "New unsynced work"
    pg.fail_commit = False
    assert main.sync_story_directory_to_firestore("storage-user", "test") is True
    assert pg.rows[("storage-user", "test", "story.md")][0] == "New unsynced work"
    assert ("storage-user", "test", "removed.md") not in pg.rows
    assert not main._story_sync_state(str(folder)).get("pending_upload")
    assert fs.gets == 0


def test_firestore_only_story_migrates_once_with_title_and_all_files(storage):
    pg, fs, folder = storage
    fs.docs["test"]["files"]["chat_log_json"] = "[]"
    fs.docs["test"]["files"]["../escape_md"] = "invalid path"
    main.restore_story_directory_from_firestore("storage-user", "test")
    assert set(name for _, _, name in pg.rows) == {"story.md", "chat_log.json"}
    assert pg.rows[("storage-user", "test", "story.md")][2] == "Old Firestore title"
    assert (folder / "story.md").read_text(encoding="utf-8") == "Old Firestore story"
    assert fs.gets == 1
    main.restore_story_directory_from_firestore("storage-user", "test")
    assert fs.gets == 1


def test_migration_cannot_overwrite_an_existing_postgres_story(storage):
    pg, fs, _ = storage
    pg.seed("story.md", "Created by another request")
    assert main._write_postgres_story("storage-user", "test", {"story.md": "Legacy"}, only_if_absent=True) is None
    assert pg.rows[("storage-user", "test", "story.md")][0] == "Created by another request"


def test_failed_legacy_import_does_not_present_unsaved_legacy_data_as_primary(storage):
    pg, fs, folder = storage
    pg.fail_commit = True
    with pytest.raises(main.HTTPException) as error:
        main.restore_story_directory_from_firestore("storage-user", "test")
    assert error.value.status_code == 503
    assert pg.rows == {} and not folder.exists()


def test_empty_cache_listing_during_postgres_outage_does_not_show_stale_firestore(storage):
    pg, fs, _ = storage
    pg.fail_connect = True
    with pytest.raises(main.HTTPException) as error:
        asyncio.run(main.list_stories("storage-user"))
    assert error.value.status_code == 503
    assert fs.lists == 0


def test_story_listing_prefers_postgres_title_and_utf8_size(storage):
    pg, fs, _ = storage
    pg.seed("story.md", "कहानी", title="Primary title")
    fs.docs["legacy"] = {"files": {"story_md": "Legacy"}, "title": "Legacy title"}
    stories = asyncio.run(main.list_stories("storage-user"))["stories"]
    assert next(story for story in stories if story["id"] == "test")["name"] == "Primary title"
    assert next(story for story in stories if story["id"] == "test")["size"] == len("कहानी".encode("utf-8"))
    assert {story["id"] for story in stories} == {"test", "legacy"}


def test_create_saves_initial_files_and_cold_duplicate_cannot_overwrite_primary(storage):
    pg, fs, _ = storage
    user = {"uid": "storage-user"}
    result = asyncio.run(main.create_story(main.CreateStoryInput(name="New story"), user))
    created = {name for _, story, name in pg.rows if story == result["id"]}
    assert "story.md" in created and len(created) > 1
    pg.seed("story.md", "Existing manuscript", story="existing")
    with pytest.raises(main.HTTPException) as error:
        asyncio.run(main.create_story(main.CreateStoryInput(name="existing"), user))
    assert error.value.status_code == 409
    assert pg.rows[("storage-user", "existing", "story.md")][0] == "Existing manuscript"
