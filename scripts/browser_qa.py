"""Verify a dedicated demo instance and refresh public, synthetic screenshots."""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main(base_url):
    images=ROOT/'docs/images';images.mkdir(parents=True,exist_ok=True)
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    errors=[];result={}
    with sync_playwright() as p:
        executable=os.environ.get('PIT_BROWSER_EXECUTABLE')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base_url,wait_until='networkidle')
        page.wait_for_function("document.querySelector('#ground-metric').textContent.includes('21.4')")
        result['desktop_overflow']=page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(images/'workspace.png'),full_page=True)
        page.locator('[data-view="knowledge"]').click()
        page.locator('#search-query').fill('DEMO-M02 数据异常复核')
        page.locator('#search-button').click()
        page.wait_for_selector('#search-results .evidence-card')
        result['search_evidence_cards']=page.locator('#search-results .evidence-card').count()
        page.screenshot(path=str(images/'knowledge.png'),full_page=True)
        page.locator('#new-chat').click();page.locator('#engine').select_option('offline')
        page.locator('#question').fill('分析地表沉降与坑底隆起')
        page.locator('#send').click();page.wait_for_selector('.message.assistant',timeout=30000)
        result['contains_expected_statistics']='21.400' in page.locator('.message.assistant').inner_text()
        page.screenshot(path=str(images/'conversation.png'),full_page=True)
        page.get_by_role('button',name='查看依据').last.click()
        page.wait_for_selector('#evidence-dialog[open]')
        result['evidence_dialog_cards']=page.locator('#evidence-list .evidence-card').count()
        page.locator('#evidence-dialog .close-dialog').click()
        page.locator('[data-view="reports"]').click();page.wait_for_selector('.report-card')
        with page.expect_download() as event:
            page.locator('.report-card a').filter(has_text='PDF').first.click()
        event.value.save_as(str(artifacts/'download.pdf'))
        result['download_pdf_bytes']=(artifacts/'download.pdf').stat().st_size
        page.screenshot(path=str(images/'reports.png'),full_page=True)
        page.locator('#new-chat').click();page.set_viewport_size({'width':390,'height':844})
        result['mobile_overflow']=page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(images/'mobile.png'),full_page=True)
        browser.close()
    result['browser_errors']=errors
    (artifacts/'browser_qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/browser-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    assert not errors and not result['desktop_overflow'] and not result['mobile_overflow'],result
    assert result['contains_expected_statistics'] and result['download_pdf_bytes']>1000,result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8765')
    main(parser.parse_args().base_url.rstrip('/'))
