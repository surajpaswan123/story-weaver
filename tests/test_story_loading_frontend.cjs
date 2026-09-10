const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');

function source(name) {
    const start = html.search(new RegExp(`        (?:async )?function ${name}\\(`));
    assert.ok(start >= 0, name);
    return html.slice(start, html.indexOf('\n        }', start) + 10);
}
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const response = data => ({ ok: true, status: 200, json: async () => data });
const page = (text, start = 0, end = 1, total = 1) => ({ messages: [{ role: 'ai', text, turn_index: start }], start_index: start, end_index: end, total_entries: total, revision: 'revision', last_user_prompt: text });

function setup() {
    const elements = new Map(), notices = [], calls = [];
    class Element {
        constructor() {
            this.children = []; this.dataset = {}; this.attributes = {}; this.value = ''; this.disabled = false;
            this.style = {}; this.scrollTop = 0; this.scrollHeight = 100; this.offsetTop = 0; this._text = '';
            this.classList = { add() {}, remove() {}, toggle() {} };
        }
        set textContent(value) { this._text = value; this.children = []; }
        get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
        set innerHTML(value) {
            this._html = value; this.children = []; this._text = value;
            for (const match of value.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element());
        }
        get innerHTML() { return this._html || ''; }
        appendChild(child) { if (child.fragment) { for (const entry of child.children) this.appendChild(entry); } else { this.children.push(child); child.parent = this; } return child; }
        setAttribute(key, value) { this.attributes[key] = value; }
        addEventListener() {}
        before(child) { if (child.id) elements.set(child.id, child); }
        remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
        querySelector() { return new Element(); }
        querySelectorAll() { return []; }
        focus() {}
    }
    for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element());
    // The controls are created on demand, not present in the original document.
    for (const id of ['history-controls', 'history-older', 'history-newer', 'history-page-status']) elements.delete(id);
    const document = { getElementById: id => elements.get(id) || null, createElement: () => new Element(),
        createDocumentFragment: () => Object.assign(new Element(), { fragment: true }), querySelectorAll: () => [] };
    const context = vm.createContext({
        document, window: { confirm: () => true }, AbortController, URLSearchParams, TextDecoder,
        setTimeout, clearTimeout, clearInterval, console: { error() {}, warn() {}, log() {} },
        currentStoryId: 'A', storyViewEpoch: 0, storySubmissionSeq: 0, storyLoadSeq: 0, storyReads: new Map(),
        activeReader: null, activeStoryId: null, isGenerating: false, isGuestMode: false,
        allChatEntries: [], renderedStartIndex: 0, historyStart: 0, historyEnd: 0, historyTotal: 0,
        historyRevision: '', historyLoading: false, CHAT_PAGE_SIZE: 40, lastUserPrompt: '', pendingRetryPrompt: '',
        fileOpenRequest: 0, fileEditorSession: 0, openFileName: null, openFileStoryId: null, openFileOwner: null,
        openFileOriginal: '', fileEditorInstance: null, _analysisPollTimer: null, feedbackRegenerationBusy: false,
        SEND_SVG: '', STOP_SVG: '', attachedAudioFile: null, currentUserSettings: {},
        input: elements.get('user-input'), sendBtn: elements.get('send-btn'), storyDisplay: elements.get('story-display'),
        storyTitle: elements.get('story-title'), elementsGrid: elements.get('elements-grid'), truncationBanner: elements.get('truncation-banner'),
        announceStatus: text => notices.push(text), announceToScreenReader: text => notices.push(text),
        fileEditorIsDirty: () => false, refreshOpenPanels() {}, triggerAnalysis() {}, showPendingRetryBanner() {},
        getSelectedModel: () => 'test-model', getSelectedReasoning: () => '', loadStoryList() {},
        createExpandablePrompt: text => { const el = new Element(); el.textContent = text; return el; },
        authFetch: async (url, options) => { calls.push({ url, options }); return response(page('loaded ' + context.currentStoryId)); },
        requireJsonResponse: async result => { if (!result.ok) throw new Error((await result.json()).detail); return result.json(); },
    });
    elements.get('provider-select').value = 'openai';
    for (const name of ['beginStoryRead', 'isCurrentStoryRead', 'resetStoryView', 'setGenerating', 'updateSendButtonState', 'updateHistoryControls',
        'renderBatch', 'renderChatEntryToNode', 'onStoryScroll', 'loadStory', 'switchStory', 'loadSummary', 'saveSummary', 'submitStory', 'stopGeneration', 'regenerateStory']) {
        vm.runInContext(source(name), context);
    }
    return { context, elements, notices, calls };
}

test('switch clears old state immediately, including editor and panels; scrolling cannot revive it', async () => {
    const app = setup(), c = app.context, pending = deferred();
    await c.loadStory();
    c.openFileName = 'story.md'; c.openFileOriginal = 'old file'; c.fileEditorInstance = { load: text => { app.editorText = text; } };
    app.elements.get('summary-textarea').value = 'old summary';
    c.authFetch = () => pending.promise;
    c.switchStory('B', 'Second story');
    c.onStoryScroll();
    assert.equal(c.allChatEntries.length, 0);
    assert.equal(c.lastUserPrompt, '');
    assert.equal(c.openFileName, null);
    assert.equal(app.editorText, '');
    assert.equal(app.elements.get('summary-textarea').value, '');
    assert.equal(app.elements.get('summary-textarea').disabled, true);
    assert.doesNotMatch(c.storyDisplay.textContent, /loaded A/);
    assert.equal(c.historyLoading, true);
    pending.resolve(response(page('B turn')));
    await new Promise(resolve => setImmediate(resolve));
    assert.match(c.storyDisplay.textContent, /B turn/);
});

