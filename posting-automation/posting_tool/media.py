"""Local immutable raster assets; never fetch remote image URLs."""
import base64
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit

ASSET = re.compile(r'assets/[0-9a-f]{64}\.(?:png|jpg|gif|webp)')
IMAGE = re.compile(r'^!\[([^\]\n]*)\]\((assets/[0-9a-f]{64}\.(?:png|jpg|gif|webp))\)$')


def validate_image(block):
    if not isinstance(block.get('src'),str) or not ASSET.fullmatch(block['src']):
        raise ValueError('업로드한 사진을 선택하세요.')
    for key in ('text', 'caption', 'source'):
        value = block.get(key, '')
        if not isinstance(value, str) or len(value) > 1000 or any(c in value for c in '\r\n\x00'):
            raise ValueError('사진 설명·캡션·출처는 줄바꿈 없이 1,000자 이하로 입력하세요.')
    if any(c in block['text'] for c in '[]'):
        raise ValueError('사진 대체 설명에는 대괄호를 사용할 수 없습니다.')
    source = block.get('source', '')
    if source:
        url = urlsplit(source)
        if url.scheme not in {'http', 'https'} or not url.hostname or url.username or any(c.isspace() for c in source):
            raise ValueError('사진 출처는 http 또는 https 주소를 입력하세요.')
    return {k: block.get(k, '').strip() for k in ('type', 'text', 'src', 'caption', 'source')}


def image_markdown(block):
    b = validate_image(block)
    return f'![{b["text"]}]({b["src"]})\n사진 설명: {b["caption"]}\n사진 출처: {b["source"]}'


def references(markdown):
    return set(m[2] for line in markdown.splitlines() if (m := IMAGE.fullmatch(line)))


def upload(root, encoded):
    if not isinstance(encoded, str) or len(encoded) > 960_000:
        raise ValueError('사진은 700KB 이하로 줄여 주세요.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ValueError('사진 데이터 형식을 확인하세요.') from None
    if not raw or len(raw) > 700_000:
        raise ValueError('사진은 700KB 이하로 줄여 주세요.')
    if raw.startswith(b'\x89PNG\r\n\x1a\n'): ext = 'png'
    elif raw.startswith(b'\xff\xd8\xff'): ext = 'jpg'
    elif raw.startswith((b'GIF87a', b'GIF89a')): ext = 'gif'
    elif raw.startswith(b'RIFF') and raw[8:12] == b'WEBP': ext = 'webp'
    else: raise ValueError('PNG/JPEG/GIF/WebP 사진만 지원합니다. SVG는 지원하지 않습니다.')
    name = hashlib.sha256(raw).hexdigest() + '.' + ext
    folder = Path(root) / 'assets'
    folder.mkdir(exist_ok=True)
    path = folder / name
    # Same content hash always represents the same immutable bytes.
    try:
        with path.open('xb') as stream: stream.write(raw)
    except FileExistsError:
        pass
    return {'src': 'assets/' + name}


def embedded(root, markdown):
    result = {}
    names = references(markdown)
    if len(names) > 20: raise ValueError('원고당 사진은 20개 이하로 추가하세요.')
    total = 0
    for name in names:
        path = Path(root) / name
        if not path.is_file(): raise ValueError('원고의 사진 파일이 없습니다. 사진을 다시 추가하세요.')
        total += path.stat().st_size
        if total > 10_000_000: raise ValueError('사진 전체 크기는 10MB 이하로 줄여 주세요.')
        mime = {'jpg':'jpeg'}.get(path.suffix[1:], path.suffix[1:])
        result[name] = 'data:image/' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    return result
