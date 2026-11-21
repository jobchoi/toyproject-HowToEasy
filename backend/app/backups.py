from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth import admin
from app.database.db import get_db

router = APIRouter(prefix='/api/backups', dependencies=[Depends(admin)])
NAME = re.compile(r'backup-\d{8}T\d{12}Z-[0-9a-f]{8}\.sqlite3')


def paths(db):
    engine = db.get_bind()
    if engine.dialect.name != 'sqlite' or not engine.url.database or engine.url.database == ':memory:':
        raise HTTPException(400, '파일 SQLite DB가 필요합니다')
    path = Path(engine.url.database).resolve()
    return path, path.parent / 'backups'


def create_backup(db):
    path, folder = paths(db)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = f"backup-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{secrets.token_hex(4)}.sqlite3"
    dest = folder / name
    try:
        with sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True) as source, sqlite3.connect(dest) as target:
            source.backup(target)
        dest.chmod(0o600)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return name


@router.get('')
def list_backups(db: Session = Depends(get_db)):
    _, folder = paths(db)
    return sorted((p.name for p in folder.glob('backup-*.sqlite3') if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name)), reverse=True) if folder.exists() else []


@router.post('')
def backup(db: Session = Depends(get_db)):
    return {'name': create_backup(db)}


class RestoreIn(BaseModel):
    name: str


@router.post('/restore')
def restore(value: RestoreIn, db: Session = Depends(get_db)):
    path, folder = paths(db)
    source = folder / value.name
    if not NAME.fullmatch(value.name) or source.is_symlink() or not source.is_file():
        raise HTTPException(404, '백업을 찾을 수 없습니다')
    # Verify the file before saving or modifying the current DB.
    try:
        with sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True) as check:
            if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('integrity check failed')
            versions = {r[0] for r in check.execute('SELECT version FROM schema_migrations')}
            if versions != {'001_space_utilization', '002_weekly_responses', '003_auth', '004_history_protection'}:
                raise ValueError('schema mismatch')
    except (sqlite3.Error, ValueError) as exc:
        raise HTTPException(400, '백업 파일 또는 스키마가 유효하지 않습니다') from exc
    db.rollback()
    before = create_backup(db)
    try:
        with sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
            dst.execute('DELETE FROM staff_sessions')
            dst.commit()
    except sqlite3.Error as exc:
        raise HTTPException(500, f'복구 실패; 복구 전 백업: {before}') from exc
    return {'pre_restore_backup': before}
