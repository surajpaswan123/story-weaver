"""Replay a running turn from disk without retaining another full draft in RAM."""

import json
import struct
import tempfile
import threading
import time

from starlette.responses import StreamingResponse
from runtime_support import StoryStreamingResponse


class StreamJournal:
    def __init__(self, run_id, turn_index):
        self.run_id = run_id
        self.turn_index = turn_index
        # Outside story folders: never included in context, backups or cloud sync.
        self.file = tempfile.TemporaryFile(mode='w+b')
        self.condition = threading.Condition()
        self.size = 0
        self.finished_at = None
        self.failed = False

    def append(self, event):
        data = event.encode('utf-8')
        with self.condition:
            self.file.seek(self.size)
            self.file.write(b'SWEV' + struct.pack('>I', len(data)) + data + b'SWEN')
            self.file.flush()
            self.size += len(data) + 12
            self.condition.notify_all()

    def valid_cursor(self, after):
        with self.condition:
            if after == 0:
                return True
            if after < 12 or after > self.size:
                return False
            self.file.seek(after - 4)
            if self.file.read(4) != b'SWEN':
                return False
            return after == self.size or self.file.read(4) == b'SWEV'

    def finish(self):
        with self.condition:
            self.finished_at = time.monotonic()
            self.condition.notify_all()

    def read(self, after, detached):
        while not detached.is_set():
            with self.condition:
                if after == self.size:
                    if self.finished_at is not None:
                        return
                    self.condition.wait(timeout=0.1)
                    continue
                self.file.seek(after)
                header = self.file.read(8)
                if header[:4] != b'SWEV':
                    raise ValueError('Invalid generation cursor')
                size = struct.unpack('>I', header[4:])[0]
                if size > self.size - after - 12:
                    raise ValueError('Invalid generation cursor')
                event = self.file.read(size).decode('utf-8')
                after += size + 12
            yield f'id: {after}\n{event}'

    def response(self, after=0):
        return ReplayResponse(self, after)


class ReplayResponse(StoryStreamingResponse):
    """Only the subscription ends on disconnect; the journal worker owns saving."""

    def __init__(self, journal, after):
        self.detached = threading.Event()
        self.relay = journal.read(after, self.detached)
        StreamingResponse.__init__(self, self.relay, media_type='text/event-stream',
                                   headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


class LiveStreams:
    def __init__(self, max_finished=16, finished_ttl=600):
        self.records = {}
        self.lock = threading.RLock()
        self.max_finished = max_finished
        self.finished_ttl = finished_ttl

    def _prune(self):
        finished = sorted((r.finished_at, key) for key, r in self.records.items()
                          if r.finished_at is not None)
        for index, (when, key) in enumerate(finished):
            if time.monotonic() - when > self.finished_ttl or index < len(finished) - self.max_finished:
                self.records.pop(key, None)

    def get(self, key, run_id):
        with self.lock:
            self._prune()
            journal = self.records.get(key)
            return journal if journal and not journal.failed and journal.run_id == run_id else None

    def start(self, key, run_id, turn_index, source):
        journal = StreamJournal(run_id, turn_index)
        with self.lock:
            self._prune()
            self.records[key] = journal

        def pump():
            try:
                for event in source:
                    if not journal.failed:
                        try:
                            journal.append(event)
                        except OSError:
                            # Live delivery is optional. Never abort generation or
                            # skip its save steps because the replay disk failed.
                            journal.failed = True
                            journal.finish()
            except Exception:
                if not journal.failed:
                    journal.append('data: ' + json.dumps({'type': 'error', 'message':
                        'Generation ended unexpectedly. Check the saved story before retrying.'}) + '\n\n')
            finally:
                try:
                    close = getattr(source, 'close', None)
                    if close:
                        close()
                finally:
                    journal.finish()
                    with self.lock:
                        self._prune()

        try:
            threading.Thread(target=pump, daemon=True, name='story-journal-worker').start()
        except Exception:
            journal.failed = True
            journal.finish()
            with self.lock:
                self.records.pop(key, None)
            raise
        return journal
