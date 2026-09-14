/* Story Weaver's plain-text editor. Build with npm --prefix frontend run build. */
import { Compartment, EditorSelection, EditorState } from '@codemirror/state';
import { EditorView, keymap } from '@codemirror/view';
import {
    standardKeymap, history, undo, redo, undoDepth, redoDepth,
    isolateHistory, selectAll, insertNewline, cursorGroupForwardWin,
    selectGroupForwardWin, deleteGroupForwardWin,
} from '@codemirror/commands';
import { SearchCursor } from '@codemirror/search';

const normalize = text => text.replace(/\r\n?/g, '\n');

// Windows word processors move through hard line breaks with Ctrl+Up/Down.
// Shift extends from the original anchor, including when direction reverses.
// Dispatch a document selection instead of asking Chrome to extend a DOM range.
function paragraph(forward, extend = false) {
    return ({ state, dispatch }) => {
        const range = state.selection.main;
        const line = state.doc.lineAt(range.head);
        const head = forward
            ? (line.number < state.doc.lines ? state.doc.line(line.number + 1).from : state.doc.length)
            : (range.head > line.from ? line.from : state.doc.line(Math.max(1, line.number - 1)).from);
        dispatch(state.update({
            selection: EditorSelection.single(extend ? range.anchor : head, head),
            scrollIntoView: true, userEvent: 'select',
        }));
        return true;
    };
}

export const editorKeymap = [
    { win: 'Ctrl-ArrowRight',
        run: cursorGroupForwardWin, shift: selectGroupForwardWin, preventDefault: true },
    { win: 'Ctrl-Delete', run: deleteGroupForwardWin, preventDefault: true },
    { win: 'Ctrl-ArrowUp', run: paragraph(false), shift: paragraph(false, true), preventDefault: true },
    { win: 'Ctrl-ArrowDown', run: paragraph(true), shift: paragraph(true, true), preventDefault: true },
    { key: 'Enter', run: insertNewline, shift: insertNewline, preventDefault: true },
    { key: 'Mod-z', run: undo, preventDefault: true },
    { key: 'Mod-y', run: redo, preventDefault: true },
    { key: 'Mod-Shift-z', run: redo, preventDefault: true },
    ...standardKeymap,
];

export function createDocumentState(text, extensions = []) {
    return EditorState.create({ doc: normalize(text), extensions: [history({ minDepth: 100 }), ...extensions] });
}

