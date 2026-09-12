const { test } = require('node:test');
const assert = require('node:assert/strict');
const { FileTextEditor, TextBuffer, SECTION_SIZE, MAX_VISIBLE_SIZE } = require('../static/file-editor.js');

function setup(text) {
    const nodes = new Map(), messages = [], documentEvents = new Map();
    const doc = {
        activeElement: null,
        getElementById(id) {
            if (!nodes.has(id)) nodes.set(id, {
                value: '', textContent: '', selectionStart: 0, selectionEnd: 0, events: {},
                addEventListener(name, handler) { this.events[name] = handler; },
                focus() { doc.activeElement = this; },
                setSelectionRange(start, end) {
                    this.selectionStart = Math.min(this.value.length, Math.max(0, start));
                    this.selectionEnd = Math.min(this.value.length, Math.max(this.selectionStart, end));
                },
            });
            return nodes.get(id);
        },
        addEventListener(name, handler) { documentEvents.set(name, handler); },
        removeEventListener(name) { documentEvents.delete(name); },
        execCommand(name) {
            assert.equal(name, 'copy');
            documentEvents.get('copy')?.({ clipboardData: { setData(type, value) { doc.clipboard = value; } },
                preventDefault() {}, stopImmediatePropagation() {} });
            return true;
        },
    };
    let saves = 0;
    const editor = new FileTextEditor(doc, { status: message => messages.push(message), save: () => saves++ });
    editor.load(text, 'story.md');
    const fire = (name, properties = {}) => {
        const event = { key: '', cancelable: true, prevented: false, preventDefault() { this.prevented = true; }, ...properties };
        editor.area.events[name](event);
        return event;
    };
    return { editor, doc, messages, fire, get saves() { return saves; } };
}

test('two million characters traverse every section without loss or a large textarea', () => {
    const text = ('हिन्दी 🐉\nA second line.\n' + 'x'.repeat(1000)).repeat(2000);
    const { editor } = setup(text);
    const parts = [];
    while (true) {
        assert.ok(editor.area.value.length <= SECTION_SIZE);
        assert.ok(!/^[\uDC00-\uDFFF]/.test(editor.area.value));
        assert.ok(!/[\uD800-\uDBFF]$/.test(editor.area.value));
        parts.push(editor.area.value);
        if (editor.end === text.length) break;
        editor.navigate(1);
    }
    assert.equal(parts.join(''), text);
    assert.equal(editor.getText(), text);
});

test('a huge single line and emoji exactly on a boundary stay bounded and intact', () => {
    const text = 'x'.repeat(SECTION_SIZE - 1) + '🐉' + 'z'.repeat(1000000);
    const { editor } = setup(text);
    assert.equal(editor.area.value.length, SECTION_SIZE - 1);
    editor.navigate(1);
    assert.ok(editor.area.value.startsWith('🐉'));
    assert.equal(editor.getText(), text);
});

test('edits in distant sections undo and redo without losing unseen content', () => {
    const original = 'begin\n' + 'middle\n'.repeat(20000) + 'end';
    const { editor } = setup(original);
    editor.area.setSelectionRange(0, 5);
    editor.replaceSelection('START');
    editor.reveal(editor.buffer.text.length);
    editor.replaceSelection('!');
    const final = 'START\n' + 'middle\n'.repeat(20000) + 'end!';
    assert.equal(editor.getText(), final);
    editor.history(false);
    editor.history(false);
    assert.equal(editor.getText(), original);
    editor.history(true);
    editor.history(true);
    assert.equal(editor.getText(), final);
});

test('Ctrl+A and native copy transfer the whole file, including offscreen sections', () => {
    const original = 'Long document 🐉\n'.repeat(10000);
    const app = setup(original);
    assert.equal(app.fire('keydown', { key: 'a', ctrlKey: true }).prevented, true);
    let copied;
    assert.equal(app.fire('copy', { clipboardData: { setData(type, value) { assert.equal(type, 'text/plain'); copied = value; } } }).prevented, true);
    assert.equal(copied, original);
    assert.ok(app.editor.area.value.length <= SECTION_SIZE);
    app.fire('beforeinput', { inputType: 'insertText', data: 'replacement' });
    assert.equal(app.editor.getText(), 'replacement');
    app.editor.history(false);
    assert.equal(app.editor.getText(), original);
    assert.equal(app.editor.selectedText(), original);
});

