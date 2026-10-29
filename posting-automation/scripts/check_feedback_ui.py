"""Local browser regression for instant previews, processing, and design controls."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from naver_browser_probe import configure_korean_fonts
configure_korean_fonts();os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(root/'.local/browsers')
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel='chromium');page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(os.environ.get('POSTING_UI_TEST_URL','http://127.0.0.1:8011/'))
    expect(page.locator('.roadmap')).to_have_count(0)
    expect(page.locator('#template')).to_contain_text('브리핑')
    page.locator('#template').select_option('sample-briefing-v1')
    expect(page.frame_locator('#choice-preview').locator('body')).to_have_css('background-color','rgb(20, 37, 44)')
    page.locator('#plain-text').fill('첫 문단입니다.\n\n1. 자료 확인\n이 내용은 처리 표시 시험입니다.')
    page.evaluate("window.runningSeen=false;new MutationObserver(()=>{if(document.querySelector('#processing').classList.contains('running'))window.runningSeen=true;}).observe(document.querySelector('#processing'),{attributes:true});")
    page.locator('#prepare').click()
    expect(page.locator('#editing')).to_be_visible()
    expect(page.locator('#processing')).to_have_attribute('aria-busy','false')
    expect(page.locator('#processing-stages .done')).to_have_count(4)
    assert page.evaluate('window.runningSeen')
    page.locator('#new-template').click();page.locator('#template-name').fill('직접 조절한 디자인')
    page.locator('#template-intro').fill('색상과 여백 미리보기')
    page.locator('#design-enabled').check()
    page.locator('#design-background').evaluate("el=>{el.value='#fff4e0';el.dispatchEvent(new Event('input',{bubbles:true}));}")
    page.locator('#design-size').fill('19');page.locator('#design-gap').fill('24')
    expect(page.frame_locator('#template-preview').locator('body')).to_have_css('background-color','rgb(255, 244, 224)')
    expect(page.frame_locator('#template-preview').locator('body')).to_have_css('font-size','19px')
    page.locator('#save-template').click();expect(page.locator('#template-status')).to_contain_text('저장했습니다')
    page.locator('#apply-template').click()
    expect(page.frame_locator('#preview').locator('body')).to_have_css('background-color','rgb(255, 244, 224)')
    page.locator('#processing').screenshot(path='/tmp/posting-processing.png')
    page.locator('#template-studio').screenshot(path='/tmp/posting-design-controls.png')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    print('Feedback UI OK: instant choice, real job stages, loading state, live design controls, snapshot save, mobile')
    browser.close()
