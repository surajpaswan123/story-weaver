const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createDocumentState, editorKeymap } = require('../static/file-editor.js');
const { stateView } = require('./editor_state_fixture.cjs');
const binding = key => editorKeymap.find(b => b.key === key || b.win === key);

test('paragraph selection crosses old section limits and reverses from its anchor', () => {
    const text = 'paragraph '.repeat(2000) + '\nnext\nlast';
    const view = stateView(text);
    binding('Ctrl-ArrowDown').shift(view);
    assert.equal(view.state.selection.main.anchor, 0);
    assert.equal(view.state.selection.main.head, text.indexOf('\n') + 1);
    binding('Ctrl-ArrowDown').shift(view);
    assert.equal(view.state.selection.main.head, text.lastIndexOf('\n') + 1);
    binding('Ctrl-ArrowUp').shift(view);
    assert.equal(view.state.selection.main.anchor, 0);
    assert.equal(view.state.selection.main.head, text.indexOf('\n') + 1);
});

test('whole-file replacement, undo and both redo shortcuts preserve large text', () => {
    const text = 'Story paragraph.\n'.repeat(100000);
    const view = stateView(text);
    binding('Mod-a').run(view);
    assert.equal(view.state.selection.main.to, text.length);
    view.dispatch(view.state.replaceSelection('replacement'), { userEvent: 'input.paste' });
    assert.equal(view.state.doc.toString(), 'replacement');
    binding('Mod-z').run(view);
    assert.equal(view.state.doc.toString(), text);
    binding('Mod-y').run(view);
    assert.equal(view.state.doc.toString(), 'replacement');
    binding('Mod-z').run(view);
    binding('Mod-Shift-z').run(view);
    assert.equal(view.state.doc.toString(), 'replacement');
});

test('redo clears after a different edit and opening another file clears history', () => {
    const view = stateView('before');
    view.dispatch({ changes: { from: 0, to: 6, insert: 'after' }, userEvent: 'input.paste' });
    binding('Mod-z').run(view);
    view.dispatch({ changes: { from: 0, to: 6, insert: 'different' }, userEvent: 'input.paste' });
    assert.equal(binding('Mod-y').run(view), false);
    view.setState(createDocumentState('second file'));
    assert.equal(binding('Mod-z').run(view), false);
    assert.equal(view.state.doc.toString(), 'second file');
});
