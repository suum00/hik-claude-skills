"""호스트 계정으로 알림 + 채팅방 생성 확인"""
import os
from playwright.sync_api import sync_playwright

BASE_URL = "https://homesinkorea-git-develop-homesinkorea.vercel.app"
SCREENSHOT_DIR = "/Users/sujin/hik-qa-test/screenshots/test-data"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def wait(page, ms=2000):
    page.wait_for_timeout(ms)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        # 호스트 로그인
        print("▶ 호스트 로그인...")
        page.goto(f"{BASE_URL}/login/host")
        page.wait_for_load_state("domcontentloaded")
        wait(page, 2000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/host-01-login.png")

        email_input = page.locator('input[type="email"], input[name="email"]').first
        pw_input = page.locator('input[type="password"]').first
        email_input.fill("hostuser01@gmail.com")
        pw_input.fill("Hostpass1234!")

        submit_btn = None
        for sel in ['button[type="submit"]', 'button:has-text("로그인")', 'button:has-text("Login")']:
            try:
                btn = page.locator(sel).first
                btn.wait_for(state="visible", timeout=2000)
                submit_btn = btn
                break
            except Exception:
                continue

        if submit_btn:
            submit_btn.click()
        else:
            pw_input.press("Enter")

        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=8000)
        except Exception:
            pass

        wait(page, 1500)
        print(f"  로그인 후 URL: {page.url}")
        page.screenshot(path=f"{SCREENSHOT_DIR}/host-02-after-login.png")

        if "/login" in page.url:
            print("  ⚠️  호스트 로그인 실패")
            wait(page, 5000)
            browser.close()
            return

        # 알림 확인
        print("▶ 알림 아이콘 클릭...")
        for sel in ['a[href="/notifications"]', '[class*="notification"]', '[aria-label*="notification"]']:
            try:
                notif = page.locator(sel).first
                notif.wait_for(state="visible", timeout=3000)
                notif.click()
                page.wait_for_load_state("domcontentloaded")
                wait(page, 2000)
                page.screenshot(path=f"{SCREENSHOT_DIR}/host-03-notifications.png")
                print(f"  알림 페이지 URL: {page.url}")
                break
            except Exception:
                continue

        # 채팅방 확인
        print("▶ 채팅 페이지 이동...")
        for href in ["/chats", "/chat", "/messages", "/inbox"]:
            page.goto(f"{BASE_URL}{href}")
            page.wait_for_load_state("domcontentloaded")
            wait(page, 2000)
            if page.url.endswith(href):
                page.screenshot(path=f"{SCREENSHOT_DIR}/host-04-chats.png")
                print(f"  채팅 페이지 발견: {page.url}")
                break

        print("\n✅ 확인 완료. 스크린샷:", SCREENSHOT_DIR)
        wait(page, 3000)
        browser.close()

if __name__ == "__main__":
    run()