test('large paste replaces all selected text without rendering the full paste', () => {
    const app = setup('old contents');
    const replacement = 'Pasted 🐉\r\n'.repeat(100000);
    app.editor.selectAll();
    app.fire('paste', { clipboardData: { getData() { return replacement; } } });
    assert.equal(app.editor.getText(), replacement.replace(/\r\n/g, '\n'));
    assert.ok(app.editor.area.value.length <= SECTION_SIZE);
    app.fire('keydown', { key: 'z', ctrlKey: true });
    assert.equal(app.editor.getText(), 'old contents');
    app.fire('keydown', { key: 'Z', ctrlKey: true, shiftKey: true });
    assert.equal(app.editor.getText(), replacement.replace(/\r\n/g, '\n'));
});

test('copy buttons preserve selection and include unsaved edits', async () => {
    const app = setup('abc'.repeat(20000));
    app.editor.area.setSelectionRange(1, 3);
    app.editor.replaceSelection('XY');
    app.editor.area.setSelectionRange(0, 3);
    assert.equal(await app.editor.copy(false), true);
    assert.equal(app.doc.clipboard, 'aXY');
    assert.equal(await app.editor.copy(true), true);
    assert.equal(app.doc.clipboard, 'aXY' + 'abc'.repeat(19999));
    assert.equal(app.editor.area.selectionEnd, 3);
});

test('failed clipboard cut never removes text and cut can be undone', () => {
    const app = setup('full document\n'.repeat(10000));
    const original = app.editor.getText();
    app.editor.selectAll();
    assert.equal(app.fire('cut', { clipboardData: { setData() { throw new Error('blocked'); } } }).prevented, true);
    assert.equal(app.editor.getText(), original);
    app.fire('cut', { clipboardData: { setData() {} } });
    assert.equal(app.editor.getText(), '');
    app.editor.history(false);
    assert.equal(app.editor.getText(), original);
});

test('native input is captured, adjacent typing groups, and redo clears after a new edit', () => {
    const app = setup('large prefix\n'.repeat(20000));
    app.editor.reveal(app.editor.buffer.text.length);
    const original = app.editor.getText();
    for (const letter of 'hello') {
        app.editor.area.value += letter;
        app.editor.area.setSelectionRange(app.editor.area.value.length, app.editor.area.value.length);
        app.fire('input', { inputType: 'insertText' });
    }
    assert.equal(app.editor.buffer.undoStack.length, 1);
    assert.equal(app.editor.buffer.undoStack[0].inserted, 'hello');
    app.editor.history(false);
    assert.equal(app.editor.getText(), original);
    app.editor.replaceSelection('new');
    assert.equal(app.editor.buffer.redoStack.length, 0);
});

test('find matches across a section boundary and replacement is exact and undoable', () => {
    const text = 'x'.repeat(SECTION_SIZE - 3) + 'UNIQUE\nlast line';
    const app = setup(text);
    app.doc.getElementById('file-find-input').value = 'UNIQUE';
    app.editor.find();
    assert.equal(app.editor.selectedText(), 'UNIQUE');
    app.doc.getElementById('file-replace-input').value = '$& literal 🐉';
    app.editor.replaceFound();
    assert.equal(app.editor.getText(), text.replace('UNIQUE', () => '$& literal 🐉'));
    app.editor.history(false);
    assert.equal(app.editor.getText(), text);
    app.doc.getElementById('file-line-input').value = '2';
    app.editor.goToLine();
    assert.equal(app.editor.selection().start, text.indexOf('\n') + 1);
});

