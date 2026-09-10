"""Bounded history reads and stream delivery for small hosting instances."""

import hashlib
import os
import queue
import threading
from collections import deque

import ijson


class HistoryChanged(ValueError):
    pass


def _revision(stat):
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return hashlib.blake2s(repr(signature).encode(), digest_size=12).hexdigest()


def _chat_entries(source):
    try:
        yield from ijson.items(source, "item", use_float=True)
    except ijson.JSONError as exc:
        raise ValueError("Chat history contains invalid JSON") from exc


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
