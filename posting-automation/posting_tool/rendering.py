"""Deliberately small Markdown renderer; all user HTML remains escaped text."""
from html import escape
import re
from .styles import style_css, appearance_css


def render_html(markdown: str, images=None) -> str:
    blocks, paragraph, listing = [], [], []
    def flush():
        if paragraph:
            blocks.append('<p>' + '<br>'.join(escape(x) for x in paragraph) + '</p>')
            paragraph.clear()
        if listing:
            blocks.append('<ul>' + ''.join('<li>' + escape(x) + '</li>' for x in listing) + '</ul>')
            listing.clear()
    from .documents import from_markdown
    from .media import validate_image, IMAGE
    photos = iter(b for b in from_markdown(markdown) if b['type']=='image')
    metadata = 0
    for line in markdown.splitlines():
        if metadata and line.startswith(('사진 설명: ', '사진 출처: ')):
            metadata -= 1
            continue
        metadata = 0
        if IMAGE.fullmatch(line):
            flush()
            metadata = 2
            try: b = validate_image(next(photos))
            except ValueError:
                blocks.append('<p>사진 정보 형식을 확인하세요.</p>'); continue
            src = escape((images or {}).get(b['src'], b['src']), quote=True)
            source = ('<a href="' + escape(b['source'], quote=True) + '" rel="noreferrer noopener">출처</a>') if b['source'] else '출처 미입력'
            blocks.append('<figure><img src="' + src + '" alt="' + escape(b['text'], quote=True) + '"><figcaption>' + escape(b['caption']) + ' · ' + source + '</figcaption></figure>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        bullet = re.match(r'^[-*]\s+(.+)$', line)
        if heading:
            flush()
            level = len(heading[1])
            blocks.append(f'<h{level}>' + escape(heading[2]) + f'</h{level}>')
        elif line.strip() == '---':
            flush()
            blocks.append('<hr>')
        elif bullet:
            if paragraph:
                flush()
            listing.append(bullet[1])
        elif not line.strip():
            flush()
        else:
            if listing:
                flush()
            paragraph.append(line)
    flush()
    return '\n'.join(blocks)


def preview_document(title: str, markdown: str, warnings: tuple[str, ...], *, show_notices: bool = True, style: str = 'plain', appearance=None, images=None) -> str:
    notices = ''.join('<li>' + escape(w) + '</li>' for w in warnings)
    notice = ('<aside><strong>게시 전 검토용 · 규칙 기반 변환 · 외부 업로드 없음</strong><ul>' + notices + '</ul></aside>') if show_notices else ''
    return ('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; style-src &apos;unsafe-inline&apos;; img-src data:; base-uri &apos;none&apos;; form-action &apos;none&apos;">'
            '<title>' + escape(title) + '</title><style>'
            'body{max-width:800px;margin:40px auto;padding:0 24px;font:17px/1.8 sans-serif;color:#243143}'
            'img{max-width:100%;height:auto}figure{margin:24px 0}figcaption{font-size:.85em;overflow-wrap:anywhere}aside{background:#fff3d6;padding:16px;border-radius:8px}h1,h2,h3{line-height:1.4}hr{margin:32px 0}'
            + style_css(style) + appearance_css(appearance) + '</style><body>' + notice + '<main>' + render_html(markdown, images) + '</main></body></html>')
