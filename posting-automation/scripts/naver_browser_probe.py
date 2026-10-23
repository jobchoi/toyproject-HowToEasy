"""Interactive, temporary browser for owner-operated Naver draft feasibility checks.
No credentials, cookies, page bodies, or traces are saved by this script.
"""
import argparse
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/tmp/posting-playwright-browsers')
from playwright.sync_api import sync_playwright, Error


def configure_korean_fonts():
    """Use existing Windows fonts without changing system font configuration."""
    root = Path(__file__).resolve().parents[1] / '.local'
    fonts = root / 'fonts'
    fonts.mkdir(parents=True, exist_ok=True)
    for name in ('malgun.ttf', 'malgunbd.ttf', 'malgunsl.ttf'):
        source = Path('/mnt/c/Windows/Fonts') / name
        target = fonts / name
        if source.is_file() and not target.is_symlink() and not target.exists():
            target.symlink_to(source)
    if not any(fonts.glob('*.ttf')):
        print('한글 글꼴이 없습니다. Linux용 한글 글꼴 설치가 필요합니다.', flush=True)
        return
    cache = root / 'font-cache'
    cache.mkdir(exist_ok=True)
    config = root / 'fonts.conf'
    config.write_text(f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
<include ignore_missing="yes">/etc/fonts/fonts.conf</include>
<dir>{escape(str(fonts))}</dir>
<cachedir>{escape(str(cache))}</cachedir>
<alias><family>sans-serif</family><prefer><family>Malgun Gothic</family></prefer></alias>
</fontconfig>
''', encoding='utf-8')
    os.environ['FONTCONFIG_FILE'] = str(config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blog-id', default='somnium_quest')
    args = parser.parse_args()
    if not all(c.isascii() and (c.isalnum() or c in '_-') for c in args.blog_id):
        parser.error('Invalid blog id')
    configure_korean_fonts()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        try:
            page.goto('https://nid.naver.com/nidlogin.login', wait_until='domcontentloaded')
        except Error:
            print('로그인 페이지 연결 실패: 네트워크 및 브라우저 인증서 신뢰 설정을 확인하세요. TLS 검증은 유지합니다.', flush=True)
            browser.close()
            return 1
        print('브라우저에서 직접 로그인하세요. 비밀번호나 인증 코드를 채팅에 입력하지 마세요.', flush=True)
        print('로그인 완료 후 이 터미널로 돌아와 Enter를 누르면 글쓰기 화면을 엽니다.', flush=True)
        print('명령: Enter 또는 editor = 글쓰기 / inspect = 필드 진단 / help = 안내 / quit = 종료', flush=True)
        try:
            while True:
                try:
                    command = input('로그인 후 Enter / 명령> ').strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if command == 'quit':
                    break
                if command in ('', 'editor'):
                    try:
                        page.goto(f'https://blog.naver.com/{args.blog_id}?Redirect=Write', wait_until='domcontentloaded')
                        print('글쓰기 화면에서 시험 원고를 직접 입력하고 임시저장할 수 있습니다.', flush=True)
                        print('자동 입력·저장 기능은 아직 없습니다. inspect는 편집 필드 진단용입니다.', flush=True)
                    except Error:
                        print('글쓰기 화면 연결 실패. 브라우저의 로그인·네트워크 상태를 확인하고 editor로 다시 시도하세요.', flush=True)
                elif command == 'inspect':
                    # Only editor field metadata; never read field values or login forms.
                    for frame in page.frames:
                        if not frame.url.startswith('https://blog.naver.com/'):
                            continue
                        fields = frame.locator('[contenteditable="true"]').evaluate_all('''els => els.map(e => ({tag:e.tagName, role:e.getAttribute('role'), class:e.className, placeholder:e.getAttribute('data-placeholder')}))''')
                        print(json.dumps({'editable_fields': fields}, ensure_ascii=False), flush=True)
                elif command == 'help':
                    print('Enter/editor: 글쓰기 화면 열기. inspect: 필드 진단. quit: 브라우저 종료.', flush=True)
                    print('진단 도구이며 자동 원고 입력·임시저장·발행 기능은 아직 없습니다.', flush=True)
                elif command:
                    print('알 수 없는 명령입니다. help를 입력하세요.', flush=True)
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    raise SystemExit(main())
