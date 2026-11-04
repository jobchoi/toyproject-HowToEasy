"""Local-only Chromium check: real editor handoff UI with network/clipboard mocked."""
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from naver_browser_probe import configure_korean_fonts
configure_korean_fonts()
root=Path(__file__).resolve().parents[1]
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(root/'.local/browsers')
from playwright.sync_api import sync_playwright,expect
import uvicorn
from posting_tool.web import create_app

with tempfile.TemporaryDirectory(prefix='posting-editor-qa-') as folder:
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(Path(folder)),host='127.0.0.1',port=port,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started:
            if time.monotonic()>deadline:raise RuntimeError('QA server startup timeout')
            time.sleep(.05)
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,channel='chromium')
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('https://**',lambda route:route.abort())
            page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.qaText=text;},write:async items=>{window.qaHTML=await (await items[0].getType('text/html')).text();}},configurable:true});")
            page.goto(f'http://127.0.0.1:{port}/')
            page.locator('#plain-text').fill('확인한 기능 테스트 원고입니다.\n\n1. 확인 사항\n<script>실행되면 안 됨</script>')
            page.locator('#title').fill('편집기 전달 기능 테스트')
            page.locator('#prepare').click()
            expect(page.locator('#editing')).to_be_visible()
            expect(page.locator('#prepare-platform')).to_be_disabled()
            page.locator('#reviewed').check();page.locator('#prepare-platform').click()
            expect(page.locator('#platform-package')).to_be_visible()
            expect(page.locator('#open-platform-editor')).to_have_attribute('href','https://rt-jobchoi.tistory.com/manage/newpost')
            expect(page.locator('#platform-target')).to_contain_text('저장·발행 전')
            page.locator('#copy-platform-rich').click()
            page.wait_for_function('window.qaHTML !== undefined')
            assert '<script>' not in page.evaluate('window.qaHTML')
            page.locator('#platform-provider').select_option('blogger-editor')
            expect(page.locator('#platform-package')).to_be_hidden()
            page.locator('#prepare-platform').click()
            expect(page.locator('#open-platform-editor')).to_have_attribute('href','https://www.blogger.com/')
            page.evaluate("()=>{navigator.clipboard.writeText=async()=>{throw new Error('denied')};}")
            page.locator('#copy-platform-html').click()
            expect(page.locator('#platform-package details')).to_have_attribute('open','')
            expect(page.locator('#platform-status')).to_contain_text('직접 복사')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('#platform-delivery').screenshot(path=str(root/'.local/editor-delivery-ui.png'))
            page.locator('#title').fill('수정한 제목')
            expect(page.locator('#platform-package')).to_be_hidden()
            expect(page.locator('#prepare-platform')).to_be_disabled()
            assert not errors,errors
            browser.close()
            print('PASS: Tistory/Blogger handoff, review gate, clipboard fallback, stale invalidation, mobile. No external login/posting.')
    finally:
        server.should_exit=True;thread.join(timeout=5)
