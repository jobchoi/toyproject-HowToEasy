"""Deliberately small Markdown renderer; all user HTML remains escaped text."""
from html import escape
import re
from .styles import style_css, appearance_css


def render_html(markdown: str) -> str:
    blocks, paragraph, listing = [], [], []
    def flush():
        if paragraph:
            blocks.append('<p>' + '<br>'.join(escape(x) for x in paragraph) + '</p>')
            paragraph.clear()
        if listing:
            blocks.append('<ul>' + ''.join('<li>' + escape(x) + '</li>' for x in listing) + '</ul>')
            listing.clear()
    for line in markdown.splitlines():
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


def preview_document(title: str, markdown: str, warnings: tuple[str, ...], *, show_notices: bool = True, style: str = 'plain', appearance=None) -> str:
    notices = ''.join('<li>' + escape(w) + '</li>' for w in warnings)
    notice = ('<aside><strong>게시 전 검토용 · 규칙 기반 변환 · 외부 업로드 없음</strong><ul>' + notices + '</ul></aside>') if show_notices else ''
    return ('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; style-src &apos;unsafe-inline&apos;; base-uri &apos;none&apos;; form-action &apos;none&apos;">'
            '<title>' + escape(title) + '</title><style>'
            'body{max-width:800px;margin:40px auto;padding:0 24px;font:17px/1.8 sans-serif;color:#243143}'
            'aside{background:#fff3d6;padding:16px;border-radius:8px}h1,h2,h3{line-height:1.4}hr{margin:32px 0}'
            + style_css(style) + appearance_css(appearance) + '</style><body>' + notice + '<main>' + render_html(markdown) + '</main></body></html>')
