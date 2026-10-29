"""Opt-in sample gallery browser QA, against a running local UI server."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from naver_browser_probe import configure_korean_fonts
configure_korean_fonts();os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(root/'.local/browsers')
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='chromium');page=browser.new_page(viewport={'width':1440,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(os.environ.get('POSTING_UI_TEST_URL','http://127.0.0.1:8011/'))
    expect(page.locator('.sample-card')).to_have_count(4)
    for index,style in enumerate(('editorial','notebook','manual','briefing')):
        card=page.locator('.sample-card').nth(index)
        expect(card.locator('iframe')).to_be_visible()
        card.get_by_role('button',name='크게 보기').click()
        expect(page.locator('#sample-dialog')).to_be_visible()
        expect(page.frame_locator('#sample-large').locator('h1')).to_have_text('작은 도서관에서 시작하는 독서 모임')
        colors={'editorial':'rgb(247, 242, 233)','notebook':'rgb(238, 244, 233)','manual':'rgb(241, 245, 251)','briefing':'rgb(20, 37, 44)'}
        expect(page.frame_locator('#sample-large').locator('body')).to_have_css('background-color',colors[style])
        page.locator('#sample-dialog').screenshot(path=f'/tmp/posting-style-{style}.png')
        page.locator('#close-sample').click()
        card.get_by_role('button',name='템플릿 선택').click()
        expect(page.locator('#template-style')).to_have_value(style)
    page.locator('.sample-card').last.get_by_role('button',name='샘플 원고 열기').click()
    expect(page.frame_locator('#preview').locator('body')).to_have_css('background-color','rgb(20, 37, 44)')
    page.reload()
    expect(page.frame_locator('#preview').locator('body')).to_have_css('background-color','rgb(20, 37, 44)')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    print('Sample gallery OK: 4 styles, large previews, selection, styled article persistence, mobile')
    browser.close()
