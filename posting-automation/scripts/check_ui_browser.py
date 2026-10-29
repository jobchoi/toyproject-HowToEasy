"""Opt-in browser smoke check; run against the local UI server on port 8010."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from naver_browser_probe import configure_korean_fonts
configure_korean_fonts()
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(root/'.local/browsers')
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,channel='chromium')
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[]
 page.on('pageerror',lambda e: errors.append(str(e)))
 page.goto(os.environ.get('POSTING_UI_TEST_URL','http://127.0.0.1:8010/'))
 expect(page.locator('#example')).to_be_enabled()
 expect(page.locator('.roadmap')).to_have_count(0)
 expect(page.locator('#phase-label')).to_contain_text('1단계')
 page.screenshot(path='/tmp/posting-ui-empty.png',full_page=True)
 page.get_by_role('button',name='예제로 둘러보기').click()
 expect(page.locator('#editing')).to_be_visible()
 expect(page.locator('#phase-label')).to_contain_text('3단계 · 내용과 출처 검토')
 expect(page.locator('#markdown')).to_have_value(__import__('re').compile('포스팅 도구'))
 expect(page.locator('#download-zip')).to_have_attribute('aria-disabled','true')
 page.locator('#toggle-editor').click()
 page.locator('#markdown').fill('# 수정한 원고\n\n확인용 본문입니다.')
 page.locator('#title').fill('UI 시험 원고')
 expect(page.locator('#phase-label')).to_contain_text('2단계')
 page.get_by_role('button',name='편집 내용 저장 · 미리보기').click()
 expect(page.locator('#save-state')).to_contain_text('이 PC에 저장됨')
 expect(page.frame_locator('#preview').locator('h1')).to_have_text('수정한 원고')
 page.locator('#reviewed').check()
 expect(page.locator('#download-zip')).to_have_attribute('aria-disabled','false')
 expect(page.locator('#phase-label')).to_contain_text('내보내기 준비됨')
 with page.expect_download() as download:
  page.locator('#download-zip').click()
 assert download.value.suggested_filename=='posting-bundle.zip'
 expect(page.locator('#phase-label')).to_contain_text('파일 받기 요청')
 page.screenshot(path='/tmp/posting-ui-editor.png',full_page=True)
 page.reload()
 expect(page.locator('#title')).to_have_value('UI 시험 원고')
 expect(page.locator('#reviewed')).not_to_be_checked()
 page.locator('#files').set_input_files({'name':'local.md','mimeType':'text/markdown','buffer':'# 업로드 원고\n\n본문'.encode()})
 expect(page.locator('#file-list')).to_contain_text('local.md')
 page.locator('#prepare').click()
 expect(page.locator('#markdown')).to_have_value(__import__('re').compile('업로드 원고'))
 expect(page.frame_locator('#preview').locator('h1')).to_have_text('UI 시험 원고')
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path='/tmp/posting-ui-mobile.png',full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'mobile overflow'
 assert not errors, errors
 print('Browser UI OK: example, edit, preview, review, ZIP, reload, upload, mobile')
 browser.close()
