"""Interactive, temporary browser for owner-operated Naver draft feasibility checks.
No credentials, cookies, page bodies, or traces are saved by this script.
"""
import argparse
import json
import os
import sys
import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(Path(__file__).resolve().parents[1] / '.local/browsers'))
from playwright.sync_api import sync_playwright, Error


def configure_korean_fonts():
    """Use existing Windows fonts without changing system font configuration."""
    if sys.platform == 'win32':
        return  # Windows uses its installed Korean fonts.
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
    from naver_trial_support import Journal, read_draft, comparable_text
    parser = argparse.ArgumentParser()
    parser.add_argument('--blog-id', default='somnium_quest')
    parser.add_argument('--diagnose', action='store_true', help='로그인 없이 DNS/HTTPS/브라우저 접속 진단')
    parser.add_argument('--channel', choices=('chromium', 'chrome', 'msedge'), default='chromium', help='이미 설치된 Chrome/Edge 선택 가능')
    parser.add_argument('--draft', type=Path, default=Path(__file__).resolve().parents[1] / 'examples/naver-trial.json')
    args = parser.parse_args()
    if not args.blog_id or not all(c.isascii() and (c.isalnum() or c in '_-') for c in args.blog_id):
        parser.error('Invalid blog id')
    if args.diagnose:
        from browser_diagnostics import system_check
        system_check()
    else:
        from naver_trial_support import journal_path
        try:
            draft = read_draft(args.draft)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        try:
            journal = Journal(journal_path(Path(__file__).resolve().parents[1]))
        except (OSError, ValueError, sqlite3.OperationalError):
            print('작업 기록 DB를 열 수 없습니다. 다른 시험 도구를 종료하고 로컬 저장 경로를 확인하세요.')
            print('기존 DB는 삭제하지 마세요. 잠김 또는 저장 경로 문제를 해결한 뒤 재실행하세요.')
            return 1
        key = journal.key(args.blog_id, draft)
    configure_korean_fonts()
    help_text = ('Enter/editor: 내 블로그 열기 | tabs: 탭 목록 | use 번호: 작업 탭 선택 | inspect: 필드 번호 확인 | '
                 'fill 제목번호 본문번호: 시험 원고 입력 | save: 임시저장 요청 | '
                 'verified: 재열기 확인 기록 | status: 작업 상태 | quit: 종료')
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=args.diagnose, channel=args.channel)
        except Error as exc:
            message = str(exc)
            if 'missing dependencies' in message:
                print('Chromium 실행에 필요한 OS 라이브러리가 없습니다.')
                print('Ubuntu 24.04 기준:')
                print('  sudo apt-get update')
                print('  sudo apt-get install -y libnspr4 libnss3 libasound2t64')
                print('설치 후 bash scripts/run_browser.sh를 다시 실행하세요.')
            else:
                print('Chromium 실행 실패. 아래 진단을 확인하세요.')
                print(message)
            return 1
        if args.diagnose:
            from browser_diagnostics import browser_check
            try:
                return browser_check(browser)
            finally:
                browser.close()
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        fields = []
        selection = None
        try:
            try:
                page.goto('https://nid.naver.com/nidlogin.login', wait_until='domcontentloaded')
            except Error as exc:
                import re
                detail = str(exc)
                code = re.search(r'net::[A-Z_]+', detail)
                if code:
                    print('로그인 페이지 연결 실패:', code.group())
                elif 'Timeout' in detail or 'timeout' in detail:
                    print('로그인 페이지 연결 실패: NAVIGATION_TIMEOUT')
                else:
                    print('로그인 페이지 연결 실패: NAVIGATION_ERROR')
                if code and code.group() in {'net::ERR_CERT_AUTHORITY_INVALID', 'net::ERR_CERT_WEAK_SIGNATURE_ALGORITHM'}:
                    print('브라우저가 인증서 발급기관을 신뢰하지 못합니다. 보안 프록시/기관 인증서 설정을 확인해야 합니다.')
                    print('이 도구는 인증서 검증을 끄지 않습니다.')
                print('오류 코드를 알려주세요. 브라우저 주소나 로그인 정보는 보내지 않아도 됩니다.')
                return 1
            print('브라우저에서 직접 로그인 후 터미널로 돌아와 Enter를 누르세요.', flush=True)
            print(help_text, flush=True)
            while True:
                try:
                    command = input('시험 도구> ').strip().split()
                except (EOFError, KeyboardInterrupt):
                    break
                try:
                    action = command[0] if command else 'editor'
                    if action == 'quit':
                        break
                    if action == 'editor':
                        fields, selection = [], None
                        if page.is_closed():
                            page = context.new_page()
                        page.goto(f'https://blog.naver.com/{args.blog_id}', wait_until='domcontentloaded')
                        print('브라우저에서 본인 블로그의 글쓰기를 직접 눌러 주세요. 바로가기 인증 반복을 피하도록 변경했습니다.')
                        print('글쓰기가 새 탭이면 tabs → use 번호로 선택한 뒤 inspect를 실행하세요.')
                    elif action == 'tabs':
                        from urllib.parse import urlsplit
                        for index, tab in enumerate(context.pages):
                            location = urlsplit(tab.url)
                            print(index, '*' if tab == page else '-', location.hostname or '(빈 탭)', location.path)
                        print('쿼리/인증 값은 표시하지 않습니다. use 번호로 작업 탭을 선택하세요.')
                    elif action == 'use':
                        if len(command) != 2 or not command[1].isdigit():
                            raise ValueError('예: use 1 (tabs에서 확인한 번호)')
                        index = int(command[1])
                        if index >= len(context.pages):
                            raise ValueError('유효한 탭 번호가 아닙니다.')
                        candidate = context.pages[index]
                        from urllib.parse import urlsplit
                        if urlsplit(candidate.url).hostname != 'blog.naver.com':
                            raise ValueError('작업 탭은 blog.naver.com이어야 합니다. 로그인 창이면 인증 상태를 먼저 확인하세요.')
                        page = candidate
                        fields, selection = [], None
                        page.bring_to_front()
                        print('작업 탭을 선택했습니다. inspect로 필드를 다시 확인하세요.')
                    elif action == 'inspect':
                        from urllib.parse import urlsplit
                        if urlsplit(page.url).hostname == 'nid.naver.com':
                            print('현재 작업 탭은 로그인 화면입니다. 반복 로그인 대신 tabs로 글쓰기 탭이 따로 있는지 확인하세요.')
                            continue
                        fields, selection = [], None
                        for frame in page.frames:
                            if not frame.url.startswith('https://blog.naver.com/'):
                                continue
                            locators = frame.locator('[contenteditable="true"]')
                            for i in range(locators.count()):
                                loc = locators.nth(i)
                                if not loc.is_visible():
                                    continue
                                metadata = loc.evaluate("e => ({tag:e.tagName, role:e.getAttribute('role'), class:e.className, placeholder:e.getAttribute('data-placeholder')})")
                                fields.append(loc)
                                print(json.dumps({'index': len(fields)-1, **metadata}, ensure_ascii=False))
                        print(f'입력 가능한 필드 {len(fields)}개. 제목/본문 번호를 확인해 fill 제목번호 본문번호로 입력하세요.')
                    elif action == 'fill':
                        if journal.state(key):
                            raise ValueError('이 원고는 저장 요청 이력이 있습니다. 임시저장 목록을 먼저 확인하세요.')
                        if len(command) != 3:
                            raise ValueError('예: fill 0 1 (실제 필드 번호를 확인한 뒤 사용)')
                        a, b = map(int, command[1:])
                        if a == b or min(a,b) < 0 or max(a,b) >= len(fields):
                            raise ValueError('서로 다른 유효한 제목/본문 번호를 지정하세요.')
                        title, body = fields[a], fields[b]
                        if title.inner_text().strip() or body.inner_text().strip():
                            raise ValueError('선택한 필드에 내용이 있어 입력을 중단했습니다. 기존 원고를 보존합니다.')
                        if input('브라우저가 본인 블로그의 새 글인지 확인하고 입력하려면 INPUT: ').strip() != 'INPUT':
                            continue
                        selection = None
                        title.fill(draft['title'])
                        body.fill(draft['body'])
                        selection = (title, body)
                        print('입력했습니다. 제목·본문·블로그를 화면에서 확인한 뒤 save를 입력하세요.')
                    elif action == 'save':
                        if not selection:
                            raise ValueError('이 실행에서 fill로 입력한 원고만 저장할 수 있습니다.')
                        for loc, expected in zip(selection, (draft['title'], draft['body'])):
                            if comparable_text(loc.inner_text()) != comparable_text(expected):
                                raise ValueError('입력 결과가 원고와 다릅니다. 저장을 중단합니다.')
                        buttons = []
                        for frame in page.frames:
                            if frame.url.startswith('https://blog.naver.com/'):
                                matches = frame.get_by_role('button', name='임시저장', exact=True)
                                for i in range(matches.count()):
                                    if matches.nth(i).is_visible():
                                        buttons.append(matches.nth(i))
                        if len(buttons) != 1:
                            raise ValueError('정확히 하나의 임시저장 버튼을 확인하지 못했습니다. 직접 화면을 확인하세요.')
                        if input('공개 발행 없이 임시저장만 요청하려면 SAVE: ').strip() != 'SAVE':
                            continue
                        journal.claim(key)
                        try:
                            buttons[0].click(timeout=10000)
                        except Error:
                            journal.finish(key, 'uncertain')
                            raise ValueError('저장 결과 불확실. 다시 누르지 말고 임시저장 목록에서 확인하세요.') from None
                        journal.finish(key, 'needs_verification')
                        print('저장 버튼을 눌렀습니다. 성공 확정이 아닙니다. 직접 목록에서 다시 열어 내용 일치를 확인하세요.')
                    elif action == 'verified':
                        if journal.state(key) not in {'needs_verification', 'uncertain', 'save_requested'}:
                            raise ValueError('먼저 저장 요청을 진행하세요.')
                        if input('임시저장 목록에서 다시 열어 제목·본문 일치를 확인했다면 VERIFIED: ').strip() == 'VERIFIED':
                            journal.finish(key, 'verified_by_user')
                            print('사용자 재열기 확인으로 기록했습니다. 자동 검증 결과와 구분합니다.')
                    elif action == 'status':
                        print('상태:', journal.state(key) or '저장 요청 전')
                    else:
                        print(help_text)
                except (Error, ValueError) as exc:
                    if isinstance(exc, Error):
                        print('브라우저 작업 실패. 현재 화면을 확인하고 필요하면 inspect를 다시 실행하세요.')
                    else:
                        print(str(exc))
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    raise SystemExit(main())
