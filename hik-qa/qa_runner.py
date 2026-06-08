import os
import requests
import gspread
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright

BASE_URL = "https://homesinkorea-git-develop-homesinkorea.vercel.app"
KEY_FILE = "/Users/sujin/Downloads/swift-implement-498523-i1-4c673fb266fe.json"
QA_SHEET_ID = "1-n6YwMjppwANQRiT3qIytOzRt-pUvoIushUzgT4sef8"
SCREENSHOT_DIR = "/Users/sujin/hik-qa-test/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)
sh = gc.open_by_key(QA_SHEET_ID)
ws = sh.worksheet("QA Issues")
ws_repeat = sh.worksheet("반복테스트")
sheets_service = build("sheets", "v4", credentials=creds)


def upload_screenshot(path):
    """catbox.moe에 이미지 업로드 후 URL 반환"""
    try:
        with open(path, "rb") as f:
            resp = requests.post("https://catbox.moe/user/api.php",
                                 data={"reqtype": "fileupload"},
                                 files={"fileToUpload": f}, timeout=15)
        return resp.text.strip() if resp.status_code == 200 else ""
    except Exception:
        return ""


def log_issue(state, screen, issue_type, description, severity, screenshot_path=None, highlight_yellow=False):
    rows = ws.get_all_values()
    # 중복 체크 — 상태/화면명/이슈유형/설명이 모두 같으면 추가하지 않음
    for row in rows[1:]:
        if len(row) >= 5 and row[1] == state and row[2] == screen and row[3] == issue_type and row[4] == description:
            print(f"  ⏭️  중복 이슈 건너뜀: [{screen}] {description}")
            return
    num = len(rows)
    row_idx = num + 1  # 1-based

    img_url = upload_screenshot(screenshot_path) if screenshot_path else ""
    ws.append_row([num, state, screen, issue_type, description, severity,
                   datetime.now().strftime("%Y-%m-%d %H:%M"), ""])

    sheet_id = ws.id
    requests_body = []

    # 스크린샷 삽입
    if img_url:
        requests_body += [
            {"updateCells": {
                "range": {"sheetId": sheet_id,
                          "startRowIndex": row_idx - 1, "endRowIndex": row_idx,
                          "startColumnIndex": 7, "endColumnIndex": 8},
                "rows": [{"values": [{"userEnteredValue": {"formulaValue": f'=IMAGE("{img_url}")'}}]}],
                "fields": "userEnteredValue"
            }},
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                          "startIndex": row_idx - 1, "endIndex": row_idx},
                "properties": {"pixelSize": 200},
                "fields": "pixelSize"
            }}
        ]

    # 노란색 배경 (수동 확인 필요)
    if highlight_yellow:
        requests_body.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id,
                          "startRowIndex": row_idx - 1, "endRowIndex": row_idx},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.976, "blue": 0.769}
                }},
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    if requests_body:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=QA_SHEET_ID,
            body={"requests": requests_body}
        ).execute()

    icon = "🟡" if highlight_yellow else "❌"
    print(f"  {icon} [{severity}] [{issue_type}] {screen}: {description}")


def log_manual_check(state, screen, issue_type, description):
    log_issue(state, screen, issue_type, description,
              severity="확인필요", highlight_yellow=True)


def log_repeat_test(flow_name, total, failures):
    """반복테스트 결과를 '반복테스트' 시트에 기록.
    failures: list of (회차, 에러메시지, screenshot_path)
    """
    success_count = total - len(failures)
    success_rate = f"{success_count / total * 100:.0f}%"
    fail_rounds = ", ".join(str(f[0]) for f in failures) if failures else "-"
    last_error = failures[-1][1][:100] if failures else "-"
    screenshot_url = ""
    if failures:
        screenshot_url = upload_screenshot(failures[0][2]) if failures[0][2] else ""

    rows = ws_repeat.get_all_values()
    # 중복 체크 — 같은 플로우·총횟수·실패횟수 조합이 오늘 날짜로 이미 있으면 덮어쓰지 않음
    today = datetime.now().strftime("%Y-%m-%d")
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 8 and row[1] == flow_name and row[7].startswith(today):
            # 기존 행 업데이트
            ws_repeat.update(f"A{i}:I{i}", [[
                row[0], flow_name, total, len(failures), success_rate,
                fail_rounds, last_error, datetime.now().strftime("%Y-%m-%d %H:%M"), ""
            ]])
            _insert_repeat_screenshot(i, screenshot_url)
            _highlight_repeat_row(i, bool(failures))
            icon = "❌" if failures else "✅"
            print(f"  {icon} [반복테스트] {flow_name}: {total}회 중 {len(failures)}회 실패 ({success_rate})")
            return

    num = len(rows)
    row_idx = num + 1
    ws_repeat.append_row([
        num, flow_name, total, len(failures), success_rate,
        fail_rounds, last_error, datetime.now().strftime("%Y-%m-%d %H:%M"), ""
    ])
    _insert_repeat_screenshot(row_idx, screenshot_url)
    _highlight_repeat_row(row_idx, bool(failures))

    icon = "❌" if failures else "✅"
    print(f"  {icon} [반복테스트] {flow_name}: {total}회 중 {len(failures)}회 실패 ({success_rate})")


