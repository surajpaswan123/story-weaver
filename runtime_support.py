"""Bounded history reads and stream delivery for small hosting instances."""

import hashlib
import json
import os
import queue
import re
import threading
import time
from collections import deque

import ijson


class TurnProgress:
    """Small process-local status records; never retain prompts or streamed text."""

    def __init__(self, max_finished=128, finished_ttl=3600):
        self.records = {}
        self.lock = threading.RLock()
        self.max_finished = max_finished
        self.finished_ttl = finished_ttl

    def _prune(self):
        now = time.time()
        finished = sorted((r['updated_at'], key) for key, r in self.records.items() if not r['active'])
        for index, (updated, key) in enumerate(finished):
            if now - updated > self.finished_ttl or index < len(finished) - self.max_finished:
                self.records.pop(key, None)

    def start(self, key, token, execution='server'):
        with self.lock:
            self._prune()
            now = time.time()
            self.records[key] = dict(token=token, run_id=hashlib.sha256(token.encode()).hexdigest()[:20],
                                     active=True, worker=False, state='starting', outcome=None,
                                     execution=execution, started_at=now, updated_at=now)

    def update(self, key, token, state=None, outcome=None, worker=None):
        with self.lock:
            record = self.records.get(key)
            if not record or record['token'] != token or not record['active']:
                return
            if state and state != record['state']:
                record.update(state=state, updated_at=time.time())
            if outcome:
                record['outcome'] = outcome
            if worker is not None:
                record['worker'] = worker

    def worker_is_running(self, key, token):
        with self.lock:
            record = self.records.get(key)
            return bool(record and record['token'] == token and record['active'] and record['worker'])

    def finish(self, key, token, outcome=None):
        with self.lock:
            record = self.records.get(key)
            if record and record['token'] == token and record['active']:
                record.update(active=False, worker=False, state=outcome or record['outcome'] or 'interrupted', updated_at=time.time())
            self._prune()

    def status(self, key, active_token=None):
        with self.lock:
            self._prune()
            record = self.records.get(key)
            if not record or (active_token and record['token'] != active_token):
                return {'active': bool(active_token), 'state': 'generating' if active_token else 'idle', 'run_id': ''}
            if not active_token and record['active']:
                self.finish(key, record['token'], outcome='interrupted')
            return {name: record[name] for name in ('active', 'state', 'run_id', 'execution', 'started_at', 'updated_at')}

    def track(self, key, token, source):
        self.update(key, token, state='generating', worker=True)
        try:
            for event in source:
                # Chunk payloads can be large. Their text never enters status storage.
                if isinstance(event, str) and event.startswith('data: {"type": "chunk"'):
                    self.update(key, token, state='generating')
                elif isinstance(event, str) and event.startswith('data: '):
                    try:
                        kind = json.loads(event[6:]).get('type')
                    except (ValueError, AttributeError):
                        kind = None
                    if kind in {'finalizing', 'retrying'}:
                        self.update(key, token, state=kind)
                    elif kind in {'done', 'error', 'stopped'}:
                        outcome = {'done': 'completed', 'error': 'failed', 'stopped': 'stopped'}[kind]
                        # The worker still needs to finish its final storage sync.
                        self.update(key, token, state='finalizing', outcome=outcome)
                yield event
        finally:
            self.update(key, token, worker=False)
            close = getattr(source, 'close', None)
            if close:
                close()


class HistoryChanged(ValueError):
    pass


def _revision(stat):
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return hashlib.blake2s(repr(signature).encode(), digest_size=12).hexdigest()


def file_revision(path):
    """Small optimistic-concurrency token; no copy of the file body is needed."""
    return _revision(os.stat(path))


_LINE_BREAK = re.compile(r"\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")


def text_metadata(chunks):
    """Match len(text), splitlines() and strip() without retaining whole lines."""
    chars = breaks = 0
    nonempty = previous_cr = ends_in_break = False
    for chunk in chunks:
        if not chunk:
            continue
        chars += len(chunk)
        breaks += sum(1 for _ in _LINE_BREAK.finditer(chunk))
        if previous_cr and chunk.startswith("\n"):
            breaks -= 1  # A CRLF can span two chunks.
        previous_cr = chunk.endswith("\r")
        ends_in_break = bool(_LINE_BREAK.fullmatch(chunk[-1]))
        nonempty = nonempty or not chunk.isspace()
    return {"chars": chars, "lines": breaks + int(bool(chars) and not ends_in_break),
            "empty": not nonempty}


def file_metadata(path, chunk_size=64 * 1024):
    """Read metadata in bounded chunks, even for a multi-megabyte single line."""
    with open(path, "r", encoding="utf-8") as handle:
        return text_metadata(iter(lambda: handle.read(chunk_size), ""))


def _chat_entries(source):
    try:
        yield from ijson.items(source, "item", use_float=True)
    except ijson.JSONError as exc:
        raise ValueError("Chat history contains invalid JSON") from exc


def count_ai_turns(path):
    """Count completed AI turns without loading the whole chat log into memory."""
    count = 0
    with open(path, "rb") as source:
        for entry in _chat_entries(source):
            if not isinstance(entry, dict):
                raise ValueError("Chat history contains an invalid entry")
            if entry.get("role") == "ai":
                count += 1
    return count