test('late JSON from A cannot overwrite B, even after fetch itself already finished', async () => {
    const { context: c } = setup(), body = deferred();
    c.authFetch = async () => ({ ok: true, status: 200, json: () => body.promise });
    const old = c.loadStory();
    await Promise.resolve(); await Promise.resolve();
    c.resetStoryView(); c.currentStoryId = 'B';
    c.authFetch = async () => response(page('B turn'));
    await c.loadStory();
    body.resolve(page('A stale turn'));
    await old;
    assert.match(c.storyDisplay.textContent, /B turn/);
    assert.doesNotMatch(c.storyDisplay.textContent, /A stale/);
});

test('A to B to A rejects the first A response and stale failures', async () => {
    const { context: c } = setup(), first = deferred();
    c.authFetch = () => first.promise;
    const old = c.loadStory();
    c.resetStoryView(); c.currentStoryId = 'B'; c.resetStoryView(); c.currentStoryId = 'A';
    c.authFetch = async () => response(page('new A'));
    await c.loadStory();
    first.reject(new Error('old network failure'));
    await old;
    assert.match(c.storyDisplay.textContent, /new A/);
    assert.doesNotMatch(c.storyDisplay.textContent, /old network failure/);
});

test('failed loads show their error and an accessible retry, without resurrecting history', async () => {
    const { context: c } = setup();
    await c.loadStory();
    c.authFetch = async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Storage is unavailable' }) });
    await c.loadStory();
    assert.equal(c.allChatEntries.length, 0);
    assert.match(c.storyDisplay.textContent, /Storage is unavailable/);
    const retry = c.storyDisplay.children.find(el => el.textContent === 'Retry loading story');
    assert.ok(retry);
    c.authFetch = async () => response(page('recovered'));
    await retry.onclick();
    assert.match(c.storyDisplay.textContent, /recovered/);
});

test('delayed summary cannot populate or save the next story', async () => {
    const app = setup(), c = app.context, pending = deferred();
    c.authFetch = () => pending.promise;
    const old = c.loadSummary();
    c.resetStoryView(); c.currentStoryId = 'B';
    pending.resolve(response({ summary: 'A summary' }));
    await old;
    assert.equal(app.elements.get('summary-textarea').value, '');
    c.authFetch = () => { throw new Error('Must not save unloaded summary'); };
    await c.saveSummary();
});

test('page controls use bounded requests and absolute indexes; conflicts reload latest', async () => {
    const app = setup(), c = app.context;
    c.authFetch = async (url, options) => { app.calls.push({ url, options }); return response(page('Turn', 80, 120, 120)); };
    await c.loadStory();
    assert.match(app.calls[0].url, /last=40/);
    assert.equal(app.calls[0].options.cache, 'no-store');
    assert.equal(c.storyDisplay.children[0].dataset.turnIndex, 80);
    await app.elements.get('history-older').onclick();
    assert.match(app.calls[1].url, /before=80&revision=revision/);
    assert.equal(c.storyDisplay.children.length, 1);
    let count = 0;
    c.authFetch = async () => ++count === 1 ? { status: 409 } : response(page('latest'));
    await c.loadStory({ before: 80, revision: 'old' });
    assert.equal(count, 2);
    assert.match(c.storyDisplay.textContent, /latest/);
    c.setGenerating(true);
    assert.equal(app.elements.get('history-older').disabled, true);
});

test('undo finishing after a story switch cannot regenerate into the new story', async () => {
    const { context: c } = setup(), pending = deferred();
    c.lastUserPrompt = 'Original A prompt';
    c.authFetch = () => pending.promise;
    const action = c.regenerateStory();
    c.resetStoryView(); c.currentStoryId = 'B';
    let generations = 0;
    c.submitStory = () => generations++;
    pending.resolve(response({}));
    await action;
    assert.equal(generations, 0);
});

test('late streaming events and cleanup cannot touch the new story or its active generation', async () => {
    const { context: c } = setup(), chunk = deferred();
    let cancelled = 0;
    c.authFetch = async () => ({ ok: true, body: { getReader: () => ({ read: () => chunk.promise, cancel: async () => cancelled++ }) } });
    const old = c.submitStory('A prompt', true);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(c.isGenerating, true);
    c.resetStoryView(); c.currentStoryId = 'B';
    c.storyDisplay.textContent = 'B turn';
    c.setGenerating(true); c.input.disabled = true;
    const newReader = {}; c.activeReader = newReader;
    chunk.resolve({ done: false, value: new TextEncoder().encode('data: {"type":"warning","message":"A warning"}\n') });
    await old;
    assert.equal(c.storyDisplay.textContent, 'B turn');
    assert.equal(c.activeReader, newReader);
    assert.equal(c.isGenerating, true);
    assert.equal(c.input.disabled, true);
    assert.ok(cancelled >= 1);
});
