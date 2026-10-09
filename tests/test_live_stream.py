import asyncio
import gc
import json
import threading
import weakref
from pathlib import Path

import pytest

import main
from live_stream import LiveStreams, StreamJournal
from test_generation_status import status_app, event


def payload(frame):
    cursor = int(frame.splitlines()[0][4:])
    data = next(line[6:] for line in frame.splitlines() if line.startswith('data: '))
    return cursor, json.loads(data)


@pytest.mark.parametrize('provider,model', [('nvidia', 'z-ai/glm-5.3'),
                                          ('openai', 'antigravity-gemini-3.8-flash-high')])
def test_reopen_writer_rules_and_memory_follows_one_provider_call(status_app, monkeypatch, provider, model):
    client, user = status_app
    uid, story = user['uid'], 'live-story'
    folder = Path(main.get_story_dir(story, uid=uid))
    (folder / 'story.md').write_text('The full existing manuscript.', encoding='utf-8')
    (folder / 'rules.md').write_text('Keep the world consistent.', encoding='utf-8')
    main.save_user_keys(uid, {'openai_api_key': 'test-key'})
    monkeypatch.setattr(main, 'has_any_generation_provider', lambda *args, **kwargs: True)
    monkeypatch.setattr(main, 'BATCH_SIZE', 1)
    writer_release, editor_release, memory_release = [threading.Event() for _ in range(3)]
    memory_started = threading.Event()
    requests = []
    thoughts = '<thought>Think carefully about Luna.</thought>'
    draft, edited = 'Luna crossed the river.', 'Luna followed the riverbank.'

    def provider_stream(system, prompt, **kwargs):
        requests.append((system, prompt, kwargs))
        def chunks():
            yield main.GenericChunk(thoughts + draft)
            assert writer_release.wait(5)
        return chunks(), provider + '/' + model, True

    def rules(text, *args, **kwargs):
        assert text == draft
        yield edited
        assert editor_release.wait(5)

    def analysis(*args, **kwargs):
        memory_started.set()
        assert memory_release.wait(5)

    monkeypatch.setattr(main, 'stream_with_fallback', provider_stream)
    monkeypatch.setattr(main, 'refine_with_rules_stream', rules)
    monkeypatch.setattr(main, 'background_analysis', analysis)
    response = asyncio.run(main.generate_story(main.StoryInput(story_id=story, user_input='Continue.',
        provider=provider, model=model), main.BackgroundTasks(), user))
    try:
        first = []
        while not first or first[-1][1]['type'] != 'chunk':
            first.append(payload(next(response.relay)))
        response.detached.set()  # Close browser after the first visible writer draft.
        status = client.get(f'/story/{story}/generation-status').json()
        assert status['active'] and status['stream_available'] and status['turn_index'] == 0
        assert status['state'] == 'generating'
        reopened = main.resume_generation_stream(story, status['run_id'], user_info=user)
        replayed = [payload(next(reopened.relay)) for _ in first]
        assert replayed == first and replayed[-1][1]['text'] == thoughts + draft
        writer_release.set()
        cursor, boundary = payload(next(reopened.relay))
        assert boundary['type'] == 'editing'
        cursor, edited_chunk = payload(next(reopened.relay))
        assert edited_chunk == {'type': 'chunk', 'text': edited}
        assert client.get(f'/story/{story}/generation-status').json()['state'] == 'editing'
        reopened.detached.set()

        # Resume after the last displayed event, rather than duplicating it.
        resumed = main.resume_generation_stream(story, status['run_id'], after=cursor, user_info=user)
        editor_release.set()
        assert memory_started.wait(5)
        final_cursor, replacement = payload(next(resumed.relay))
        assert final_cursor > cursor
        assert replacement == {'type': 'replace', 'text': edited, 'model_thoughts': thoughts}
        assert payload(next(resumed.relay))[1]['type'] == 'finalizing'
        saved = client.get(f'/story/{story}/chat').json()
        assert saved['generation']['active'] and saved['generation']['turn_index'] == 0
        assert saved['messages'][-1]['text'] == edited
        assert saved['messages'][-1]['model_thoughts'] == thoughts
        resumed.detached.set()
        memory_release.set()
        final = client.get(f'/story/{story}/generation-stream', params={'run_id': status['run_id']})
        all_events = [json.loads(line[6:]) for line in final.text.splitlines() if line.startswith('data: ')]
        assert all_events[-1]['type'] == 'done'
        assert client.get(f'/story/{story}/generation-status').json()['state'] == 'completed'
        assert (folder / 'story.md').read_text(encoding='utf-8') == 'The full existing manuscript.\n\n' + edited
        assert len(requests) == 1
        assert requests[0][2]['selected_provider'] == provider
        assert requests[0][2]['selected_model'] == model
        assert 'The full existing manuscript.' in requests[0][0]
    finally:
        writer_release.set(); editor_release.set(); memory_release.set()
        response.detached.set()


