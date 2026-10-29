"""Small, testable draft contract and persistent trial journal."""
from contextlib import contextmanager
import hashlib
import json
import os
import sys
import sqlite3
from pathlib import Path, PureWindowsPath


def read_draft(path):
    path = Path(path)
    if path.stat().st_size > 256_000:
        raise ValueError('원고 파일은 256KB 이하로 제한합니다.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'title', 'body'}:
        raise ValueError('JSON에는 title, body 두 필드만 필요합니다.')
    for key, limit in [('title', 200), ('body', 100_000)]:
        if not isinstance(data[key], str) or not data[key].strip() or len(data[key]) > limit:
            raise ValueError(f'{key} 값이 비어 있거나 길이 제한을 초과했습니다.')
    return data


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trials (key TEXT PRIMARY KEY, state TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def key(blog_id, draft):
        return hashlib.sha256(json.dumps([blog_id, draft], ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def state(self, key):
        with self.connect() as db:
            row = db.execute('SELECT state FROM trials WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def claim(self, key):
        # No reset/retry command: an interrupted save needs manual reconciliation.
        with self.connect() as db:
            try:
                db.execute('INSERT INTO trials VALUES (?, ?)', (key, 'save_requested'))
            except sqlite3.IntegrityError:
                raise ValueError('이 원고는 이미 저장을 요청했습니다. 네이버 임시저장 목록에서 먼저 확인하세요.') from None

    def finish(self, key, state):
        if state not in {'needs_verification', 'uncertain', 'verified_by_user'}:
            raise ValueError('Invalid state')
        with self.connect() as db:
            db.execute('UPDATE trials SET state=? WHERE key=?', (state, key))


def comparable_text(text):
    """Ignore browser-created blank layout lines, preserve nonempty line order."""
    return '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').replace('\u00a0', ' ').split('\n') if line.strip())


def journal_path(project_root, *, platform=None, environ=None):
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    if platform == 'win32':
        local = environ.get('LOCALAPPDATA', '')
        location = PureWindowsPath(local)
        if not location.is_absolute() or location.drive.startswith('\\\\'):
            raise ValueError('Windows 로컬 LOCALAPPDATA 경로가 필요합니다.')
        return Path(local) / 'HowToEasyPosting' / 'state' / 'trials.sqlite3'
    return Path(project_root) / '.local' / 'trials.sqlite3'
