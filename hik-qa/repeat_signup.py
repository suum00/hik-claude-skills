import sys, time
sys.path.insert(0, '/Users/sujin/hik-qa-test')
from qa_runner import repeat_flow_test, BASE_URL
from playwright.sync_api import sync_playwright

def guest_signup_flow(page):
    page.goto(f"{BASE_URL}/signup")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)

    # 이메일 입력 (local part)
    email_input = page.locator('input[placeholder="e-mail"]').first
    email_input.wait_for(state="visible", timeout=5000)
    email_input.fill(f"qatest{int(time.time())}")

    # 도메인 선택 버튼 클릭 후 gmail.com 선택
    page.locator('button:has-text("select")').first.click()
    page.wait_for_timeout(800)
    try:
        page.get_by_text("gmail.com", exact=False).first.click()
        page.wait_for_timeout(500)
    except Exception:
        page.keyboard.press("Escape")

    # 인증번호 전송 버튼 클릭
    send_btn = page.get_by_text("Send verification code", exact=False).first
    send_btn.wait_for(state="visible", timeout=5000)
    send_btn.click()
    page.wait_for_timeout(1500)

    # 페이지가 /signup에 머물거나 다음 단계로 이동했는지 확인 (404 아니면 성공)
    if "404" in page.title() or "not found" in page.url.lower():
        raise Exception(f"404 발생: {page.url}")


def host_signup_flow(page):
    page.goto(f"{BASE_URL}/signup/host")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)

    # 이메일 입력
    email_input = page.locator('input[placeholder="이메일"]').first
    email_input.wait_for(state="visible", timeout=5000)
    email_input.fill(f"qahost{int(time.time())}")

    # 도메인 선택
    domain_btn = page.locator('button').filter(has_text="입력해주세요").first
    try:
        domain_btn.click()
        page.wait_for_timeout(800)
        page.get_by_text("gmail.com", exact=False).first.click()
        page.wait_for_timeout(500)
    except Exception:
        page.keyboard.press("Escape")

    # 인증번호 전송 버튼
    send_btn = page.get_by_text("인증번호 전송", exact=False).first
    send_btn.wait_for(state="visible", timeout=5000)
    send_btn.click()
    page.wait_for_timeout(1500)

    if "404" in page.title() or "not found" in page.url.lower():
        raise Exception(f"404 발생: {page.url}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    print("\n===== 게스트 회원가입 반복테스트 =====")
    page = browser.new_page(viewport={"width": 390, "height": 844})
    repeat_flow_test(page, "회원가입(게스트)", guest_signup_flow, repeat=10)
    page.close()

    print("\n===== 호스트 회원가입 반복테스트 =====")
    page = browser.new_page(viewport={"width": 390, "height": 844})
    repeat_flow_test(page, "회원가입(호스트)", host_signup_flow, repeat=10)
    page.close()

    browser.close()