def test_replay_endpoint_is_account_story_and_run_scoped_and_read_only(status_app, monkeypatch):
    client, user = status_app
    token = main.begin_story_turn('one', user['uid'])
    response = main.start_live_story_stream(iter([event('chunk', text='Private draft'), event('done')]),
                                          'one', user['uid'], token)
    status = main.current_generation_status('one', user['uid'])
    monkeypatch.setattr(main, 'restore_story_directory_from_firestore', lambda *args: pytest.fail('No cloud restore'))
    run = status['run_id']
    assert client.get('/story/one/generation-stream', params={'run_id': run, 'after': -1}).status_code == 422
    assert client.get('/story/one/generation-stream', params={'run_id': run, 'after': 3}).status_code == 422
    assert client.get('/story/one/generation-stream', params={'run_id': 'wrong'}).status_code == 404
    assert client.get('/story/two/generation-stream', params={'run_id': run}).status_code == 404
    user['uid'] = 'different-account'
    assert client.get('/story/one/generation-stream', params={'run_id': run}).status_code == 404
    response.detached.set()


def test_worker_runs_without_any_reader_and_journal_releases_finished_drafts():
    streams = LiveStreams(max_finished=0)
    done, release = threading.Event(), threading.Event()
    def source():
        yield event('chunk', text='अपूर्ण draft. ' * 10000)
        assert release.wait(5)
        for _ in range(100):
            yield event('chunk', text='Still generating.')
        done.set()
    journal = streams.start(('account', 'story'), 'run', 0, source())
    ref = weakref.ref(journal)
    assert not any(isinstance(value, str) and 'अपूर्ण' in value for value in vars(journal).values())
    release.set()
    assert done.wait(5)
    # Wait for final journal housekeeping, not just the source's final line.
    with journal.condition:
        journal.condition.wait_for(lambda: journal.finished_at is not None, timeout=5)
    assert streams.get(('account', 'story'), 'run') is None
    file_ref = weakref.ref(journal.file)
    del journal
    gc.collect()
    assert ref() is None and file_ref() is None


def test_cursor_replays_exact_unicode_and_old_run_never_follows_a_new_turn():
    streams = LiveStreams()
    journal = streams.start(('u', 's'), 'old', 0, iter([event('chunk', text='Luna: नदी 🌙')]))
    detached = threading.Event()
    frame = next(journal.read(0, detached))
    cursor, value = payload(frame)
    assert value['text'] == 'Luna: नदी 🌙'
    assert journal.valid_cursor(cursor) and not journal.valid_cursor(cursor + 1)
    newer = streams.start(('u', 's'), 'new', 1, iter([event('chunk', text='Next turn')]))
    assert streams.get(('u', 's'), 'old') is None
    assert list(journal.read(cursor, detached)) == []
    assert payload(next(newer.read(0, detached)))[1]['text'] == 'Next turn'


def test_replay_disk_failure_does_not_interrupt_the_save_worker(monkeypatch):
    streams, saved = LiveStreams(), threading.Event()
    def fail(*args):
        raise OSError('Replay storage unavailable')
    monkeypatch.setattr(StreamJournal, 'append', fail)
    def source():
        for _ in range(100):
            yield event('chunk', text='Complete generation continues.')
        saved.set()
    journal = streams.start(('u', 's'), 'run', 0, source())
    assert saved.wait(5)
    assert journal.failed and streams.get(('u', 's'), 'run') is None


def test_replay_setup_failure_releases_the_turn_reservation(status_app, monkeypatch):
    _, user = status_app
    token = main.begin_story_turn('story', user['uid'])
    def fail(*args):
        raise OSError('No temporary file available')
    monkeypatch.setattr(main._live_streams, 'start', fail)
    with pytest.raises(OSError):
        main.start_live_story_stream(iter([]), 'story', user['uid'], token)
    assert not main.story_turn_is_active('story', user['uid'])
