const { test } = require('node:test');
const assert = require('node:assert/strict');
const { Draft, consume } = require('../static/live-generation.js');

test('replayed chunks preserve every character across split thought tags and Unicode', () => {
    const raw = 'A beginning. <thought>Think about नदी 🌙 carefully.</thought> Luna continued.\n\nAnother paragraph.';
    for (let split = 1; split < raw.length; split++) {
        const draft = new Draft();
        draft.apply({ type: 'chunk', text: raw.slice(0, split) });
        draft.apply({ type: 'chunk', text: raw.slice(split) });
        assert.equal(draft.text, 'A beginning.  Luna continued.\n\nAnother paragraph.');
        assert.equal(draft.thoughts, 'Think about नदी 🌙 carefully.');
    }
});

test('rules editing replaces the writer draft while retaining thoughts; saved replacement is exact', () => {
    const draft = new Draft();
    draft.apply({ type: 'chunk', text: '<thought>Original thoughts.</thought>Writer draft.' });
    draft.apply({ type: 'editing' });
    assert.equal(draft.text, 'Writer draft.'); // Keep it visible while the editor starts.
    draft.apply({ type: 'chunk', text: 'Edited draft.' });
    assert.equal(draft.text, 'Edited draft.');
    assert.equal(draft.thoughts, 'Original thoughts.');
    assert.equal(draft.stage, 'editing');
    draft.apply({ type: 'replace', text: 'Exact saved prose.\n\nAll of it.', model_thoughts: '<thought>Original thoughts.</thought>' });
    draft.apply({ type: 'finalizing' });
    assert.equal(draft.text, 'Exact saved prose.\n\nAll of it.');
    assert.equal(draft.thoughts, 'Original thoughts.');
    assert.equal(draft.stage, 'finalizing');
});

test('provider retry replaces a thought-only attempt instead of mixing two attempts', () => {
    const draft = new Draft();
    draft.apply({ type: 'chunk', text: '<thought>First attempt.</thought>' });
    draft.apply({ type: 'reset' });
    draft.apply({ type: 'chunk', text: '<thought>Second attempt.</thought>Actual prose.' });
    assert.equal(draft.text, 'Actual prose.');
    assert.equal(draft.thoughts, 'Second attempt.');
});

test('stream reader assembles split SSE frames and UTF-8 without losing cursor IDs', async () => {
    const events = [
        'id: 100\ndata: {"type":"chunk","text":"नदी 🌙"}\n\n',
        'id: 200\ndata: {"type":"editing"}\n\n',
    ];
    const bytes = new TextEncoder().encode(events.join(''));
    const response = new Response(new ReadableStream({ start(controller) {
        for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
        controller.close();
    } }));
    const received = [];
    await consume(response, (event, cursor) => received.push([event, cursor]), new AbortController().signal);
    assert.deepEqual(received, [[{ type: 'chunk', text: 'नदी 🌙' }, 100], [{ type: 'editing' }, 200]]);
});

test('a truncated event is not acknowledged, so reconnect can replay it completely', async () => {
    let cursor = 0;
    const response = new Response('id: 100\ndata: {"type":"chunk","text":"partial');
    await assert.rejects(consume(response, (_, id) => cursor = id, new AbortController().signal), /Incomplete generation event/);
    assert.equal(cursor, 0);
});

test('aborting a subscription cancels its reader without rendering a late event', async () => {
    const abort = new AbortController();
    let cancelled = false, resolveRead;
    const response = { body: { getReader: () => ({ read: () => new Promise(resolve => resolveRead = resolve),
        cancel: async () => cancelled = true, releaseLock() {} }) } };
    const events = [];
    const task = consume(response, event => events.push(event), abort.signal);
    abort.abort();
    resolveRead({ done: false, value: new TextEncoder().encode('id: 1\ndata: {"type":"chunk","text":"old story"}\n\n') });
    await task;
    assert.equal(cancelled, true);
    assert.deepEqual(events, []);
});
