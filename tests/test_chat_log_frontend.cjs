const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const code = html.slice(html.indexOf('let openFileName = null;'), html.indexOf('async function saveRules()'));
const original = '[{"role":"ai","text":"Mira waited.","model_thoughts":"<thought>Wait.</thought>"}]';

function setup() {
    const elements = new Map(), calls = [], announcements = [];
    const element = id => {
        if (!elements.has(id)) elements.set(id, {
            value: '', textContent: '', disabled: false, attributes: {}, focused: false,
            classList: { values: new Set(), toggle(key, enabled) { enabled ? this.values.add(key) : this.values.delete(key); }, remove() {}, add() {} },
            setAttribute(key, value) { this.attributes[key] = value; },
            focus() { this.focused = true; },
        });
        return elements.get(id);
    };
    const context = vm.createContext({
        currentStoryId: 'first-story', document: { getElementById: element },
        window: { confirm: () => true }, console: { error() {} },
        announceToScreenReader: message => announcements.push(message), announceStatus() {},
        requireJsonResponse: async response => { if (!response.ok) throw new Error(response.detail); return response.data; },
        authFetch: async (url, options) => {
            calls.push({ url, options });
            return { ok: true, data: options?.method === 'PUT' ? { lines: 1, chars: 90 } : {
                name: 'chat_log.json', owner: 'app', label: 'Chat history', description: 'Transcript and model thoughts.',
                text: original, lines: 1, chars: original.length,
            } };
        },
        loadStory: async () => calls.push({ reloadStory: true }),
    });
    vm.runInContext(code, context);
    context.loadFileList = () => {};
    return { context, element, calls, announcements };
}

test('chat history opens with accessible description and saves with a stale-edit check', async () => {
    const app = setup();
    await app.context.openStoryFile('chat_log.json');
    assert.equal(app.element('file-textarea').value, original);
    assert.equal(app.element('file-textarea').attributes['aria-label'], 'Contents of chat_log.json, editable');
    assert.match(html, /aria-label="File contents, editable" aria-describedby="file-editor-desc"/);
    assert.equal(app.element('file-editor-heading').focused, true);
    assert.equal(app.element('file-delete-btn').classList.values.has('hidden'), true);
    assert.match(app.element('file-editor-meta').textContent, /Transcript/);
    const edited = original.replace('Wait.</thought>', 'Stay cautious.</thought>');
    app.element('file-textarea').value = edited;
    await app.context.saveOpenFile();
    assert.deepEqual(JSON.parse(app.calls[1].options.body), { text: edited, expected_text: original });
    assert.equal(app.calls[1].url, '/story/first-story/file/chat_log.json');
    assert.equal(app.calls[2].reloadStory, true);
    assert.equal(app.context.fileEditorIsDirty(), false);
});

test('invalid JSON or a stale save stays editable and does not refresh history', async () => {
    const app = setup();
    await app.context.openStoryFile('chat_log.json');
    app.element('file-textarea').value = 'invalid JSON';
    app.context.authFetch = async () => ({ ok: false, detail: 'Invalid chat JSON at line 1, column 1' });
    await app.context.saveOpenFile();
    assert.equal(app.element('file-textarea').value, 'invalid JSON');
    assert.equal(app.context.fileEditorIsDirty(), true);
    assert.match(app.element('file-status').textContent, /Invalid chat JSON/);
    assert.equal(app.element('file-save-btn').disabled, false);
    assert.equal(app.calls.some(call => call.reloadStory), false);
});

test('switching stories cannot save the previously opened chat history into another story', async () => {
    const app = setup();
    await app.context.openStoryFile('chat_log.json');
    app.context.currentStoryId = 'second-story';
    app.element('file-textarea').value = '[]';
    await app.context.saveOpenFile();
    assert.equal(app.calls.length, 1);
    assert.match(app.element('file-status').textContent, /selected story changed/);
});
