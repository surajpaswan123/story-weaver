const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const feedbackCode = html.slice(html.indexOf('let feedbackRegenerationBusy = false;'), html.indexOf('async function regenerateStory()'));
const retryCode = html.slice(html.indexOf('async function retryLastPrompt('), html.indexOf('let feedbackRegenerationBusy = false;'));
const regeneration = { turn_to_replace: 'Old turn.', model_thoughts: '<thought>Old plan.</thought>', feedback: 'Make it cautious.' };

class Control {
    constructor() { this.value = ''; this.disabled = false; this.textContent = ''; this.listeners = {}; this.focused = false; }
    focus() { this.focused = true; }
    addEventListener(type, handler) { this.listeners[type] = handler; }
}

function setup() {
    const calls = [], generations = [], announcements = [];
    let activeForm = null;
    class Form extends Control {
        constructor() {
            super(); this.dataset = {}; this.attributes = {}; this.removed = false;
            this.controls = Object.fromEntries(['textarea', '[data-feedback-cancel]', '[data-feedback-status]', '[type="submit"]'].map(key => [key, new Control()]));
        }
        setAttribute(key, value) { this.attributes[key] = value; }
        querySelector(key) { return this.controls[key]; }
        remove() { this.removed = true; if (activeForm === this) activeForm = null; }
    }
    const provider = Object.assign(new Control(), { value: 'openai' });
    const input = new Control();
    const bar = { after(form) { activeForm = form; } };
    const button = Object.assign(new Control(), { closest: () => bar });
    const response = data => ({ ok: true, json: async () => data });
    const context = vm.createContext({
        document: {
            getElementById(id) {
                if (id === 'provider-select') return provider;
                if (id === 'regeneration-feedback-input') return activeForm?.querySelector('textarea') || null;
                return null;
            },
            createElement(tag) { assert.equal(tag, 'form'); return new Form(); },
        },
        currentStoryId: 'story-one', isGenerating: false, isGuestMode: false, input,
        getSelectedModel: () => 'test-model',
        showGuestNagDialog() { announcements.push('Sign in'); },
        updateSendButtonState() {},
        announceToScreenReader(message) { announcements.push(message); },
        announceStatus(message) { announcements.push(message); },
        console,
        authFetch: async (url, options) => { calls.push({ url, options }); return response({ restored_prompt: 'Original prompt.', regeneration }); },
        requireJsonResponse: async result => { if (!result.ok) throw new Error('Undo rejected'); return result.json(); },
        loadStory: async () => { calls.push({ load: true }); },
        submitStory: async (...args) => { generations.push(args); },
    });
    vm.runInContext(feedbackCode + '\n' + retryCode, context);
    const open = () => { context.showRegenerateFeedback(button); return activeForm; };
    const submit = form => context.submitFeedbackRegeneration({ preventDefault() {} }, form);
    return { context, open, submit, button, provider, input, calls, generations, announcements, response };
}

test('opening focuses the feedback textbox; cancelling leaves the turn untouched', () => {
    const app = setup();
    const form = app.open();
    assert.equal(form.attributes['aria-label'], 'Regenerate with feedback');
    assert.match(form.innerHTML, /<label for="regeneration-feedback-input"[^>]*>Enter your feedback<\/label>/);
    assert.match(form.innerHTML, /aria-describedby="regeneration-feedback-help"/);
    assert.equal(form.querySelector('textarea').focused, true);
    assert.equal(app.open(), form);
    form.querySelector('[data-feedback-cancel]').listeners.click();
    assert.equal(form.removed, true);
    assert.equal(app.button.focused, true);
    assert.equal(app.calls.length, 0);
});

test('blank feedback and missing model never undo the turn', async () => {
    const app = setup();
    const form = app.open();
    form.querySelector('textarea').value = '  \n';
    await app.submit(form);
    assert.match(form.querySelector('[data-feedback-status]').textContent, /Enter feedback/);
    form.querySelector('textarea').value = 'Do better.';
    app.context.getSelectedModel = () => '';
    await app.submit(form);
    assert.match(form.querySelector('[data-feedback-status]').textContent, /Choose a provider and model/);
    assert.equal(app.calls.length, 0);
});

test('feedback submission undoes once, reloads context, and forwards the exact captured turn', async () => {
    const app = setup();
    const form = app.open();
    form.querySelector('textarea').value = '  Keep <names> & make it cautious.\n';
    await app.submit(form);
    assert.equal(app.calls[0].url, '/story/story-one/undo');
    assert.deepEqual(JSON.parse(app.calls[0].options.body), { feedback: '  Keep <names> & make it cautious.\n' });
    assert.equal(app.calls[1].load, true);
    assert.equal(app.generations.length, 1);
    assert.deepEqual(app.generations[0], ['Original prompt.', false, regeneration]);
    assert.equal(form.removed, true);
    assert.equal(app.input.disabled, false);
});

test('double submission while undo is pending does not remove another turn', async () => {
    const app = setup();
    let resolve;
    app.context.authFetch = (url, options) => { app.calls.push({ url, options }); return new Promise(done => { resolve = done; }); };
    const form = app.open();
    form.querySelector('textarea').value = 'Make it cautious.';
    const first = app.submit(form);
    await app.submit(form);
    assert.equal(app.calls.length, 1);
    resolve(app.response({ restored_prompt: 'Original prompt.', regeneration }));
    await first;
    assert.equal(app.generations.length, 1);
});

test('an undo failure keeps feedback editable and does not start generation', async () => {
    const app = setup();
    app.context.authFetch = async () => ({ ok: false });
    const form = app.open();
    form.querySelector('textarea').value = 'Make it cautious.';
    await app.submit(form);
    assert.equal(form.removed, false);
    assert.equal(form.querySelector('textarea').disabled, false);
    assert.equal(form.querySelector('textarea').value, 'Make it cautious.');
    assert.match(form.querySelector('[data-feedback-status]').textContent, /Undo rejected/);
    assert.equal(app.generations.length, 0);
});

test('switching stories does not regenerate the wrong story', async () => {
    const app = setup();
    const form = app.open();
    form.querySelector('textarea').value = 'Make it cautious.';
    app.context.currentStoryId = 'another-story';
    await app.submit(form);
    assert.equal(app.calls.length, 0);
    assert.equal(app.generations.length, 0);
});

test('retry after reload forwards saved feedback instead of doing another undo', async () => {
    const app = setup();
    app.context.authFetch = async (url, options) => { app.calls.push({ url, options }); return app.response({ prompt: 'Original prompt.', regeneration }); };
    await app.context.retryLastPrompt('Older prompt');
    assert.equal(app.calls[0].url, '/story/story-one/retry');
    assert.deepEqual(app.generations[0], ['Original prompt.', false, regeneration]);
    assert.equal(app.calls.some(call => call.url?.endsWith('/undo')), false);
});

test('all latest-turn action renderers include the new accessible button', () => {
    assert.equal((html.match(/onclick="showRegenerateFeedback\(this\)"/g) || []).length, 4);
    assert.match(html, /summary\.textContent = 'Model thoughts'/);
});