def _insert_repeat_screenshot(row_idx, img_url):
    if not img_url:
        return
    sheet_id = ws_repeat.id
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=QA_SHEET_ID,
        body={"requests": [
            {"updateCells": {
                "range": {"sheetId": sheet_id,
                          "startRowIndex": row_idx - 1, "endRowIndex": row_idx,
                          "startColumnIndex": 8, "endColumnIndex": 9},
                "rows": [{"values": [{"userEnteredValue": {"formulaValue": f'=IMAGE("{img_url}")'}}]}],
                "fields": "userEnteredValue"
            }},
            {"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                          "startIndex": row_idx - 1, "endIndex": row_idx},
                "properties": {"pixelSize": 120},
                "fields": "pixelSize"
            }}
        ]}
    ).execute()


def _highlight_repeat_row(row_idx, has_failure):
    color = (
        {"red": 1.0, "green": 0.85, "blue": 0.85}   # 연한 빨강 — 실패
        if has_failure else
        {"red": 0.85, "green": 0.94, "blue": 0.85}  # 연한 초록 — 성공
    )
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=QA_SHEET_ID,
        body={"requests": [{
            "repeatCell": {
                "range": {"sheetId": ws_repeat.id,
                          "startRowIndex": row_idx - 1, "endRowIndex": row_idx},
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor"
            }
        }]}
    ).execute()


def repeat_flow_test(page, flow_name, test_fn, repeat=10):
    """flow_name 플로우를 repeat회 반복 실행, 결과를 반복테스트 시트에 기록."""
    print(f"\n  ▶ {flow_name} 반복테스트 {repeat}회 시작...")
    failures = []
    for i in range(1, repeat + 1):
        try:
            test_fn(page)
            print(f"    {i}회: ✅")
        except Exception as e:
            screenshot_path = f"{SCREENSHOT_DIR}/repeat_{flow_name}_{i}.png"
            try:
                page.screenshot(path=screenshot_path)
            except Exception:
                screenshot_path = None
            failures.append((i, str(e), screenshot_path))
            print(f"    {i}회: ❌ {str(e)[:60]}")
    log_repeat_test(flow_name, repeat, failures)


def ok(msg):
    print(f"  ✅ {msg}")

def info(msg):
    print(f"  ℹ️  {msg}")


def login_guest(page):
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', "guesttest01@gmail.com")
    page.fill('input[type="password"]', "Guestpass1234!")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def check_element_visible(page, locator, label):
    """요소 존재 여부 확인. 있으면 True, 없으면 False."""
    try:
        el = page.locator(locator).first
        el.wait_for(state="visible", timeout=3000)
        return True
    except Exception:
        return False