test('document shortcuts work and ordinary selection stays native within a section', () => {
    const app = setup('line\n'.repeat(10000));
    app.fire('keydown', { key: 'End', ctrlKey: true });
    assert.equal(app.editor.selection().start, app.editor.getText().length);
    app.fire('keydown', { key: 'Home', ctrlKey: true });
    assert.equal(app.editor.selection().start, 0);
    assert.equal(app.fire('keydown', { key: 'ArrowDown', ctrlKey: true, shiftKey: true }).prevented, false);
    app.fire('keydown', { key: 's', ctrlKey: true });
    assert.equal(app.saves, 1);
    app.fire('keydown', { key: 'f', ctrlKey: true });
    assert.equal(app.doc.activeElement, app.doc.getElementById('file-find-input'));
});

test('opening another file clears selection and history', () => {
    const app = setup('original');
    app.editor.replaceSelection('edit');
    app.editor.selectAll();
    app.editor.load('second', 'rules.md');
    app.editor.history(false);
    assert.equal(app.editor.getText(), 'second');
    assert.equal(app.editor.allSelected, false);
});

test('history retains a bounded number of differences rather than full document snapshots', () => {
    const buffer = new TextBuffer('x'.repeat(2000000));
    for (let i = 0; i < 1000; i++) buffer.edit(buffer.text.length, buffer.text.length, 'a');
    assert.equal(buffer.undoStack.length, 500);
    assert.equal(buffer.historyBytes, 1000);
    for (let i = 0; i < 500; i++) buffer.undo();
    assert.equal(buffer.text.length, 2000500);
});

test('copy buttons await a successful async clipboard write before reporting success', async t => {
    const previous = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    t.after(() => previous ? Object.defineProperty(globalThis, 'navigator', previous) : delete globalThis.navigator);
    let copied, finish;
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: {
        writeText: text => new Promise(resolve => { copied = text; finish = resolve; }),
    } } });
    const app = setup('entire file\n'.repeat(10000));
    app.doc.execCommand = () => { throw new Error('Native fallback must not run on success'); };
    const result = app.editor.copy(true);
    assert.equal(copied, app.editor.getText());
    assert.equal(app.messages.length, 0);
    finish();
    assert.equal(await result, true);
    assert.match(app.messages.at(-1), /Entire file copied/);
});

test('blocked clipboard APIs do not claim that anything was copied', async t => {
    const previous = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    t.after(() => previous ? Object.defineProperty(globalThis, 'navigator', previous) : delete globalThis.navigator);
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: {
        writeText: async () => { throw new Error('denied'); },
    } } });
    const app = setup('preserve this text');
    app.doc.execCommand = () => false;
    assert.equal(await app.editor.copy(true), false);
    assert.match(app.messages.at(-1), /blocked/);
    assert.equal(app.editor.getText(), 'preserve this text');
});

test('small undo differences do not retain dozens of complete old manuscripts', () => {
    const { execFileSync } = require('node:child_process');
    const source = require.resolve('../static/file-editor.js');
    // An isolated process and explicit GC measure retained strings, not timing or
    // temporary allocations from other tests. Old sliced history retained 61 MB.
    const measurement = execFileSync(process.execPath, ['--expose-gc', '-e', `
        const { TextBuffer } = require(${JSON.stringify(source)});
        global.gc();
        const initial = process.memoryUsage().heapUsed;
        const buffer = new TextBuffer(('हिन्दी text for a memory probe.\\n').repeat(16000));
        for (let i = 0; i < 60; i++) {
            const start = 10000 + i * 37;
            buffer.edit(start, start + 24, 'replacement-' + String(i).padStart(12, '0'));
        }
        global.gc();
        console.log(JSON.stringify({ entries: buffer.undoStack.length,
            retained: process.memoryUsage().heapUsed - initial }));
    `], { encoding: 'utf8', timeout: 15000 });
    const result = JSON.parse(measurement);
    assert.equal(result.entries, 60);
    assert.ok(result.retained < 12 * 1024 * 1024, `Retained ${result.retained} bytes for small differences`);
});

