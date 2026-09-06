const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const pipelineCode = html.slice(html.indexOf('function populatePipelineModelDropdowns('), html.indexOf('// ===== MULTI-KEY'));
const discoveryCode = html.slice(html.indexOf('let providersData = {};'), html.indexOf('// ===== LOCAL OPENAI-COMPATIBLE SERVER'));
const settingsCode = html.slice(html.indexOf('async function fetchUserSettings()'), html.indexOf('function renderUserSettingsUI()'));

// Minimal select DOM for exercising the real page functions without a browser
// dependency. Options retain browser-like selection and disabled semantics.
class Element {
    constructor(tag = 'div') {
        this.tagName = tag;
        this.children = [];
        this.dataset = {};
        this.style = {};
        this.disabled = false;
        this.selected = false;
        this.textContent = '';
        this.classList = { add() {}, remove() {} };
    }
    get options() {
        return this.children.flatMap(child => child.tagName === 'option' ? [child] : child.options);
    }
    get value() {
        if (this.tagName !== 'select') return this._value || '';
        return (this.options.filter(option => option.selected).at(-1) || this.options[0])?.value || '';
    }
    set value(value) {
        if (this.tagName !== 'select') this._value = value;
        else this.options.forEach(option => { option.selected = option.value === value; });
    }
    set innerHTML(value) {
        this.children = [];
        if (value.includes('<option')) {
            const option = new Element('option');
            option.value = '';
            option.selected = true;
            option.disabled = value.includes('disabled');
            this.children.push(option);
        }
    }
    appendChild(child) { this.children.push(child); }
    querySelector(selector) {
        const value = selector.match(/option\[value="(.*)"\]/)[1];
        return this.options.find(option => option.value === value) || null;
    }
}

const pipelineIds = ['input-story-model', 'input-background-model', 'input-rules-model', 'input-audio-model'];
function setup() {
    const elements = {};
    for (const id of ['provider-select', 'model-select', ...pipelineIds]) elements[id] = new Element('select');
    for (const id of ['models-loader-bar', 'models-status-tag', 'settings-models-status', 'selected-provider-status', 'manual-model-field']) elements[id] = new Element();
    elements['manual-model-id'] = new Element('input');
    const requests = [];
    const context = vm.createContext({
        document: { getElementById: id => elements[id] || null, createElement: tag => new Element(tag) },
        CSS: { escape: value => value },
        console,
        authFetch: url => new Promise((resolve, reject) => requests.push({ url, resolve, reject })),
        requireJsonResponse: async response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        },
        addLocalProviderToDropdown() {},
        getLocalServerConfig: () => ({ enabled: false }),
        refreshLocalModelDropdown() {},
        renderUserSettingsUI() {},
        populateLocalPipelineModelDropdowns() {},
        showGuestBanner() {}, applyGuestRestrictions() {},
    });
    vm.runInContext(`let currentUserSettings = null; let isGuestMode = false; let settingsRequestVersion = 0;\n${pipelineCode}\n${discoveryCode}\n${settingsCode}`, context);
    return { elements, requests, context, load: () => context.loadProvidersAndModels() };
}
function reply(request, models, errors = {}) {
    const providers = { openai: { name: 'OpenAI (User Key)', configured: true, models,
        base_url: 'https://example.com/v1', discovery_error: errors.openai || '' } };
    request.resolve({ ok: true, json: async () => ({ providers, errors }) });
}
function values(element) { return element.options.filter(option => !option.disabled).map(option => option.value).filter(Boolean); }
const tick = () => new Promise(resolve => setImmediate(resolve));

test('one catalog request updates all selectors and preserves a still-valid choice', async () => {
    const app = setup();
    app.elements['provider-select'].appendChild(Object.assign(new Element('option'), { value: 'openai', selected: true }));
    app.elements['model-select'].appendChild(Object.assign(new Element('option'), { value: 'fresh-model', selected: true }));
    const done = app.load();
    assert.equal(app.requests.length, 1);
    assert.equal(app.elements['model-select'].value, '');
    assert.equal(app.elements['model-select'].disabled, true);
    reply(app.requests[0], ['fresh-model']);
    await done;
    assert.equal(app.elements['model-select'].value, 'fresh-model');
    for (const id of pipelineIds) assert.deepEqual(values(app.elements[id]), ['openai::fresh-model']);
});

test('a slower previous connection response cannot overwrite the new catalog', async () => {
    const app = setup();
    const old = app.load();
    const fresh = app.load();
    reply(app.requests[1], ['new-model']);
    await fresh;
    reply(app.requests[0], ['old-opencode-model']);
    await old;
    for (const id of pipelineIds) assert.deepEqual(values(app.elements[id]), ['openai::new-model']);
    assert.match(app.elements['models-status-tag'].textContent, /1 online models ready/);
});

test('stale JSON body or failure cannot replace a newer empty result', async () => {
    for (const reject of [false, true]) {
        const app = setup();
        const old = app.load();
        let resolveBody;
        if (!reject) {
            app.requests[0].resolve({ ok: true, json: () => new Promise(resolve => { resolveBody = resolve; }) });
            await tick();
        }
        const fresh = app.load();
        reply(app.requests[1], [], { openai: 'The provider returned no models for this API key.' });
        await fresh;
        if (reject) app.requests[0].reject(new Error('stale failure'));
        else resolveBody({ providers: { openai: { models: ['old-model'] } } });
        await old;
        assert.deepEqual(values(app.elements['provider-select']), ['openai']);
        assert.match(app.elements['settings-models-status'].textContent, /returned no models/);
        assert.doesNotMatch(app.elements['models-status-tag'].textContent, /ready|stale failure/);
    }
});