export class FileTextEditor {
    constructor(doc, options = {}) {
        this.doc = doc;
        this.el = id => doc.getElementById(id);
        this.status = options.status || (() => {});
        this.onSave = options.save || (() => {});
        this.wrap = new Compartment();
        this.name = '';
        this.cachedDoc = null;
        this.cachedText = '';
        this.view = new EditorView({ parent: this.el('file-editor-host'), state: this.stateFor('') });
        this.bind();
        this.updateControls();
    }
    stateFor(text) {
        return createDocumentState(text, [
            keymap.of([
                { key: 'Mod-s', run: () => { this.onSave(); return true; }, preventDefault: true },
                { key: 'Mod-f', run: () => { this.openFind(); return true; }, preventDefault: true },
                ...editorKeymap,
            ]),
            this.wrap.of(this.el('file-wrap-input').checked ? EditorView.lineWrapping : []),
            EditorView.contentAttributes.of({
                id: 'file-textarea', role: 'textbox', 'aria-multiline': 'true',
                'aria-label': this.name ? `Contents of ${this.name}, editable` : 'File contents, editable',
                'aria-describedby': 'file-editor-desc file-editor-help',
                spellcheck: 'false', autocorrect: 'off', autocapitalize: 'off', autocomplete: 'off',
            }),
            EditorView.theme({
                '&': { height: 'min(60vh, 36rem)', minHeight: '16rem', border: '1px solid #a8a29e',
                    borderRadius: '0.5rem', backgroundColor: '#fff', color: '#292524' },
                '&.cm-focused': { outline: '2px solid #78716c' },
                '.cm-scroller': { overflow: 'auto', fontFamily: 'inherit', fontSize: '1rem', lineHeight: '1.6' },
                '.cm-content': { padding: '12px', caretColor: '#292524' },
            }),
            EditorView.updateListener.of(update => {
                if (update.docChanged) { this.cachedDoc = null; this.cachedText = ''; }
                if (update.docChanged || update.transactions.length) this.updateControls();
            }),
        ]);
    }
    load(text, name = '') {
        this.name = name;
        this.cachedDoc = null;
        this.cachedText = '';
        this.view.setState(this.stateFor(text));
        this.updateControls();
    }
    focus() { this.view.focus(); }
    getText() {
        const current = this.view.state.doc;
        if (this.cachedDoc !== current) {
            this.cachedDoc = current;
            this.cachedText = current.toString();
        }
        return this.cachedText;
    }
    breakHistoryGroup() { this.view.dispatch({ annotations: isolateHistory.of('full') }); }
    selection() {
        const range = this.view.state.selection.main;
        return { start: range.from, end: range.to };
    }
    selectedText() {
        const { from, to } = this.view.state.selection.main;
        return this.view.state.sliceDoc(from, to);
    }
    selectAll() { selectAll(this.view); this.focus(); }
    reveal(start, end = start) {
        this.view.dispatch({ selection: EditorSelection.single(start, end), scrollIntoView: true });
        this.focus();
    }
    replaceSelection(text) {
        this.view.dispatch(this.view.state.replaceSelection(normalize(text)), {
            userEvent: 'input', annotations: isolateHistory.of('full'), scrollIntoView: true,
        });
        this.focus();
    }
    history(forward) {
        const changed = (forward ? redo : undo)(this.view);
        if (!changed) this.status(forward ? 'Nothing to redo.' : 'Nothing to undo.');
        this.focus();
    }
    updateControls() {
        if (!this.view) return;
        for (const [id, disabled] of [
            ['file-undo-btn', undoDepth(this.view.state) === 0],
            ['file-redo-btn', redoDepth(this.view.state) === 0],
        ]) {
            const button = this.el(id);
            if (button.disabled !== disabled) button.disabled = disabled;
        }
    }
    async copy(all = false) {
        const text = all ? this.getText() : this.selectedText();
        if (!all && !text) { this.status('Select text first, or choose Copy all.'); return false; }
        let copied = false;
        try {
            await this.doc.defaultView.navigator.clipboard.writeText(text);
            copied = true;
        } catch (_) {
            const active = this.doc.activeElement;
            let written = false;
            const handler = event => {
                if (!event.clipboardData) return;
                event.preventDefault();
                event.stopImmediatePropagation();
                event.clipboardData.setData('text/plain', text);
                written = true;
            };
            this.doc.addEventListener('copy', handler, true);
            try { this.focus(); copied = this.doc.execCommand('copy') && written; }
            catch (_) { copied = false; }
            finally { this.doc.removeEventListener('copy', handler, true); active?.focus(); }
        }
        this.status(copied ? `${all ? 'Entire file' : 'Selection'} copied.` :
            'Copy was blocked. Focus the editor and press Ctrl+C, or use Download file.');
        return copied;
    }
    openFind() {
        this.el('file-find-controls').open = true;
        this.el('file-find-input').focus();
    }
    find() {
        const query = this.el('file-find-input').value;
        if (!query) { this.status('Enter text to find.'); this.openFind(); return; }
        const state = this.view.state;
        let cursor = new SearchCursor(state.doc, query, state.selection.main.to).next();
        let wrapped = false;
        if (cursor.done) { cursor = new SearchCursor(state.doc, query).next(); wrapped = true; }
        if (cursor.done) { this.status('No matching text in this file.'); return; }
        this.reveal(cursor.value.from, cursor.value.to);
        this.status(wrapped ? 'Search wrapped to the start. Match selected.' : 'Match selected.');
    }
    replaceFound() {
        const query = this.el('file-find-input').value;
        if (!query || this.selectedText() !== query) { this.find(); return; }
        this.replaceSelection(this.el('file-replace-input').value);
        this.status('Match replaced.');
    }
    goToLine() {
        const line = Number(this.el('file-line-input').value);
        const count = this.view.state.doc.lines;
        if (!Number.isSafeInteger(line) || line < 1 || line > count) {
            this.status(`Enter a line number from 1 to ${count.toLocaleString()}.`); return;
        }
        this.reveal(this.view.state.doc.line(line).from);
        this.status(`Line ${line.toLocaleString()}.`);
    }
    download() {
        const win = this.doc.defaultView;
        const url = win.URL.createObjectURL(new win.Blob([this.getText()], { type: 'text/plain;charset=utf-8' }));
        const link = this.doc.createElement('a');
        link.href = url;
        link.download = this.name || 'story-file.txt';
        link.click();
        win.setTimeout(() => win.URL.revokeObjectURL(url), 30000);
        this.status('Downloaded the complete file, including unsaved edits.');
    }
    bind() {
        const actions = {
            'file-copy-btn': () => this.copy(), 'file-copy-all-btn': () => this.copy(true),
            'file-select-all-btn': () => this.selectAll(),
            'file-undo-btn': () => this.history(false), 'file-redo-btn': () => this.history(true),
            'file-find-btn': () => this.find(), 'file-replace-btn': () => this.replaceFound(),
            'file-line-btn': () => this.goToLine(), 'file-download-btn': () => this.download(),
        };
        for (const [id, action] of Object.entries(actions)) this.el(id).addEventListener('click', action);
        this.el('file-wrap-input').addEventListener('change', event => {
            this.view.dispatch({ effects: this.wrap.reconfigure(event.target.checked ? EditorView.lineWrapping : []) });
        });
        for (const [id, action] of [['file-find-input', () => this.find()], ['file-line-input', () => this.goToLine()]]) {
            this.el(id).addEventListener('keydown', event => {
                if (event.key === 'Enter') { event.preventDefault(); action(); }
            });
        }
    }
}
