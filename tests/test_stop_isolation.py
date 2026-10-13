"""Regression tests for run-scoped cancellation and delayed worker cleanup."""

import asyncio
import threading
import time

import pytest

import main
from test_generation_status import status_app


def test_stop_requires_matching_run_and_keeps_story_locked(status_app, monkeypatch):
    client, user = status_app
    story, uid = 'stop-scope', user['uid']
    token = main.begin_story_turn(story, uid)
    run_id = main._run_id_for_token(token)
    main.append_chat_entry(story, 'user', 'Do not lose this prompt.', uid=uid)
    monkeypatch.setattr(main, 'restore_story_directory_from_firestore',
                        lambda *args: pytest.fail('Stop must not reload story files'))
    monkeypatch.setattr(main, 'sync_story_directory_to_firestore',
                        lambda *args: pytest.fail('Stop must not save before worker exits'))

    try:
        assert client.post(f'/story/{story}/stop').status_code == 400
        assert client.post(f'/story/{story}/stop', json={'run_id': 'wrong'}).status_code == 409
        assert not main.stop_requested(story, uid, token)
        response = client.post(f'/story/{story}/stop', json={'run_id': run_id})
        assert response.status_code == 200
        assert response.json()['stopping'] is True
        assert main.stop_requested(story, uid, token)
        assert client.get(f'/story/{story}/generation-status').json()['active'] is True
        with pytest.raises(main.HTTPException) as error:
            main.begin_story_turn(story, uid)
        assert error.value.status_code == 409
        assert main.get_chat_log_path(story, uid=uid)
        assert client.get(f'/story/{story}/chat').json()['messages'][-1]['role'] == 'user'
    finally:
        main.end_story_turn(story, uid, token)
    assert not main.stop_requested(story, uid, token)


def test_stale_stop_cannot_cancel_next_generation(status_app):
    client, user = status_app
    story, uid = 'successor', user['uid']
    old = main.begin_story_turn(story, uid)
    old_run = main._run_id_for_token(old)
    assert client.post(f'/story/{story}/stop', json={'run_id': old_run}).status_code == 200
    main.end_story_turn(story, uid, old)
    new = main.begin_story_turn(story, uid)
    try:
        new_run = main._run_id_for_token(new)
        assert new_run != old_run
        assert client.post(f'/story/{story}/stop', json={'run_id': old_run}).status_code == 409
        assert not main.stop_requested(story, uid, new)
        assert main.current_generation_status(story, uid)['run_id'] == new_run
    finally:
        main.end_story_turn(story, uid, new)


def test_stop_is_rejected_once_commit_begins(status_app):
    client, user = status_app
    story, uid = 'finalizing', user['uid']
    token = main.begin_story_turn(story, uid)
    try:
        main._turn_progress.update(main._stop_key(story, uid), token, state='finalizing')
        result = client.post(f'/story/{story}/stop',
                             json={'run_id': main._run_id_for_token(token)})
        assert result.status_code == 409
        assert not main.stop_requested(story, uid, token)
    finally:
        main.end_story_turn(story, uid, token)


def test_provider_open_late_after_stop_cleans_only_dangling_prompt(status_app, monkeypatch):
    client, user = status_app
    story, uid = 'late-model', user['uid']
    main.save_user_keys(uid, {'nvidia_api_key': 'test-only-key'})
    monkeypatch.setattr(main, 'has_any_generation_provider', lambda *args, **kwargs: True)
    entered, release = threading.Event(), threading.Event()

    def delayed_provider(*args, **kwargs):
        entered.set()
        assert release.wait(10), 'Release the blocked provider after requesting Stop'
        return iter([main.GenericChunk('This should not be saved.')]), 'nvidia/test', True

    monkeypatch.setattr(main, 'stream_with_fallback', delayed_provider)
    response = asyncio.run(main.generate_story(
        main.StoryInput(story_id=story, user_input='Continue.', provider='nvidia',
                        model='z-ai/glm-5.3', skip_rules_check=True),
        main.BackgroundTasks(), user))
    try:
        assert entered.wait(10), 'Writer must reach provider opening'
        run_id = main.current_generation_status(story, uid)['run_id']
        assert response.headers['X-Story-Run-Id'] == run_id
        assert client.post(f'/story/{story}/stop', json={'run_id': run_id}).status_code == 200
        release.set()
        for _ in range(200):
            status = main.current_generation_status(story, uid)
            if not status['active']:
                break
            time.sleep(0.02)
        assert not status['active'] and status['state'] == 'stopped'
        history = client.get(f'/story/{story}/chat').json()['messages']
        assert not history or history[-1]['role'] != 'user'
        assert 'This should not be saved.' not in main.get_recent_story_text(story, uid=uid)
    finally:
        release.set()
        response.detached.set()
