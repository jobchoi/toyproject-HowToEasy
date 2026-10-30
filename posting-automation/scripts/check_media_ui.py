"""Local-only photo editing, persistence, and portable export regression."""
import base64
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from naver_browser_probe import configure_korean_fonts
configure_korean_fonts()
root = Path(__file__).resolve().parents[1]
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(root / '.local/browsers')
from playwright.sync_api import sync_playwright, expect
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL1sAAAAASUVORK5CYII=')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chromium')
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ.get('POSTING_UI_TEST_URL','http://127.0.0.1:8012/'))
    page.locator('#plain-text').fill('사진과 함께 기록하는 블로그 글입니다.')
    page.locator('#prepare').click(); expect(page.locator('#editing')).to_be_visible()
    page.locator('#image-file').set_input_files({'name':'sample.png','mimeType':'image/png','buffer':PNG})
    expect(page.locator('.document-block.image')).to_have_count(1)
    photo = page.locator('.document-block.image')
    photo.locator('input').nth(0).fill('테스트 사진')
    photo.locator('input').nth(1).fill('사진 캡션입니다.')
    photo.locator('input').nth(2).fill('https://example.com/photo')
    assert photo.locator('img').evaluate('el=>el.complete && el.naturalWidth>0')
    page.locator('#apply').click()
    expect(page.frame_locator('#preview').locator('figcaption')).to_contain_text('사진 캡션입니다.')
    assert page.frame_locator('#preview').locator('img').evaluate('el=>el.complete && el.naturalWidth>0')
    page.locator('#toggle-editor').click();expect(page.locator('#markdown')).to_contain_text('')
    assert '사진 출처: https://example.com/photo' in page.locator('#markdown').input_value()
    page.locator('#toggle-editor').click(); expect(page.locator('.document-block.image')).to_have_count(1)
    page.reload();expect(page.locator('.document-block.image')).to_have_count(1)
    expect(page.locator('.document-block.image input').nth(1)).to_have_value('사진 캡션입니다.')
    page.locator('#reviewed').check()
    with page.expect_download() as event: page.locator('#download-zip').click()
    assert event.value.suggested_filename == 'posting-bundle.zip'
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    browser.close()
    print('Media UI OK: upload, caption/source, image decoding, save, Markdown roundtrip, reload, ZIP, mobile')