test('independent history strings preserve Unicode and unmatched UTF-16 surrogates', () => {
    const original = 'हिन्दी 🐉 \ud800 ' + 'prefix '.repeat(30) + ' \udc00 end';
    const inserted = 'changed \ud800 हिन्दी 🐉 \udc00';
    const buffer = new TextBuffer(original);
    buffer.edit(0, original.length, inserted);
    assert.equal(buffer.text, inserted);
    buffer.undo();
    assert.equal(buffer.text, original);
    buffer.redo();
    assert.equal(buffer.text, inserted);
});

test('typing in a full section keeps the native textbox until its headroom is used', () => {
    const original = 'x'.repeat(30000);
    const { editor, fire } = setup(original);
    let nativeValue = editor.area.value, rewrites = 0;
    Object.defineProperty(editor.area, 'value', {
        get: () => nativeValue,
        set: value => { rewrites++; nativeValue = value; },
    });
    editor.area.setSelectionRange(100, 100);
    let expected = original;
    function nativeType(text) {
        const at = editor.area.selectionStart, absolute = editor.start + at;
        nativeValue = nativeValue.slice(0, at) + text + nativeValue.slice(at);
        editor.area.setSelectionRange(at + text.length, at + text.length);
        expected = expected.slice(0, absolute) + text + expected.slice(absolute);
        fire('input', { inputType: 'insertText' });
        assert.equal(editor.getText(), expected);
        assert.equal(editor.selection().end, absolute + text.length);
    }
    for (const letter of 'हिन्दी typing without a textbox rebuild') nativeType(letter);
    assert.equal(rewrites, 0);
    nativeType('a'.repeat(MAX_VISIBLE_SIZE - nativeValue.length));
    assert.equal(rewrites, 0);
    nativeType('!');
    assert.equal(rewrites, 1);
    assert.ok(editor.area.value.length <= SECTION_SIZE);
    const operations = editor.buffer.undoStack.length;
    for (let i = 0; i < operations; i++) editor.history(false);
    assert.equal(editor.getText(), original);
    for (let i = 0; i < operations; i++) editor.history(true);
    assert.equal(editor.getText(), expected);
});

test('selection leaves descriptions alone and a typing burst shares one update', async () => {
    const { editor, fire, doc } = setup('hello');
    const info = doc.getElementById('file-section-info');
    let content = info.textContent, writes = 0;
    Object.defineProperty(info, 'textContent', {
        get: () => content, set: value => { writes++; content = value; },
    });
    for (let i = 0; i < 100; i++) {
        fire('keydown', { key: 'ArrowDown', ctrlKey: true, shiftKey: true });
        editor.updateControls();
    }
    assert.equal(writes, 0);
    for (let i = 0; i < 100; i++) {
        editor.area.value += 'a';
        fire('input', { inputType: 'insertText' });
    }
    assert.equal(writes, 0);
    await new Promise(resolve => setTimeout(resolve, 300));
    assert.equal(writes, 1);
    assert.match(content, /105 characters/);
    editor.area.value += '!';
    fire('input', { inputType: 'insertText' });
    editor.load('second file');
    assert.equal(editor.descriptionTimer, null);
    assert.match(content, /11 characters/);
});

test('Windows and CR line endings normalize once without phantom edits or offset drift', () => {
    const original = 'हिन्दी 🐉\r\nnext\rthird\n'.repeat(2000);
    const normalized = original.replace(/\r\n?/g, '\n');
    const { editor } = setup(original);
    editor.navigate(1);
    assert.equal(editor.getText(), normalized);
    assert.equal(editor.buffer.undoStack.length, 0);
    editor.area.setSelectionRange(2, 4);
    const { start, end } = editor.selection();
    editor.replaceSelection('new\r\nline\r');
    assert.equal(editor.getText(), normalized.slice(0, start) + 'new\nline\n' + normalized.slice(end));
    editor.history(false);
    assert.equal(editor.getText(), normalized);
});
