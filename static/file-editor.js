/* Plain-text editing with a bounded native textarea for large documents. */
(function (root) {
    'use strict';
    const SECTION_SIZE = 8000;
    // Leave room for native typing: resetting textarea.value after every added
    // character rebuilds Chrome's accessible text and disrupts screen readers.
    const MAX_VISIBLE_SIZE = 12000;
    const HISTORY_LIMIT = 20 * 1024 * 1024;

    function independentText(text) {
        // V8 can keep an entire old manuscript alive behind a tiny substring.
        // Materialize history text instead of retaining slices of those versions.
        // JSON round-tripping preserves UTF-16, including unpaired surrogates.
        return text ? JSON.parse(JSON.stringify(text)) : '';
    }

    function normalizeNewlines(text) { return text.replace(/\r\n?/g, '\n'); }

    // Never split a surrogate pair or a CRLF at a viewport boundary.
    function boundary(text, offset) {
        offset = Math.max(0, Math.min(text.length, offset));
        const code = text.charCodeAt(offset);
        if ((code >= 0xDC00 && code <= 0xDFFF) ||
            (text[offset] === '\n' && text[offset - 1] === '\r')) offset--;
        return Math.max(0, offset);
    }

    class TextBuffer {
        constructor(text = '') { this.reset(text); }
        reset(text) {
            this.text = text;
            this.undoStack = [];
            this.redoStack = [];
            this.historyBytes = 0;
            this.group = 0;
        }
        breakGroup() { this.group++; }
        edit(start, end, inserted, typing = false) {
            let removed = this.text.slice(start, end);
            if (removed === inserted) return false;
            removed = independentText(removed);
            inserted = independentText(inserted);
            const now = Date.now();
            const last = this.undoStack.at(-1);
            this.historyBytes -= this.redoStack.reduce((n, op) => n + op.bytes, 0);
            this.redoStack = [];
            if (typing && !removed && last?.typing && last.group === this.group &&
                !last.removed && start === last.start + last.inserted.length && now - last.time < 1000) {
                last.inserted += inserted;
                last.bytes += inserted.length * 2;
                last.time = now;
                this.historyBytes += inserted.length * 2;
            } else {
                const op = { start, removed, inserted, typing, time: now, group: this.group,
                    bytes: (removed.length + inserted.length) * 2 };
                this.undoStack.push(op);
                this.historyBytes += op.bytes;
            }
            // Keep the newest operation undoable even when it alone exceeds the budget.
            while (this.undoStack.length > 1 && (this.historyBytes > HISTORY_LIMIT || this.undoStack.length > 500)) {
                this.historyBytes -= this.undoStack.shift().bytes;
            }
            this.text = this.text.slice(0, start) + inserted + this.text.slice(end);
            return true;
        }
        undo() {
            const op = this.undoStack.pop();
            if (!op) return null;
            this.text = this.text.slice(0, op.start) + op.removed + this.text.slice(op.start + op.inserted.length);
            this.redoStack.push(op);
            this.breakGroup();
            return { start: op.start, end: op.start + op.removed.length };
        }
        redo() {
            const op = this.redoStack.pop();
            if (!op) return null;
            this.text = this.text.slice(0, op.start) + op.inserted + this.text.slice(op.start + op.removed.length);
            this.undoStack.push(op);
            this.breakGroup();
            return { start: op.start, end: op.start + op.inserted.length };
        }
    }

    class FileTextEditor {
        constructor(doc, options = {}) {
            this.doc = doc;
            this.el = id => doc.getElementById(id);
            this.area = this.el('file-textarea');
            this.status = options.status || (() => {});
            this.onSave = options.save || (() => {});
            this.buffer = new TextBuffer();
            this.start = 0;
            this.end = 0;
            this.visible = '';
            this.allSelected = false;
            this.composing = false;
            this.bind();
        }
        load(text, name = '') {
            // The native textarea always normalizes CRLF/CR. Normalize once so
            // reading or navigating a Windows file cannot manufacture an edit.
            this.buffer.reset(normalizeNewlines(text));
            this.name = name;
            this.allSelected = false;
            this.show(0);
        }
        getText() { this.flush(); return this.buffer.text; }
        flush(typing = false) {
            const next = this.area.value;
            if (next === this.visible) return;
            let left = 0, oldEnd = this.visible.length, newEnd = next.length;
            while (left < oldEnd && left < newEnd && this.visible[left] === next[left]) left++;
            while (oldEnd > left && newEnd > left && this.visible[oldEnd - 1] === next[newEnd - 1]) { oldEnd--; newEnd--; }
            this.buffer.edit(this.start + left, this.start + oldEnd, next.slice(left, newEnd), typing);
            this.end += next.length - this.visible.length;
            this.visible = next;
            this.allSelected = false;
            if (!this.composing && next.length > MAX_VISIBLE_SIZE) {
                const caret = this.start + this.area.selectionEnd;
                this.show(Math.max(0, caret - Math.floor(SECTION_SIZE / 2)), caret, caret);
            } else this.updateControls(true);
        }
        show(start, selectionStart = start, selectionEnd = selectionStart) {
            const text = this.buffer.text;
            this.start = boundary(text, start);
            let end = boundary(text, Math.min(text.length, this.start + SECTION_SIZE));
            // Prefer complete lines, but still bound a file consisting of one huge line.
            if (end < text.length) {
                const newline = text.lastIndexOf('\n', end - 1);
                if (newline > this.start + SECTION_SIZE / 2 && newline >= selectionEnd) end = newline + 1;
            }
            this.end = end;
            this.visible = text.slice(this.start, this.end);
            this.area.value = this.visible;
            this.allSelected = false;
            this.area.setSelectionRange(Math.max(0, selectionStart - this.start),
                Math.min(this.visible.length, selectionEnd - this.start));
            this.updateControls();
        }
        reveal(start, end = start) {
            if (start < this.start || end > this.end || this.area.value.length > MAX_VISIBLE_SIZE) {
                this.show(Math.max(0, start - Math.floor(SECTION_SIZE / 4)), start, end);
            } else {
                this.allSelected = false;
                this.area.setSelectionRange(start - this.start, end - this.start);
                this.updateControls();
            }
            this.area.focus();
        }
        updateControls(deferDescription = false) {
            for (const [id, disabled] of [
                ['file-undo-btn', !this.buffer.undoStack.length],
                ['file-redo-btn', !this.buffer.redoStack.length],
                ['file-previous-btn', this.start === 0],
                ['file-next-btn', this.end >= this.buffer.text.length],
            ]) {
                const control = this.el(id);
                if (control.disabled !== disabled) control.disabled = disabled;
            }
            const sectionControls = this.el('file-section-controls');
            const hidden = this.start === 0 && this.end >= this.buffer.text.length;
            if (sectionControls.hidden !== hidden) sectionControls.hidden = hidden;
            if (deferDescription) {
                if (this.descriptionTimer == null) this.descriptionTimer = root.setTimeout(() => {
                    this.descriptionTimer = null;
                    this.updateControls();
                }, 250);
                return;
            }
            root.clearTimeout(this.descriptionTimer);
            this.descriptionTimer = null;
            const info = this.allSelected ? 'Entire file selected. Copy, cut, typing, or paste applies to the entire file.' :
                !hidden ?
                    `Showing characters ${(this.start + 1).toLocaleString()}–${this.end.toLocaleString()} of ${this.buffer.text.length.toLocaleString()}. Save and Copy all include every section.` :
                    `Whole file shown. ${this.buffer.text.length.toLocaleString()} characters.`;
            const description = this.el('file-section-info');
            if (description.textContent !== info) description.textContent = info;
        }
        selection() {
            return this.allSelected ? { start: 0, end: this.buffer.text.length } :
                { start: this.start + this.area.selectionStart, end: this.start + this.area.selectionEnd };
        }
        selectedText() {
            this.flush();
            const { start, end } = this.selection();
            return this.buffer.text.slice(start, end);
        }
        selectAll() {
            this.flush();
            this.buffer.breakGroup();
            this.allSelected = true;
            this.area.focus();
            this.area.setSelectionRange(0, this.visible.length);
            this.updateControls();
            this.status(`Entire file selected: ${this.buffer.text.length.toLocaleString()} characters.`);
        }
        replaceSelection(text) {
            this.flush();
            text = normalizeNewlines(text);
            const { start, end } = this.selection();
            this.buffer.breakGroup();
            this.buffer.edit(start, end, text);
            const caret = start + text.length;
            this.show(Math.max(0, caret - Math.floor(SECTION_SIZE / 2)), caret, caret);
            this.area.focus();
        }
        history(redo) {
            this.flush();
            const range = redo ? this.buffer.redo() : this.buffer.undo();
            if (!range) { this.status(redo ? 'Nothing to redo.' : 'Nothing to undo.'); return; }
            this.show(Math.max(0, range.start - Math.floor(SECTION_SIZE / 4)), range.start, range.end);
            if (range.start === 0 && range.end === this.buffer.text.length && range.end > this.visible.length) {
                this.selectAll();
            }
            this.area.focus();
            this.status(redo ? 'Edit redone.' : 'Edit undone.');
        }
        navigate(direction) {
            this.flush();
            this.buffer.breakGroup();
            this.show(direction > 0 ? this.end : Math.max(0, this.start - SECTION_SIZE));
            this.area.focus();
            this.status(this.el('file-section-info').textContent);
        }
        async copy(all = false) {
            const text = all ? this.getText() : this.selectedText();
            if (!all && !text) { this.status('Select text first, or choose Copy all.'); return false; }
            // On HTTPS/localhost, await the actual clipboard write before announcing success.
            // This path copies large strings without adding another textarea to the page.
            try {
                await root.navigator.clipboard.writeText(text);
                this.status(`${all ? 'Entire file' : 'Selection'} copied: ${text.length.toLocaleString()} characters.`);
                return true;
            } catch (_) { /* Fall back for browsers without async clipboard support. */ }
            let written = false;
            const previous = this.doc.activeElement;
            const handler = event => {
                if (!event.clipboardData) return;
                event.clipboardData.setData('text/plain', text);
                event.preventDefault();
                event.stopImmediatePropagation();
                written = true;
            };
            this.doc.addEventListener('copy', handler, true);
            try {
                this.area.focus();
                written = this.doc.execCommand('copy') && written;
            } catch (_) { written = false; }
            finally {
                this.doc.removeEventListener('copy', handler, true);
                previous?.focus();
            }
            if (!written) {
                this.status('Copy was blocked by the browser. Focus the editor and press Ctrl+C, or use Download file.');
                return false;
            }
            this.status(`${all ? 'Entire file' : 'Selection'} copied: ${text.length.toLocaleString()} characters.`);
            return true;
        }
        find() {
            this.flush();
            this.buffer.breakGroup();
            const query = this.el('file-find-input').value;
            if (!query) { this.status('Enter text to find.'); this.el('file-find-input').focus(); return; }
            const from = this.allSelected ? 0 : this.selection().end;
            let found = this.buffer.text.indexOf(query, from);
            let wrapped = false;
            if (found < 0) { found = this.buffer.text.indexOf(query); wrapped = true; }
            if (found < 0) { this.status('No matching text in this file.'); return; }
            this.reveal(found, found + query.length);
            this.status(`${wrapped ? 'Search wrapped to the start. ' : ''}Match at character ${(found + 1).toLocaleString()}.`);
        }
        replaceFound() {
            const query = this.el('file-find-input').value;
            if (!query || this.selectedText() !== query) { this.find(); return; }
            this.replaceSelection(this.el('file-replace-input').value);
            this.status('Match replaced. Choose Find next for another match.');
        }
        goToLine() {
            this.flush();
            this.buffer.breakGroup();
            const line = Number(this.el('file-line-input').value);
            if (!Number.isSafeInteger(line) || line < 1) { this.status('Enter a line number of 1 or greater.'); return; }
            let offset = 0;
            for (let count = 1; count < line; count++) {
                const next = this.buffer.text.indexOf('\n', offset);
                if (next < 0) { this.status(`The file has only ${count.toLocaleString()} lines.`); return; }
                offset = next + 1;
            }
            this.reveal(offset);
            this.status(`Line ${line.toLocaleString()}.`);
        }
        download() {
            const url = root.URL.createObjectURL(new root.Blob([this.getText()], { type: 'text/plain;charset=utf-8' }));
            const link = this.doc.createElement('a');
            link.href = url;
            link.download = this.name || 'story-file.txt';
            link.click();
            root.setTimeout(() => root.URL.revokeObjectURL(url), 30000);
            this.status('Downloaded the complete file, including unsaved edits.');
        }
        bind() {
            const actions = {
                'file-copy-btn': () => this.copy(), 'file-copy-all-btn': () => this.copy(true),
                'file-select-all-btn': () => this.selectAll(),
                'file-undo-btn': () => this.history(false), 'file-redo-btn': () => this.history(true),
                'file-previous-btn': () => this.navigate(-1), 'file-next-btn': () => this.navigate(1),
                'file-find-btn': () => this.find(), 'file-replace-btn': () => this.replaceFound(),
                'file-line-btn': () => this.goToLine(), 'file-download-btn': () => this.download(),
            };
            for (const [id, action] of Object.entries(actions)) this.el(id).addEventListener('click', action);
            this.el('file-wrap-input').addEventListener('change', event => {
                this.area.wrap = event.target.checked ? 'soft' : 'off';
            });
            for (const [id, action] of [['file-find-input', () => this.find()], ['file-line-input', () => this.goToLine()]]) {
                this.el(id).addEventListener('keydown', event => {
                    if (event.key === 'Enter') { event.preventDefault(); action(); }
                });
            }
            this.area.addEventListener('input', event => this.flush(event.inputType === 'insertText' && !this.composing));
            this.area.addEventListener('compositionstart', () => {
                if (this.allSelected) this.replaceSelection('');
                this.composing = true;
                this.buffer.breakGroup();
            });
            this.area.addEventListener('compositionend', () => {
                this.composing = false;
                this.flush();
                if (this.visible.length > MAX_VISIBLE_SIZE) this.show(this.start);
            });
            this.area.addEventListener('pointerdown', () => {
                this.allSelected = false;
                this.buffer.breakGroup();
                this.updateControls();
            });
            this.area.addEventListener('keydown', event => {
                if (event.isComposing) return;
                const modifier = (event.ctrlKey || event.metaKey) && !event.altKey;
                const key = event.key.toLowerCase();
                if (modifier && key === 'a') { event.preventDefault(); this.selectAll(); }
                else if (modifier && (key === 'z' || key === 'y')) {
                    event.preventDefault(); this.history(key === 'y' || event.shiftKey);
                } else if (modifier && key === 's') { event.preventDefault(); this.onSave(); }
                else if (modifier && key === 'f') {
                    event.preventDefault(); this.el('file-find-controls').open = true; this.el('file-find-input').focus();
                } else if (event.altKey && !modifier && ['PageUp', 'PageDown'].includes(event.key)) {
                    event.preventDefault(); this.navigate(event.key === 'PageDown' ? 1 : -1);
                } else if (modifier && !event.shiftKey && ['Home', 'End'].includes(event.key)) {
                    event.preventDefault(); this.flush(); this.reveal(event.key === 'Home' ? 0 : this.buffer.text.length);
                } else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'Escape'].includes(event.key)) {
                    if (this.allSelected) {
                        event.preventDefault();
                        this.reveal(['ArrowRight', 'ArrowDown', 'End'].includes(event.key) ? this.buffer.text.length : 0);
                    }
                    this.allSelected = false;
                    this.buffer.breakGroup();
                }
            });
            this.area.addEventListener('beforeinput', event => {
                if (['historyUndo', 'historyRedo'].includes(event.inputType) && event.cancelable) {
                    event.preventDefault(); this.history(event.inputType === 'historyRedo'); return;
                }
                if (!this.allSelected || !event.cancelable) return;
                if (event.inputType.startsWith('delete')) { event.preventDefault(); this.replaceSelection(''); }
                else if (event.inputType === 'insertText' && event.data !== null) { event.preventDefault(); this.replaceSelection(event.data); }
                else if (['insertLineBreak', 'insertParagraph'].includes(event.inputType)) { event.preventDefault(); this.replaceSelection('\n'); }
            });
            for (const name of ['copy', 'cut']) this.area.addEventListener(name, event => {
                if (!event.clipboardData) return;
                const text = this.selectedText();
                if (!text) return;
                event.preventDefault();
                try {
                    event.clipboardData.setData('text/plain', text);
                    if (name === 'cut') this.replaceSelection('');
                    this.status(`${name === 'cut' ? 'Cut' : 'Copied'} ${text.length.toLocaleString()} characters.`);
                } catch (_) { this.status('Clipboard operation failed. Text was kept. Use Copy all or Download file.'); }
            });
            this.area.addEventListener('paste', event => {
                if (!event.clipboardData) return;
                event.preventDefault();
                this.replaceSelection(event.clipboardData.getData('text/plain'));
                this.status('Text pasted.' + (this.buffer.undoStack.length ? ' Undo is available.' : ''));
            });
            // Do not let dropping a large file bypass the bounded-textarea paste path.
            this.area.addEventListener('drop', event => {
                event.preventDefault();
                this.status('Use paste to insert text at the cursor.');
            });
        }
    }
    root.StoryFileEditor = { FileTextEditor, TextBuffer, SECTION_SIZE, MAX_VISIBLE_SIZE };
    if (typeof module !== 'undefined' && module.exports) module.exports = root.StoryFileEditor;
})(typeof globalThis !== 'undefined' ? globalThis : window);
