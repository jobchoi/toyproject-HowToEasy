"""Bounded, read-only imports from an explicit allowed root."""
import hashlib
from pathlib import Path
from .models import Source

MAX_FILE_BYTES = 256_000
MAX_FILES = 20
MAX_TOTAL_BYTES = 1_000_000


def import_sources(root: Path, bundle: str) -> tuple[Source, ...]:
    root = Path(root).resolve(strict=True)
    relative = Path(bundle)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('자료는 허용 루트 내부의 상대 경로여야 합니다.')
    folder = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('심볼릭 링크 자료 경로는 허용하지 않습니다.')
    if not folder.is_dir() or not folder.resolve().is_relative_to(root):
        raise ValueError('자료 폴더를 확인하세요.')
    paths = sorted(folder.iterdir())
    if any(p.is_symlink() for p in paths):
        raise ValueError('자료 묶음에 심볼릭 링크가 있습니다.')
    files = [p for p in paths if p.is_file() and p.suffix.lower() in {'.md', '.txt'}]
    if not files or len(files) > MAX_FILES:
        raise ValueError('Markdown/TXT 파일은 1~20개가 필요합니다. 하위 폴더는 읽지 않습니다.')
    sources, total = [], 0
    for path in files:
        before = path.stat()
        if before.st_size > MAX_FILE_BYTES:
            raise ValueError(f'{path.name}: 파일은 256KB 이하만 허용합니다.')
        with path.open('rb') as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        after = path.stat()
        if len(raw) > MAX_FILE_BYTES or (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError(f'{path.name}: 파일이 너무 크거나 읽는 중 변경되었습니다.')
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('자료 전체 크기는 1MB 이하로 제한합니다.')
        try:
            text = raw.decode('utf-8-sig').strip()
        except UnicodeDecodeError:
            raise ValueError(f'{path.name}: UTF-8 파일이 필요합니다.') from None
        if not text or '\x00' in text:
            raise ValueError(f'{path.name}: 비어 있거나 텍스트 형식이 아닙니다.')
        sources.append(Source(path.relative_to(root).as_posix(), hashlib.sha256(raw).hexdigest(), text))
    return tuple(sources)