def qa_g_home(page, state="게스트"):
    print("\n━━━ [G-HOME] 홈 화면 QA ━━━")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.screenshot(path=f"{SCREENSHOT_DIR}/g-home.png", full_page=True)

    # ── 규칙 1: UI — 주요 요소 확인 ──
    print("\n  [규칙 1] UI 확인")

    # 검색 바
    if check_element_visible(page, 'input[placeholder*="earch"], [class*="search"] input', "search"):
        ok("검색 바 존재")
    else:
        # 텍스트로 찾기
        el = page.get_by_text("Search locations").first
        try:
            el.wait_for(state="visible", timeout=3000)
            ok("검색 바 존재 (텍스트로 확인)")
        except Exception:
            log_issue(state, "G-HOME", "UI", "검색 바(Search locations) 미노출", "중간")

    # 숙소 유형 4개
    for t in ["Co-living", "Studio", "Micro Studio", "Multi-bedroom"]:
        el = page.get_by_text(t, exact=True).first
        try:
            el.wait_for(state="visible", timeout=3000)
            ok(f"숙소 유형 버튼 존재: {t}")
        except Exception:
            log_issue(state, "G-HOME", "UI", f"숙소 유형 버튼 미노출: {t}", "중간")

    # 하단 내비게이션
    for nav in ["Home", "Map", "Booking", "Chat", "My"]:
        if check_element_visible(page, f'nav >> text={nav}', nav):
            ok(f"하단 nav 존재: {nav}")
        else:
            log_issue(state, "G-HOME", "UI", f"하단 nav 미노출: {nav}", "높음")

    # 알림 아이콘 (헤더 우측)
    bell_found = False
    bell_selectors = [
        'header a[href*="noti"], header button[aria-label*="noti"]',
        'header >> [href*="noti"]',
        'a[href*="/notification"], a[href*="/noti"]',
    ]
    for sel in bell_selectors:
        if check_element_visible(page, sel, "bell"):
            bell_found = True
            ok("알림 아이콘 존재")
            break

    if not bell_found:
        # href 기반으로 직접 찾기
        links = page.locator('a').all()
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                if "noti" in href.lower():
                    bell_found = True
                    ok(f"알림 아이콘 존재 (href: {href})")
                    break
            except Exception:
                continue

    if not bell_found:
        log_issue(state, "G-HOME", "UI", "알림(벨) 아이콘을 찾을 수 없음 — 셀렉터 확인 필요", "중간")

    # ── 규칙 2: 플로우 — 알림 아이콘 클릭 ──
    print("\n  [규칙 2] 플로우 확인 (알림 아이콘 → 알림 페이지)")
    noti_link = page.locator('a[href*="noti"]').first
    try:
        noti_link.wait_for(state="visible", timeout=3000)
        noti_link.click()
        page.wait_for_load_state("networkidle")
        url = page.url
        if "noti" in url.lower() or "notification" in url.lower():
            ok(f"알림 아이콘 클릭 → 알림 페이지 이동 정상 ({url})")
        else:
            log_issue(state, "G-HOME", "플로우", f"알림 아이콘 클릭 후 알림 페이지로 이동 안 됨 (현재: {url})", "높음")
        page.go_back()
        page.wait_for_load_state("networkidle")
    except Exception:
        log_issue(state, "G-HOME", "플로우", "알림 아이콘 링크를 찾을 수 없어 플로우 검증 불가", "높음")

    # ── 규칙 3: 뒤로가기 ──
    print("\n  [규칙 3] 뒤로가기 확인")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE_URL}/map")
    page.wait_for_load_state("networkidle")
    page.go_back()
    page.wait_for_load_state("networkidle")
    if page.url.rstrip("/") == BASE_URL.rstrip("/"):
        ok("뒤로가기 → 홈 복귀 정상")
    else:
        log_issue(state, "G-HOME", "뒤로가기", f"뒤로가기 후 홈이 아닌 페이지: {page.url}", "중간")

    # ── 규칙 4: 팝업/바텀시트 ──
    info("G-HOME Figma 기준 팝업/바텀시트 트리거 없음 → 건너뜀")


