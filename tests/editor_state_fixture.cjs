// State-only adapter for integration tests. Browser layout belongs to CodeMirror.
const { FileTextEditor, createDocumentState } = require('../static/file-editor.js');
function stateView(text = '') {
    const view = {
        state: createDocumentState(text), focus() {},
        dispatch(...specs) { view.state = view.state.update(...specs).state; },
        setState(state) { view.state = state; },
    };
    return view;
}
class HeadlessFileEditor extends FileTextEditor {
    constructor(doc, options = {}) {
        const editor = Object.create(HeadlessFileEditor.prototype);
        editor.doc = doc;
        editor.el = id => doc.getElementById(id);
        editor.status = options.status || (() => {});
        editor.view = stateView();
        editor.view.focus = () => editor.el('file-textarea').focus();
        Object.defineProperty(editor.el('file-textarea'), 'value', {
            configurable: true,
            get: () => editor.getText(),
            set: text => editor.view.dispatch({ changes: { from: 0, to: editor.view.state.doc.length, insert: text } }),
        });
        return editor;
    }
    stateFor(text) { return createDocumentState(text); }
    load(text, name) {
        super.load(text, name);
        this.el('file-textarea').setAttribute('aria-label', `Contents of ${name}, editable`);
    }
}
module.exports = { stateView, HeadlessFileEditor };
