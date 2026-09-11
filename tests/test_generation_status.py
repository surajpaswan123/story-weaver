import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import main
from runtime_support import TurnProgress


@pytest.fixture
def status_app(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'STORIES_DIR', str(tmp_path))
    monkeypatch.setattr(main, 'db_conn_str', '')
    monkeypatch.setattr(main, 'db_firestore', None)
    monkeypatch.setattr(main, '_active_story_turns', {})
    monkeypatch.setattr(main, '_turn_progress', TurnProgress())
    user = {'uid': 'status-user', 'is_super_admin': False}
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: user
    main.app.dependency_overrides[main.get_current_user_id] = lambda: user['uid']
    with TestClient(main.app) as client:
        yield client, user
    main.app.dependency_overrides.clear()


def event(kind, **fields):
    return 'data: ' + json.dumps({'type': kind, **fields}) + '\n\n'


def test_disconnected_reader_keeps_running_and_reopened_story_gets_saved_result(status_app):
    client, user = status_app
    story, uid = 'story', user['uid']
    token = main.begin_story_turn(story, uid)
    main.append_chat_entry(story, 'user', 'Continue.', uid=uid)
    release, saved = threading.Event(), threading.Event()
    def worker():
        yield event('chunk', text='A beginning.')
        release.wait(10)
        main.commit_ai_turn(story, 'A complete saved turn.', 'mock-model', uid=uid)
        yield event('finalizing')
        yield event('done')
        saved.set()
    stream = main._relay_stream(main.tracked_story_stream(worker(), story, uid, token))
    try:
        next(stream)
        stream.close()  # The laptop/browser connection disappeared.
        response = client.get('/story/story/generation-status')
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        running = response.json()
        assert running['active'] is True and running['state'] == 'generating'
        assert token not in response.text and 'token' not in response.text
        assert client.get('/story/story/chat').json()['generation']['active'] is True
        release.set()
        assert saved.wait(10)
        for _ in range(100):
            result = client.get('/story/story/generation-status').json()
            if not result['active']:
                break
            time.sleep(0.01)
        assert result['state'] == 'completed' and result['run_id'] == running['run_id']
        assert client.get('/story/story/chat').json()['messages'][-1]['text'] == 'A complete saved turn.'
    finally:
        release.set()
        stream.close()


def test_status_is_account_scoped_and_does_not_restore_cloud_files(status_app, monkeypatch):
    client, user = status_app
    token = main.begin_story_turn('same-story', user['uid'])
    monkeypatch.setattr(main, 'restore_story_directory_from_firestore', lambda *args: pytest.fail('Status must not download story files'))
    assert client.get('/story/same-story/generation-status').json()['active'] is True
    user['uid'] = 'another-user'
    assert client.get('/story/same-story/generation-status').json() == {'active': False, 'state': 'idle', 'run_id': ''}
    main.end_story_turn('same-story', 'status-user', token)


@pytest.mark.parametrize('kind,state', [('done', 'completed'), ('error', 'failed'), ('stopped', 'stopped')])
def test_terminal_status_is_reported_only_after_worker_finalization(status_app, kind, state):
    client, user = status_app
    token = main.begin_story_turn('story', user['uid'])
    def worker():
        yield event(kind)
        during_cleanup = client.get('/story/story/generation-status').json()
        assert during_cleanup['active'] is True and during_cleanup['state'] == 'finalizing'
    list(main.tracked_story_stream(worker(), 'story', user['uid'], token))
    result = client.get('/story/story/generation-status').json()
    assert result['active'] is False and result['state'] == state


def test_running_worker_does_not_expire_during_long_model_wait(status_app):
    client, user = status_app
    uid = user['uid']
    token = main.begin_story_turn('story', uid)
    stream = main.tracked_story_stream(iter([event('retrying'), event('done')]), 'story', uid, token)
    try:
        next(stream)
        key = main._stop_key('story', uid)
        main._active_story_turns[key] = (token, time.time() - main.STORY_TURN_TTL_SECONDS - 1)
        assert client.get('/story/story/generation-status').json()['state'] == 'retrying'
        with pytest.raises(main.HTTPException) as error:
            main.begin_story_turn('story', uid)
        assert error.value.status_code == 409
    finally:
        stream.close()


def test_expired_browser_reservation_is_interrupted_and_not_claimed_as_server_work(status_app):
    client, user = status_app
    token = main.begin_story_turn('story', user['uid'], execution='browser')
    status = client.get('/story/story/generation-status').json()
    assert status['execution'] == 'browser' and status['active'] is True
    main._active_story_turns[main._stop_key('story', user['uid'])] = (token, 0)
    status = client.get('/story/story/generation-status').json()
    assert status['active'] is False and status['state'] == 'interrupted'


def test_old_worker_cannot_change_new_turn_status(status_app):
    client, user = status_app
    uid = user['uid']
    old = main.begin_story_turn('story', uid)
    main.end_story_turn('story', uid, old)
    new = main.begin_story_turn('story', uid)
    main._turn_progress.update(main._stop_key('story', uid), old, outcome='failed')
    main.end_story_turn('story', uid, old)
    result = client.get('/story/story/generation-status').json()
    assert result['active'] is True and result['state'] == 'starting'
    main.end_story_turn('story', uid, new)


def test_finished_status_records_are_bounded_and_do_not_store_generated_text():
    progress = TurnProgress(max_finished=3)
    for index in range(10):
        key, token = ('user', str(index)), 'token-' + str(index)
        progress.start(key, token)
        list(progress.track(key, token, [event('chunk', text='private story text'), event('done')]))
        progress.finish(key, token)
    assert len(progress.records) == 3
    assert 'private story text' not in repr(progress.records)