def qa_g_my_login(page, state="게스트"):
    print("\n━━━ [G-MY.login] 마이페이지 QA ━━━")
    page.goto(f"{BASE_URL}/my")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=f"{SCREENSHOT_DIR}/g-my-login.png", full_page=True)

    # ── 규칙 1: UI — 메뉴 항목 확인 ──
    print("\n  [규칙 1] UI 확인")

    # 프로필 영역
    try:
        page.get_by_text("guesttest01@gmail.com").first.wait_for(state="visible", timeout=3000)
        ok("프로필 영역 (이메일) 노출")
    except Exception:
        log_issue(state, "G-MY.login", "UI", "프로필 이메일 미노출", "중간")

    # 메뉴 항목 (Figma 기준 5개)
    menus = {
        "My Booking": "My Booking",
        "Payment": "Payment",
        "Wish": "Wish",
        "Blog": "Blog",
        "Contact HOMES IN KOREA": "Contact",
    }
    for label, search_text in menus.items():
        el = page.get_by_text(search_text).first
        try:
            el.wait_for(state="visible", timeout=3000)
            ok(f"메뉴 존재: {label}")
        except Exception:
            log_issue(state, "G-MY.login", "UI", f"메뉴 항목 미노출: {label} — Figma 디자인에는 있음", "높음")

    # 호스트 전환 버튼 (한국어/영어 모두 확인)
    host_btn = None
    for text in ["호스트 모드 시작하기", "Switching to Host Mode", "Switch to Host"]:
        el = page.get_by_text(text).first
        try:
            el.wait_for(state="visible", timeout=2000)
            host_btn = el
            ok(f"호스트 전환 버튼 존재: '{text}'")
            break
        except Exception:
            continue
    if not host_btn:
        log_issue(state, "G-MY.login", "UI", "호스트 전환 버튼 미노출", "높음")

    # 로그아웃 버튼
    logout_btn = None
    for text in ["Logout", "Log out", "로그아웃"]:
        el = page.get_by_text(text).first
        try:
            el.wait_for(state="visible", timeout=2000)
            logout_btn = el
            ok(f"로그아웃 버튼 존재: '{text}'")
            break
        except Exception:
            continue
    if not logout_btn:
        log_issue(state, "G-MY.login", "UI", "로그아웃 버튼 미노출", "중간")

    # ── 규칙 2: 플로우 문서 항목 없음 ──
    info("G-MY.login 플로우 문서 항목 없음 → 건너뜀")

    # ── 규칙 3: 뒤로가기 ──
    print("\n  [규칙 3] 뒤로가기 확인")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.go_back()
    page.wait_for_load_state("networkidle")
    if "my" in page.url:
        ok("뒤로가기 → My 페이지 복귀 정상")
    else:
        log_issue(state, "G-MY.login", "뒤로가기", f"뒤로가기 후 예상 외 페이지: {page.url}", "중간")

    # ── 규칙 4: 팝업/다이얼로그 ──
    print("\n  [규칙 4] 팝업/다이얼로그 확인")
    page.goto(f"{BASE_URL}/my")
    page.wait_for_load_state("networkidle")

    def find_dialog(page):
        selectors = ['[role="dialog"]', '[class*="modal"]', '[class*="dialog"]',
                     '[class*="popup"]', '[class*="overlay"]', '[class*="sheet"]']
        for sel in selectors:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=2000)
                return el
            except Exception:
                continue
        return None

    def find_close_btn(page):
        for text in ["Cancel", "취소", "No", "닫기", "Close"]:
            try:
                el = page.get_by_text(text).first
                el.wait_for(state="visible", timeout=1000)
                return el
            except Exception:
                continue
        # X 버튼
        try:
            el = page.locator('[aria-label="close"], button[class*="close"]').first
            el.wait_for(state="visible", timeout=1000)
            return el
        except Exception:
            return None

    # 호스트 전환 다이얼로그
    for text in ["호스트 모드 시작하기", "Switching to Host Mode"]:
        el = page.get_by_text(text).first
        try:
            el.wait_for(state="visible", timeout=2000)
            el.click()
            page.wait_for_timeout(1000)
            dlg = find_dialog(page)
            if dlg:
                page.screenshot(path=f"{SCREENSHOT_DIR}/g-my-host-dialog.png")
                ok(f"'{text}' 클릭 → 다이얼로그 노출")
                close = find_close_btn(page)
                if close:
                    close.click()
                    page.wait_for_timeout(500)
                    ok("다이얼로그 닫힘 정상")
                else:
                    log_issue(state, "G-MY.login", "팝업·바텀시트", "호스트 전환 다이얼로그 닫기 버튼 없음", "중간")
            else:
                log_issue(state, "G-MY.login", "팝업·바텀시트", f"'{text}' 클릭해도 다이얼로그 미노출", "높음")
            break
        except Exception:
            continue

    # 로그아웃 다이얼로그
    page.goto(f"{BASE_URL}/my")
    page.wait_for_load_state("networkidle")
    for text in ["Logout", "Log out", "로그아웃"]:
        el = page.get_by_text(text).first
        try:
            el.wait_for(state="visible", timeout=2000)
            el.click()
            page.wait_for_timeout(1000)
            dlg = find_dialog(page)
            if dlg:
                page.screenshot(path=f"{SCREENSHOT_DIR}/g-my-logout-dialog.png")
                ok(f"'{text}' 클릭 → 다이얼로그 노출")
                close = find_close_btn(page)
                if close:
                    close.click()
                    page.wait_for_timeout(500)
                    ok("로그아웃 다이얼로그 취소 정상")
                else:
                    log_issue(state, "G-MY.login", "팝업·바텀시트", "로그아웃 다이얼로그 닫기 버튼 없음", "중간")
            else:
                log_issue(state, "G-MY.login", "팝업·바텀시트", f"'{text}' 클릭해도 다이얼로그 미노출", "높음")
            break
        except Exception:
            continue


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        print("=" * 50)
        print("HIK QA — 게스트 로그인 상태")
        print("=" * 50)

        print("\n▶ 게스트 로그인 중...")
        login_guest(page)
        print(f"  로그인 후 URL: {page.url}")

        qa_g_home(page, state="게스트")
        qa_g_my_login(page, state="게스트")

        browser.close()

    print("\n" + "=" * 50)
    print("QA 완료")
    print(f"시트: https://docs.google.com/spreadsheets/d/{QA_SHEET_ID}")
    print("=" * 50)


if __name__ == "__main__":
    main()