test('settings save invalidation prevents in-flight old connection data from rendering', async () => {
    const app = setup();
    const old = app.load();
    app.context.invalidateProviderModels();
    reply(app.requests[0], ['old-model']);
    await old;
    assert.deepEqual(values(app.elements['provider-select']), []);
    assert.equal(app.elements['model-select'].disabled, true);
});

test('empty/error discovery makes old pipeline choices explicitly unavailable', async () => {
    const app = setup();
    app.elements['input-story-model'].dataset.val = 'openai::old-model';
    const done = app.load();
    reply(app.requests[0], [], { openai: 'The provider returned no models for this API key.' });
    await done;
    assert.deepEqual(values(app.elements['input-story-model']), []);
    const old = app.elements['input-story-model'].options.find(option => option.value === 'openai::old-model');
    assert.equal(old.disabled, true);
    assert.match(old.textContent, /Unavailable/);
    assert.equal(app.elements['models-status-tag'].dataset.state, 'error');
});

test('a user changing a pipeline selection is not overridden by the saved dataset on refresh', async () => {
    const app = setup();
    app.elements['input-story-model'].dataset.val = 'openai::first-model';
    let done = app.load();
    reply(app.requests[0], ['first-model', 'second-model']);
    await done;
    app.elements['input-story-model'].value = 'openai::second-model';
    done = app.load();
    reply(app.requests[1], ['first-model', 'second-model']);
    await done;
    assert.equal(app.elements['input-story-model'].value, 'openai::second-model');
});

test('network failures clear online choices and allow an explicit successful retry', async () => {
    const app = setup();
    let done = app.load();
    app.requests[0].reject(new Error('offline'));
    await done;
    assert.deepEqual(values(app.elements['provider-select']), []);
    assert.match(app.elements['models-status-tag'].textContent, /Refresh models/);
    done = app.load();
    reply(app.requests[1], ['recovered-model']);
    await done;
    assert.deepEqual(values(app.elements['input-story-model']), ['openai::recovered-model']);
});

test('loading settings performs just one shared catalog discovery', async () => {
    const app = setup();
    const done = app.context.fetchUserSettings();
    assert.equal(app.requests[0].url, '/api/user/settings');
    app.requests[0].resolve({ ok: true, json: async () => ({ masked_keys: {} }) });
    await tick();
    assert.equal(app.requests[1].url, '/api/providers-models');
    reply(app.requests[1], ['new-model']);
    await done;
    assert.equal(app.requests.length, 2);
});

test('configured OpenAI is selectable with an empty catalog and exposes a labelled manual model field', async () => {
    const app = setup();
    const done = app.load();
    reply(app.requests[0], [], { openai: 'The provider returned no models.' });
    await done;
    assert.deepEqual(values(app.elements['provider-select']), ['openai']);
    app.elements['provider-select'].value = 'openai';
    app.context.onProviderChange();
    assert.equal(app.elements['provider-select'].disabled, false);
    assert.equal(app.elements['model-select'].disabled, true);
    assert.equal(app.elements['manual-model-field'].hidden, false);
    assert.equal(app.elements['manual-model-id'].disabled, false);
    assert.match(app.elements['selected-provider-status'].textContent, /https:\/\/example.com\/v1/);
    assert.match(app.elements['selected-provider-status'].textContent, /returned no models/);
    assert.match(html, /<label for="manual-model-id"/);
    assert.match(html, /id="manual-model-id"[^>]+aria-describedby="manual-model-help selected-provider-status"/);
    app.elements['manual-model-id'].value = '  known-provider-model  ';
    assert.equal(app.context.getSelectedModel(), 'known-provider-model');
});

test('manual model selection is cleared when the provider or saved connection changes', async () => {
    const app = setup();
    const done = app.load();
    reply(app.requests[0], []);
    await done;
    app.elements['provider-select'].value = 'openai';
    app.context.onProviderChange();
    app.elements['manual-model-id'].value = 'old-model';
    app.elements['provider-select'].value = '';
    app.context.onProviderChange();
    assert.equal(app.elements['manual-model-id'].value, '');
    assert.equal(app.elements['manual-model-field'].hidden, true);
    assert.equal(app.context.getSelectedModel(), '');
    app.elements['provider-select'].value = 'openai';
    app.context.onProviderChange();
    app.elements['manual-model-id'].value = 'another-old-model';
    app.context.invalidateProviderModels();
    assert.equal(app.elements['manual-model-id'].value, '');
    assert.equal(app.elements['manual-model-id'].disabled, true);
});

test('a successful catalog refresh restores the dropdown and hides manual entry', async () => {
    const app = setup();
    let done = app.load();
    reply(app.requests[0], []);
    await done;
    app.elements['provider-select'].value = 'openai';
    app.context.onProviderChange();
    app.elements['manual-model-id'].value = 'manual-model';
    done = app.load();
    reply(app.requests[1], ['listed-model']);
    await done;
    assert.equal(app.elements['manual-model-field'].hidden, true);
    assert.equal(app.elements['model-select'].disabled, false);
    assert.deepEqual(values(app.elements['model-select']), ['listed-model']);
    app.elements['model-select'].value = 'listed-model';
    assert.equal(app.context.getSelectedModel(), 'listed-model');
});
