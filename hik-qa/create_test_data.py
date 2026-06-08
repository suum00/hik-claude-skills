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

        # ── 1. 게스트 로그인 ──
        print("▶ 게스트 로그인...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("domcontentloaded")
        wait(page, 2000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/01-login.png")

        # 로그인 폼 입력
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail"]').first
        pw_input = page.locator('input[type="password"]').first
        email_input.fill("guesttest01@gmail.com")
        pw_input.fill("Guestpass1234!")

        # 제출 버튼 — type=submit 또는 텍스트로 탐색
        submit_btn = None
        for sel in ['button[type="submit"]', 'button:has-text("로그인")', 'button:has-text("Login")', 'button:has-text("Sign in")']:
            try:
                btn = page.locator(sel).first
                btn.wait_for(state="visible", timeout=2000)
                submit_btn = btn
                print(f"  로그인 버튼 발견: {sel}")
                break
            except Exception:
                continue

        if submit_btn:
            submit_btn.click()
        else:
            print("  ⚠️  로그인 버튼 못 찾음 → Enter 키 시도")
            pw_input.press("Enter")

        # URL이 /login에서 벗어날 때까지 대기 (최대 8초)
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=8000)
        except Exception:
            pass

        wait(page, 1500)
        print(f"  로그인 후 URL: {page.url}")
        page.screenshot(path=f"{SCREENSHOT_DIR}/02-after-login.png")

        if "/login" in page.url:
            # 에러 메시지 확인
            try:
                err = page.locator('[class*="error"], [class*="alert"], [role="alert"]').first.inner_text()
                print(f"  ⚠️  로그인 에러: {err}")
            except Exception:
                print("  ⚠️  로그인 실패 (에러 메시지 없음) — 버튼 목록:")
                for b in page.locator("button").all()[:8]:
                    try:
                        print(f"    - '{b.inner_text().strip()}'")
                    except Exception:
                        pass
            wait(page, 60000)  # 수동 확인용 60초 대기
            browser.close()
            return

        # ── 2. 홈 이동 후 숙소 링크 탐색 ──
        print("▶ 홈 이동...")
        page.goto(BASE_URL)
        page.wait_for_load_state("domcontentloaded")
        wait(page, 2500)
        page.screenshot(path=f"{SCREENSHOT_DIR}/03-home.png")

        print("▶ 숙소 링크 탐색...")
        listing_href = None
        for link in page.locator("a[href]").all():
            try:
                href = link.get_attribute("href") or ""
                if any(kw in href for kw in ["/properties/", "/listing", "/property", "/room", "/stay", "/house", "/accommodation"]):
                    listing_href = href
                    print(f"  숙소 링크 발견: {href}")
                    break
            except Exception:
                continue

        if listing_href:
            full_url = listing_href if listing_href.startswith("http") else f"{BASE_URL}{listing_href}"
            print(f"  이동: {full_url}")
            page.goto(full_url)
            page.wait_for_load_state("domcontentloaded")
            wait(page, 2000)
        else:
            print("  직접 URL 패턴 없음 — 페이지 내 모든 링크 목록 (상위 15개):")
            for link in page.locator("a[href]").all()[:15]:
                try:
                    href = link.get_attribute("href") or ""
                    txt = link.inner_text().strip()[:30]
                    print(f"    {href}  ({txt})")
                except Exception:
                    pass
            # 카드 클릭 시도
            cards = page.locator('[class*="card"], [class*="item"], [class*="listing"]').all()
            print(f"  카드 {len(cards)}개 중 첫 번째 클릭")
            if cards:
                cards[0].click()
                page.wait_for_load_state("domcontentloaded")
                wait(page, 2000)

        print(f"  현재 URL: {page.url}")
        page.screenshot(path=f"{SCREENSHOT_DIR}/04-listing.png")

        # ── 3. 문의하기 버튼 클릭 ──
        print("▶ 문의하기 버튼 탐색...")
        found = False
        for text in ["문의하기", "이용 문의", "문의", "호스트에게 문의", "채팅하기", "채팅", "Contact host", "Contact", "Inquiry", "Chat"]:
            try:
                btn = page.get_by_text(text, exact=False).first
                btn.wait_for(state="visible", timeout=2000)
                print(f"  '{text}' 버튼 발견 → 클릭")
                page.screenshot(path=f"{SCREENSHOT_DIR}/05-before-inquiry.png")
                btn.click()
                page.wait_for_load_state("domcontentloaded")
                wait(page, 2000)
                page.screenshot(path=f"{SCREENSHOT_DIR}/06-after-inquiry.png")
                print(f"  클릭 후 URL: {page.url}")
                found = True
                break
            except Exception:
                continue

        if not found:
            print("  ⚠️  문의하기 버튼 없음 — 현재 페이지 버튼 목록:")
            for b in page.locator("button, a[role='button']").all()[:15]:
                try:
                    print(f"    버튼: '{b.inner_text().strip()}'")
                except Exception:
                    pass
            wait(page, 5000)
            browser.close()
            return

        # ── 4. 문의 폼 작성 및 전송 ──
        print("▶ 문의 메시지 입력...")
        # textarea에 메시지 입력
        for sel in ['textarea', '[placeholder*="message"]', '[placeholder*="Message"]']:
            try:
                ta = page.locator(sel).first
                ta.wait_for(state="visible", timeout=3000)
                ta.fill("안녕하세요! 테스트 문의입니다. QA 테스트 데이터 생성을 위한 메시지입니다.")
                print(f"  메시지 입력 완료 ({sel})")
                break
            except Exception:
                continue

        page.screenshot(path=f"{SCREENSHOT_DIR}/07-inquiry-filled.png")

        # Send Message 버튼 클릭
        print("▶ Send Message 버튼 클릭...")
        for text in ["Send Message", "Send", "전송", "보내기"]:
            try:
                btn = page.get_by_text(text, exact=False).last
                btn.wait_for(state="visible", timeout=2000)
                btn.click()
                page.wait_for_load_state("domcontentloaded")
                wait(page, 2500)
                page.screenshot(path=f"{SCREENSHOT_DIR}/08-after-send.png")
                print(f"  전송 후 URL: {page.url}")
                break
            except Exception:
                continue

        print("\n✅ 스크린샷 저장 완료:", SCREENSHOT_DIR)
        wait(page, 3000)
        browser.close()

if __name__ == "__main__":
    run()
