"""Optional browser smoke: requires Playwright and its Chromium browser."""
from pathlib import Path
import sys
import shutil
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assistant import Assistant
from phone import PhoneServer
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as data:
        assistant = Assistant(Path(data), Path(data) / 'data')
        server = PhoneServer(('127.0.0.1', 0), assistant, token='browser-smoke-code')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=shutil.which('chromium'))
                try:
                    page = browser.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.locator('#code').fill('wrong-code')
                    page.locator('#pair-form button').click()
                    page.locator('#status.error').wait_for()
                    page.locator('#code').fill('browser-smoke-code')
                    page.locator('#pair-form button').click()
                    page.locator('#connected').wait_for(state='visible')
                    page.locator('[data-tab=tasks]').click()
                    page.locator('#task-text').fill('Plan my week')
                    page.locator('#task-form button').click()
                    page.locator('#review').wait_for(state='visible')
                    assert assistant.listing('task') == 'No active tasks.'
                    page.locator('#cancel').click()
                    page.locator('#review').wait_for(state='hidden')
                    page.locator('#task-form button').wait_for(state='visible')
                    page.wait_for_function("!document.querySelector('#task-form button').disabled")
                    page.locator('#task-form button').click()
                    page.locator('#confirm').click()
                    page.get_by_text('Plan my week', exact=True).first.wait_for()
                    page.locator('[data-tab=notes]').click()
                    page.locator('#note-text').fill('<img src=x onerror=alert(1)> A personal note')
                    page.locator('#note-form button').click()
                    page.locator('#confirm').click()
                    page.locator('#notes-list .item-text').wait_for()
                    assert page.locator('#notes-list img').count() == 0
                    page.locator('[data-tab=calendar]').click()
                    page.locator('#event-text').fill('Lunch with Alex')
                    page.locator('#event-date').fill('2030-01-02T13:30')
                    page.locator('#event-form button').click()
                    page.locator('#confirm').click()
                    page.locator('#events-list .item-text').wait_for()
                    page.locator('[data-tab=today]').click()
                    page.locator('#memory-key').fill('My name')
                    page.locator('#memory-value').fill('Sam')
                    page.locator('#memory-form button').click()
                    page.locator('#confirm').click()
                    page.locator('#memory-list .item-text').wait_for()
                    assert 'Sam' in assistant.prepare('memory').run()
                    page.locator('#reminder-text').fill('Take a break')
                    page.locator('#reminder-form button').click()
                    page.locator('#confirm').click()
                    page.locator('#reminders-list .item-text').wait_for()
                    page.locator('[data-tab=chat]').click()
                    page.locator('#mode').select_option('command')
                    page.locator('#message').fill('run echo blocked')
                    page.locator('#message-form button').click()
                    page.locator('#status.error').wait_for()
                    assert 'disabled' in page.locator('#status').inner_text()
                    for width in [320, 390, 768]:
                        page.set_viewport_size({'width': width, 'height': 844})
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overflow at {width}px'
                    page.locator('[data-tab=today]').click()
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.screenshot(path='/tmp/havie-phone.png', full_page=True)
                    assert not errors, errors
                    page.locator('#disconnect').click()
                    page.locator('#pair').wait_for(state='visible')
                    assert page.evaluate("sessionStorage.getItem('havie-token')") is None
                    print('Mobile browser smoke passed: pairing, cancel/confirm, tasks, notes, calendar, preferences, reminders, PC controls blocked, responsive widths and disconnect.')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    main()
