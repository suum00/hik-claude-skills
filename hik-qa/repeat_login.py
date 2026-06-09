import sys
sys.path.insert(0, '/Users/sujin/hik-qa-test')
from qa_runner import repeat_flow_test, BASE_URL
from playwright.sync_api import sync_playwright

def login_flow(page):
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)

    page.locator('input[type="email"]').fill("guesttest01@gmail.com")
    page.locator('input[type="password"]').fill("Guestpass1234!")
    page.click('button[type="submit"]')

    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=8000)
    except Exception:
        raise Exception(f"로그인 후 URL이 /login에 머묾: {page.url}")

    page.wait_for_timeout(500)
    # 로그아웃 후 다음 회차 준비
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("domcontentloaded")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    repeat_flow_test(page, "로그인", login_flow, repeat=10)
    browser.close()
