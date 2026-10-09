(function (root) {
    'use strict';

    class Draft {
        constructor() { this.text = ''; this.thoughts = ''; this.buffer = ''; this.inThought = false; this.stage = 'generating'; this.model = ''; this.editingPending = false; }
        chunk(text) {
            this.buffer += text || '';
            while (this.buffer) {
                const tag = this.inThought ? '</thought>' : '<thought>';
                const index = this.buffer.indexOf(tag);
                if (index >= 0) {
                    this.append(this.buffer.slice(0, index));
                    this.buffer = this.buffer.slice(index + tag.length);
                    this.inThought = !this.inThought;
                    continue;
                }
                let held = 0;
                for (let size = tag.length - 1; size > 0; size--) {
                    if (this.buffer.endsWith(tag.slice(0, size))) { held = size; break; }
                }
                this.append(this.buffer.slice(0, this.buffer.length - held));
                this.buffer = held ? this.buffer.slice(-held) : '';
                break;
            }
        }
        append(text) { if (this.inThought) this.thoughts += text; else this.text += text; }
        apply(event) {
            if (event.type === 'chunk') {
                if (this.editingPending) { this.text = this.buffer = ''; this.inThought = false; this.editingPending = false; }
                this.chunk(event.text);
            }
            else if (event.type === 'info') this.model = event.model || '';
            else if (event.type === 'reset') { this.text = this.thoughts = this.buffer = ''; this.inThought = this.editingPending = false; this.stage = 'generating'; }
            else if (event.type === 'editing') {
                if (this.inThought) this.append(this.buffer);
                this.buffer = ''; this.inThought = false; this.editingPending = true; this.stage = 'editing';
            } else if (event.type === 'replace') {
                this.text = event.text || ''; this.buffer = ''; this.inThought = this.editingPending = false;
                if (typeof event.model_thoughts === 'string') this.thoughts = event.model_thoughts.replace(/<\/?(?:thought|think|thoughts|thaughts)\b[^>]*>/gi, '');
            } else if (['thinking', 'retrying', 'finalizing', 'error', 'stopped'].includes(event.type)) this.stage = event.type;
            else if (event.type === 'done') this.stage = 'finalizing';
        }
    }

    async function consume(response, onEvent, signal) {
        const reader = response.body.getReader(), decoder = new TextDecoder();
        const abort = () => reader.cancel().catch(() => {});
        signal.addEventListener('abort', abort, { once: true });
        let buffer = '';
        try {
            while (!signal.aborted) {
                const { done, value } = await reader.read();
                if (signal.aborted) return;
                buffer += decoder.decode(value, { stream: !done });
                let end;
                while ((end = buffer.indexOf('\n\n')) >= 0) {
                    const frame = buffer.slice(0, end); buffer = buffer.slice(end + 2);
                    const lines = frame.split('\n');
                    const data = lines.filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n');
                    const id = lines.find(line => line.startsWith('id: '));
                    if (data) onEvent(JSON.parse(data), id ? Number(id.slice(4)) : null);
                }
                if (done) {
                    if (buffer.trim()) throw new Error('Incomplete generation event');
                    return;
                }
            }
        } finally {
            signal.removeEventListener('abort', abort);
            await reader.cancel().catch(() => {});
            reader.releaseLock();
        }
    }

    function createView(document, display, runId) {
        const draft = new Draft(), container = document.createElement('div');
        container.dataset.liveRun = runId;
        const heading = document.createElement('h3');
        heading.className = 'px-6 pt-4 pb-1 font-bold text-sm text-stone-500';
        heading.textContent = 'AI said:';
        const toggle = document.createElement('button');
        toggle.type = 'button'; toggle.className = 'action-btn'; toggle.style.margin = '0 24px 8px';
        toggle.textContent = 'Show Model thoughts'; toggle.hidden = true;
        const thoughts = document.createElement('div');
        thoughts.id = 'live-thoughts-' + runId; thoughts.className = 'thinking-panel'; thoughts.hidden = true;
        toggle.setAttribute('aria-controls', thoughts.id); toggle.setAttribute('aria-expanded', 'false');
        toggle.addEventListener('click', () => {
            thoughts.hidden = !thoughts.hidden;
            toggle.setAttribute('aria-expanded', String(!thoughts.hidden));
            toggle.textContent = thoughts.hidden ? 'Show Model thoughts' : 'Hide Model thoughts';
        });
        const body = document.createElement('div');
        body.className = 'story-font text-lg leading-relaxed whitespace-pre-wrap px-6 pb-3';
        for (const node of [heading, toggle, thoughts, body]) container.appendChild(node);
        display.appendChild(container);
        let timer = null;
        function paint() {
            timer = null;
            const follow = display.scrollHeight - display.scrollTop - display.clientHeight < 120;
            heading.textContent = 'AI said:' + (draft.model ? ' - ' + draft.model : '');
            body.textContent = draft.text.replace(/\*/g, '').split(/\n{2,}/).map(p => p.replace(/\n/g, ' ').trim()).filter(Boolean).join('\n');
            thoughts.textContent = draft.thoughts;
            toggle.hidden = !draft.thoughts.trim();
            if (follow) display.scrollTop = display.scrollHeight;
        }
        return {
            draft,
            apply(event) { draft.apply(event); if (!timer) timer = setTimeout(paint, 100); },
            dispose() { clearTimeout(timer); container.remove(); },
        };
    }

    const api = { Draft, consume, createView };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.StoryLiveStream = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