def recent_ai_text(path, num_turns=10):
    """Return the same recent-AI prose as the old json.load path, but bounded.

    Positive num_turns retains only that many AI entries while parsing. A
    non-positive value preserves the historical "all AI turns" behavior.
    """
    limit = int(num_turns)
    recent = deque(maxlen=limit if limit > 0 else None)
    with open(path, "rb") as source:
        for entry in _chat_entries(source):
            if not isinstance(entry, dict):
                raise ValueError("Chat history contains an invalid entry")
            if entry.get("role") != "ai":
                continue
            text = entry.get("text", "")
            if not isinstance(text, str):
                raise ValueError("Chat history contains non-text content")
            if text.strip():
                recent.append(text)
    return "\n\n".join(text.strip() for text in recent if text.strip())


def read_chat_page(path, last=40, before=None, after=None, revision=None, max_chars=256_000):
    """Parse one entry at a time; retain only a bounded page of complete entries."""
    last = max(1, min(int(last), 100))
    if before is not None and after is not None:
        raise ValueError("Use either before or after, not both")
    page, chars, total, turns = deque(), 0, 0, 0
    last_user_prompt = ""
    forward_full = False
    with open(path, "rb") as source:
        current_revision = _revision(os.fstat(source.fileno()))
        if revision and revision != current_revision:
            raise HistoryChanged("History changed. Reload the latest turns before browsing further.")
        # ijson.items on an object would otherwise look like an empty history.
        while True:
            initial = source.read(1)
            if initial not in (b" ", b"\r", b"\n", b"\t"):
                break
        if initial != b"[":
            raise ValueError("Chat history must be a JSON array")
        source.seek(0)
        for entry in _chat_entries(source):
            if not isinstance(entry, dict) or entry.get("role") not in {"user", "ai"}:
                raise ValueError("Chat history contains an invalid entry")
            if not isinstance(entry.get("text", ""), str):
                raise ValueError("Chat history contains non-text content")
            entry["turn_index"] = turns
            if entry["role"] == "ai":
                turns += 1
            else:
                last_user_prompt = entry.get("text", "")
            eligible = (before is None or total < before) and (after is None or total >= after)
            if eligible:
                size = len(entry.get("text", "")) + len(str(entry.get("model_thoughts", "")))
                if after is None:
                    page.append((total, entry, size))
                    chars += size
                    while len(page) > last or (len(page) > 1 and chars > max_chars):
                        chars -= page.popleft()[2]
                elif not forward_full:
                    if page and (len(page) >= last or chars + size > max_chars):
                        forward_full = True
                    else:
                        page.append((total, entry, size))
                        chars += size
            total += 1
    if _revision(os.stat(path)) != current_revision:
        raise HistoryChanged("History changed while loading. Reload the latest turns.")
    end = page[-1][0] + 1 if page else min(before if before is not None else total, total)
    start = page[0][0] if page else end
    return {"messages": [entry for _, entry, _ in page], "start_index": start,
            "end_index": end, "total_entries": total, "total_turns": turns,
            "revision": current_revision, "last_user_prompt": last_user_prompt}


def relay_stream(gen, max_queue=16):
    """Bound delivery memory; finish saving in the worker after UI disconnects."""
    events = queue.Queue(maxsize=max_queue)
    detached = threading.Event()

    def deliver(event):
        while not detached.is_set():
            try:
                events.put(event, timeout=0.1)
                return
            except queue.Full:
                pass

    def pump():
        try:
            for item in gen:
                deliver(("item", item))
        except Exception as exc:
            deliver(("error", exc))
        finally:
            deliver(("done", None))

    threading.Thread(target=pump, daemon=True, name="story-stream-worker").start()
    try:
        while True:
            kind, item = events.get()
            if kind == "done":
                return
            if kind == "error":
                raise item
            yield item
    finally:
        detached.set()
        # Release buffered text immediately. The worker still runs all save steps.
        while True:
            try:
                events.get_nowait()
            except queue.Empty:
                break


def heartbeat_stream(stream, heartbeat, interval=15, max_queue=16):
    """Keep idle connections alive and release the pump when a turn is stopped."""
    events = queue.Queue(maxsize=max_queue)
    stopped = threading.Event()

    def deliver(event):
        while not stopped.is_set():
            try:
                events.put(event, timeout=0.1)
                return True
            except queue.Full:
                pass
        return False

    def pump():
        try:
            for item in stream:
                if not deliver((False, item)):
                    break
        except Exception as exc:
            deliver((True, exc))
        finally:
            close = getattr(stream, "close", None)
            if close:
                try:
                    close()
                except Exception:
                    pass
            deliver((False, None))

    threading.Thread(target=pump, daemon=True, name="provider-stream-reader").start()
    try:
        while True:
            try:
                failed, item = events.get(timeout=interval)
            except queue.Empty:
                yield heartbeat
                continue
            if failed:
                raise item
            if item is None:
                return
            yield item
    finally:
        stopped.set()
