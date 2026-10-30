"""Local browser QA for navigation, viewport state, and history."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from naver_browser_probe import configure_korean_fonts
configure_korean_fonts()
root = Path(__file__).resolve().parents[1]
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(root / '.local/browsers')
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chromium')
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('POSTING_UI_TEST_URL','http://127.0.0.1:8012/'))
    nav = page.locator('.workspace-nav')
    links = nav.locator('a')
    ids = ['writing-room','library','template-gallery','template-studio']
    def active(key):
        expect(nav.locator('[aria-current="location"]')).to_have_count(1)
        expect(nav.locator('[aria-current="location"]')).to_have_attribute('href','#'+key)
        expect(page.locator('#current-location')).to_have_text(nav.locator(f'[href="#{key}"]').get_attribute('data-label'))
    expect(page.locator('#sample-gallery .sample-card').first).to_be_visible()
    assert links.evaluate_all('els=>els.map(el=>el.hash.slice(1))') == ids
    positions = [page.locator('#'+key).evaluate('el=>el.getBoundingClientRect().top') for key in ids]
    assert positions == sorted(positions)
    for key in ids:
        nav.locator(f'[href="#{key}"]').click()
        active(key)
        assert page.locator('#'+key).evaluate('el=>Math.abs(el.getBoundingClientRect().top-parseFloat(getComputedStyle(el).scrollMarginTop))<3')
    page.go_back(); active('template-gallery')
    page.go_forward(); active('template-studio')
    page.locator('#library').evaluate('el=>el.scrollIntoView()');active('library')
    page.locator('#workspace').evaluate('el=>el.scrollIntoView()');active('writing-room')
    nav.locator('[href="#writing-room"]').focus()
    page.keyboard.press('Tab');page.keyboard.press('Enter');active('library')
    page.reload();active('library')
    for width in (390,760):
        page.set_viewport_size({'width':width,'height':844})
        for key in reversed(ids):
            nav.locator(f'[href="#{key}"]').click();active(key)
            assert page.locator('#'+key).evaluate('el=>el.getBoundingClientRect().top>=document.querySelector(".sidebar").getBoundingClientRect().bottom-1')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors, errors
    print('Navigation UI OK: order, click, scroll, editor grouping, keyboard, history, reload, mobile')
    browser.close()
