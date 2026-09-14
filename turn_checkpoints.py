"""Durable turn backups. All operations require the application's story lock.

Reference files are compressed; manuscript/chat history is restored from verified
prefixes rather than storing a complete book copy for every turn.
"""
import base64
import hashlib
import json
import zlib
from pathlib import Path

HISTORY = '_turn_undo.json'
PENDING = '_turn_undo_pending.json'
JOURNAL = '_undo_journal.json'
INTERNAL = {HISTORY, PENDING, JOURNAL, '_sync_meta.json', 'pending_retry.json'}
MAX_REFERENCE_BYTES = 64 * 1024 * 1024


class CheckpointError(ValueError):
    pass


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def safe_name(name):
    return (isinstance(name, str) and name.lower().endswith(('.md', '.json'))
            and not any(c in name for c in '/\\:') and not name.startswith('temp_')
            and name.rsplit('.', 1)[0].casefold() not in {'.', '..', 'con', 'prn', 'aux', 'nul',
                *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))})


class TurnCheckpoints:
    def __init__(self, folder, write_text):
        self.folder, self.write_text = Path(folder), write_text

    def read(self, name, default=''):
        path = self.folder / name
        if path.is_symlink():
            raise CheckpointError('A story file is a symbolic link; refusing to overwrite it.')
        return path.read_text(encoding='utf-8') if path.is_file() else default

    def references(self):
        return {p.name: self.read(p.name) for p in self.folder.iterdir()
                if p.is_file() and safe_name(p.name)
                and p.name not in INTERNAL | {'story.md', 'chat_log.json'}}

    def _apply(self, files):
        for name, text in files.items():
            if text is None:
                (self.folder / name).unlink(missing_ok=True)
            else:
                self.write_text(str(self.folder / name), text)

    def _validate(self, files):
        if not isinstance(files, dict) or any(not safe_name(n) or n == JOURNAL
                or (t is not None and not isinstance(t, str)) for n, t in files.items()):
            raise CheckpointError('Invalid file-operation journal.')

    def recover(self):
        raw = self.read(JOURNAL)
        if raw:
            before = json.loads(raw)['before']
            self._validate(before)
            self._apply(before)
            (self.folder / JOURNAL).unlink()

    def transaction(self, changes):
        self.recover()
        self._validate(changes)
        before = {name: self.read(name, None) for name in changes}
        self.write_text(str(self.folder / JOURNAL), dumps({'before': before}))
        try:
            self._apply(changes)
            (self.folder / JOURNAL).unlink()
        except Exception:
            # Keep the journal if rollback also fails. The next story access
            # must recover it before reading or syncing any partially changed files.
            self._apply(before)
            (self.folder / JOURNAL).unlink()
            raise

    def history(self):
        value = json.loads(self.read(HISTORY, '{"version":1,"turns":[]}'))
        if (not isinstance(value, dict) or value.get('version') != 1
                or not isinstance(value.get('turns'), list)
                or any(not isinstance(t, dict) or t.get('version') != 1
                       or not isinstance(t.get('references'), str) for t in value['turns'])):
            raise CheckpointError('The saved turn history is invalid.')
        return value['turns']

    def begin(self):
        self.recover()
        story = self.read('story.md')
        entries = json.loads(self.read('chat_log.json', '[]'))
        if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
            raise CheckpointError('Chat history is invalid; cannot save a turn backup.')
        raw = dumps(self.references()).encode('utf-8')
        if len(raw) > MAX_REFERENCE_BYTES:
            raise CheckpointError('Reference files exceed the 64 MiB checkpoint limit.')
        record = {'version': 1, 'story_chars': len(story), 'story_before': digest(story),
                  'chat_count': len(entries), 'chat_before': digest(dumps(entries)),
                  'references': base64.b64encode(zlib.compress(raw, 3)).decode('ascii'),
                  'references_hash': hashlib.sha256(raw).hexdigest()}
        # Starting or failing a request never replaces completed-turn history.
        self.write_text(str(self.folder / PENDING), dumps(record))

    def commit(self, original_story, updated_story, entries):
        self.recover()
        changes = {'story.md': updated_story, 'chat_log.json': dumps(entries)}
        raw = self.read(PENDING)
        if raw:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise CheckpointError('The pending turn backup is invalid.')
            count = record.get('chat_count')
            if (record.get('version') != 1 or not isinstance(count, int) or count < 0
                    or len(entries) != count + 2 or entries[-2].get('role') != 'user'
                    or record.get('story_before') != digest(original_story)
                    or record.get('chat_before') != digest(dumps(entries[:count]))):
                raise CheckpointError('Story changed since generation began; cannot commit its turn safely.')
            record.update(story_after=digest(updated_story), chat_after=digest(dumps(entries)))
            turns = self.history() + [record]
            while len(turns) > 1 and (len(turns) > 20 or
                    sum(len(t['references']) for t in turns) > 8 * 1024 * 1024):
                turns.pop(0)
            changes.update({HISTORY: dumps({'version': 1, 'turns': turns}), PENDING: None})
        self.transaction(changes)

    def undo(self, story, entries, retry=None):
        self.recover()
        turns = self.history()
        if not turns:
            raise CheckpointError('This turn has no reliable saved file state. It may predate the undo update '
                                  'or its backup is unavailable. Nothing was changed. New completed turns '
                                  'will save backups for Undo and Regenerate.')
        record = turns[-1]
        if record.get('story_after') != digest(story) or record.get('chat_after') != digest(dumps(entries)):
            raise CheckpointError('The saved backup does not match the latest story turn. Nothing was changed.')
        chars, count = record.get('story_chars'), record.get('chat_count')
        if (not isinstance(chars, int) or not 0 <= chars <= len(story)
                or not isinstance(count, int) or not 0 <= count < len(entries)):
            raise CheckpointError('Invalid turn boundaries in the saved backup. Nothing was changed.')
        previous_story, previous_chat = story[:chars], entries[:count]
        if (digest(previous_story) != record.get('story_before')
                or digest(dumps(previous_chat)) != record.get('chat_before')):
            raise CheckpointError('The earlier story was edited after this turn. Nothing was changed.')
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(base64.b64decode(record['references'], validate=True), MAX_REFERENCE_BYTES + 1)
            if len(raw) > MAX_REFERENCE_BYTES or not decoder.eof or decoder.unused_data:
                raise ValueError('Incomplete or oversized backup')
            if hashlib.sha256(raw).hexdigest() != record['references_hash']:
                raise ValueError('Backup checksum mismatch')
            references = json.loads(raw)
            if not isinstance(references, dict) or any(not safe_name(n)
                    or n in INTERNAL | {'story.md', 'chat_log.json'} or not isinstance(t, str)
                    for n, t in references.items()):
                raise ValueError('Invalid reference file map')
        except (KeyError, ValueError, TypeError, zlib.error) as exc:
            raise CheckpointError('The reference-file backup is incomplete or damaged. Nothing was changed.') from exc
        changes = {name: None for name in self.references() if name not in references}
        changes.update(references)
        changes.update({'story.md': previous_story, 'chat_log.json': dumps(previous_chat),
                        HISTORY: dumps({'version': 1, 'turns': turns[:-1]}), PENDING: None,
                        'pending_retry.json': dumps(retry) if retry else None})
        self.transaction(changes)
        return len(references)
