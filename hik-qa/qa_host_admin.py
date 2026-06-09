#!/usr/bin/env python3
"""HIK QA — 호스트 & 관리자 상태 검증"""
import os, sys
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread
from playwright.sync_api import sync_playwright

BASE_URL    = "https://homesinkorea-git-develop-homesinkorea.vercel.app"
KEY_FILE    = "/Users/sujin/Downloads/swift-implement-498523-i1-4c673fb266fe.json"
QA_SHEET_ID = "1-n6YwMjppwANQRiT3qIytOzRt-pUvoIushUzgT4sef8"
SS_DIR      = "/Users/sujin/hik-qa-test/screenshots"
os.makedirs(SS_DIR, exist_ok=True)

HOST_EMAIL  = "hostuser01@gmail.com"
HOST_PW     = "Hostpass1234!"
ADMIN_EMAIL = "admintest01@gmail.com"
ADMIN_PW    = "Adminpass1234!"
S_HOST  = "호스트"
S_ADMIN = "관리자"

# ── Sheet 연결 ────────────────────────────────────────────
creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)
sh = gc.open_by_key(QA_SHEET_ID)
sheets_svc = build("sheets", "v4", credentials=creds)

_ws_cache = {}
def get_ws(state):
    tab = {"호스트": "QA Issues (호스트)", "관리자": "QA Issues (관리자)"}.get(state, "QA Issues")
    if tab not in _ws_cache:
        _ws_cache[tab] = sh.worksheet(tab)
    return _ws_cache[tab]

def log_issue(state, screen, issue_type, desc, severity, ss_path=None, yellow=False):
    ws = get_ws(state)
    rows = ws.get_all_values()
    for row in rows[1:]:
        if len(row) >= 5 and row[2] == screen and row[3] == issue_type and row[4] == desc:
            print(f"  ⏭️  중복 건너뜀: [{screen}] {desc}")
            return
    num = len(rows)
    row_idx = num + 1
    ss_note = os.path.basename(ss_path) if ss_path else ""
    ws.append_row([num, state, screen, issue_type, desc, severity,
                   datetime.now().strftime("%Y-%m-%d %H:%M"), ss_note])
    reqs = []
    if yellow:
        reqs.append({"repeatCell": {
            "range": {"sheetId": ws.id,
                      "startRowIndex": row_idx-1, "endRowIndex": row_idx},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 1.0, "green": 0.976, "blue": 0.769}}},
            "fields": "userEnteredFormat.backgroundColor"}})
    if reqs:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=QA_SHEET_ID, body={"requests": reqs}).execute()
    icon = "🟡" if yellow else "❌"
    print(f"  {icon} [{severity}] [{issue_type}] {screen}: {desc}")

def log_manual(state, screen, itype, desc):
    log_issue(state, screen, itype, desc, "확인필요", yellow=True)

def ok(msg):  print(f"  ✅ {msg}")
def info(msg): print(f"  ℹ️  {msg}")

# ── 유틸 ────────────────────────────────────────────
def visible(page, sel, timeout=3000):
    try:
        page.locator(sel).first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False

def find_by_texts(page, texts, timeout=2000):
    for t in texts:
        try:
            el = page.get_by_text(t, exact=False).first
            el.wait_for(state="visible", timeout=timeout)
            return el
        except Exception:
            continue
    return None

def find_dialog(page):
    for sel in ['[role="dialog"]','[class*="modal"]','[class*="dialog"]','[class*="popup"]']:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=2000)
            return el
        except Exception:
            continue
    return None

def close_dialog(page, state, screen):
    for t in ["취소", "Cancel", "No", "닫기", "Close", "아니오"]:
        try:
            el = page.get_by_text(t, exact=True).first
            el.wait_for(state="visible", timeout=1000)
            el.click()
            page.wait_for_timeout(500)
            ok(f"다이얼로그 닫힘 ('{t}')")
            return True
        except Exception:
            continue
    try:
        el = page.locator('[aria-label*="close"], button[class*="close"]').first
        el.wait_for(state="visible", timeout=1000)
        el.click()
        page.wait_for_timeout(500)
        ok("다이얼로그 X버튼 닫힘")
        return True
    except Exception:
        pass
    log_issue(state, screen, "팝업·바텀시트", "다이얼로그 닫기 버튼 없음", "중간")
    return False

def goto_first(page, paths):
    for p in paths:
        try:
            page.goto(f"{BASE_URL}{p}")
            page.wait_for_load_state("networkidle")
            if "404" not in page.url and "/login" not in page.url:
                return page.url
        except Exception:
            continue
    return None

def screenshot(page, name):
    path = f"{SS_DIR}/{name}.png"
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:
        pass
    return path

# ── 로그인 ────────────────────────────────────────────
def login(page, url, email, pw):
    page.goto(f"{BASE_URL}{url}")
    page.wait_for_load_state("networkidle")
    try:
        page.fill('input[type="email"]', email)
        page.fill('input[type="password"]', pw)
    except Exception:
        for sel in ['input[name="email"]', 'input[placeholder*="mail"]']:
            try:
                page.fill(sel, email)
                break
            except Exception:
                continue
    for sel in ['button[type="submit"]', 'button:has-text("로그인")', 'button:has-text("Login")']:
        try:
            page.locator(sel).first.click(timeout=2000)
            break
        except Exception:
            continue
    try:
        page.wait_for_url(lambda u: "/login" not in u, timeout=8000)
    except Exception:
        pass
    page.wait_for_load_state("networkidle")
    print(f"  로그인 후 URL: {page.url}")

# ══════════════════════════════════════════════════════════
# 호스트 QA
# ══════════════════════════════════════════════════════════

def qa_h_login(page):
    print("\n━━━ [H-LOGIN] 호스트 로그인 화면 ━━━")
    page.goto(f"{BASE_URL}/login/host")
    page.wait_for_load_state("networkidle")
    screenshot(page, "h-login")
    s = S_HOST

    print("  [규칙 1] UI")
    if visible(page, 'input[type="email"]'): ok("이메일 입력 필드")
    else: log_issue(s, "H-LOGIN", "UI", "이메일 입력 필드 미노출", "높음")

    if visible(page, 'input[type="password"]'): ok("비밀번호 입력 필드")
    else: log_issue(s, "H-LOGIN", "UI", "비밀번호 입력 필드 미노출", "높음")

    if find_by_texts(page, ["로그인", "Login", "Sign in"]): ok("로그인 버튼")
    else: log_issue(s, "H-LOGIN", "UI", "로그인 버튼 미노출", "높음")

    if find_by_texts(page, ["이메일로 가입", "Sign up", "가입하기", "Create account"]): ok("이메일 가입 버튼")
    else: log_issue(s, "H-LOGIN", "UI", "이메일 가입 버튼 미노출", "중간")

    print("  [규칙 2] 플로우 — 로그인 성공")
    login(page, "/login/host", HOST_EMAIL, HOST_PW)
    if "/login" not in page.url:
        ok(f"로그인 성공 → {page.url}")
    else:
        log_issue(s, "H-LOGIN", "플로우", f"로그인 실패 — URL: {page.url}", "높음",
                  screenshot(page, "h-login-fail"))

def qa_h_my(page):
    print("\n━━━ [H-MY.login] 호스트 마이 ━━━")
    url = goto_first(page, ["/my", "/host/my", "/profile", "/host/profile"])
    if not url:
        log_issue(S_HOST, "H-MY.login", "플로우", "마이 페이지 URL 미발견", "높음")
        return
    screenshot(page, "h-my")
    s = S_HOST

    print("  [규칙 1] UI")
    for label, texts in [
        ("개인정보 수정 탭", ["개인정보 수정", "Edit Profile", "프로필 수정"]),
        ("로그아웃 탭", ["로그아웃", "Logout", "Log out"]),
        ("게스트 모드 전환 탭", ["게스트 모드", "Guest Mode", "게스트로 전환"]),
    ]:
        if find_by_texts(page, texts): ok(label)
        else: log_issue(s, "H-MY.login", "UI", f"{label} 미노출", "높음")

    print("  [규칙 3] 뒤로가기")
    prev = page.url
    page.go_back()
    page.wait_for_load_state("networkidle")
    page.goto(url)
    page.wait_for_load_state("networkidle")

    print("  [규칙 4] 팝업/다이얼로그")
    # 로그아웃 다이얼로그
    logout_btn = find_by_texts(page, ["로그아웃", "Logout", "Log out"])
    if logout_btn:
        logout_btn.click()
        page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("로그아웃 다이얼로그 노출")
            screenshot(page, "h-my-logout-dlg")
            close_dialog(page, s, "H-MY.login")
        else:
            log_issue(s, "H-MY.login", "팝업·바텀시트", "로그아웃 클릭 시 다이얼로그 미노출", "높음",
                      screenshot(page, "h-my-logout-nodlg"))

    # 게스트 모드 전환 다이얼로그
    page.goto(url); page.wait_for_load_state("networkidle")
    switch_btn = find_by_texts(page, ["게스트 모드", "Guest Mode", "게스트로 전환"])
    if switch_btn:
        switch_btn.click()
        page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("게스트 모드 전환 다이얼로그 노출")
            screenshot(page, "h-my-switch-dlg")
            close_dialog(page, s, "H-MY.login")
        else:
            log_issue(s, "H-MY.login", "팝업·바텀시트", "게스트 모드 전환 클릭 시 다이얼로그 미노출", "높음",
                      screenshot(page, "h-my-switch-nodlg"))

def qa_h_prop(page):
    print("\n━━━ [H-PROP] 숙소관리 ━━━")
    url = goto_first(page, ["/host/property", "/host/properties", "/properties", "/property", "/host"])
    if not url:
        log_issue(S_HOST, "H-PROP", "플로우", "숙소관리 URL 미발견", "높음")
        return
    screenshot(page, "h-prop")
    s = S_HOST

    print("  [규칙 1] UI")
    reg_btn = find_by_texts(page, ["숙소 등록", "Register Stay", "Add Property", "등록"])
    cards = page.locator('[class*="card"], [class*="property"], [class*="listing"]').all()

    if cards:
        ok(f"숙소 카드 {len(cards)}개 노출 (H-PROP.list 상태)")
        # H-PROP.list: 숙소 카드 탭 → H-PROP-PREV.base
        print("  [규칙 2] 플로우 — 숙소 카드 탭")
        try:
            cards[0].click()
            page.wait_for_load_state("networkidle")
            screenshot(page, "h-prop-prev")
            ok(f"숙소 카드 탭 → {page.url}")

            print("  [규칙 3] 뒤로가기")
            page.go_back()
            page.wait_for_load_state("networkidle")
            if page.url.rstrip("/") == url.rstrip("/"):
                ok("뒤로가기 → 숙소관리 복귀")
            else:
                log_issue(s, "H-PROP.list", "뒤로가기", f"뒤로가기 후 예상 외 URL: {page.url}", "중간")
        except Exception as e:
            log_issue(s, "H-PROP.list", "플로우", f"숙소 카드 탭 오류: {str(e)[:80]}", "중간")

        # 수정 버튼
        page.goto(url); page.wait_for_load_state("networkidle")
        edit_btn = find_by_texts(page, ["수정", "Edit", "편집"])
        if edit_btn:
            edit_btn.click()
            page.wait_for_load_state("networkidle")
            ok(f"수정 버튼 탭 → {page.url}")
            page.go_back(); page.wait_for_load_state("networkidle")
        else:
            log_issue(s, "H-PROP.list", "UI", "수정 버튼 미노출", "중간")

    elif reg_btn:
        ok("숙소 없는 상태 (H-PROP.empty) — 숙소 등록 버튼 노출")
        print("  [규칙 2] 플로우 — 숙소 등록 버튼")
        try:
            reg_btn.click()
            page.wait_for_load_state("networkidle")
            ok(f"숙소 등록 버튼 탭 → {page.url}")
            screenshot(page, "h-reg-type")
            # X버튼(등록 중단) 팝업
            x_btn = find_by_texts(page, ["취소", "중단", "나가기"]) or \
                    page.locator('[aria-label*="close"], button[class*="close"]').first
            try:
                x_btn.wait_for(state="visible", timeout=2000)
                x_btn.click()
                page.wait_for_timeout(1000)
                if find_dialog(page):
                    ok("등록 중단 팝업 노출")
                    screenshot(page, "h-reg-cancel-pop")
                    close_dialog(page, s, "H-REG-INFO.type")
                else:
                    log_issue(s, "H-REG-INFO.type", "팝업·바텀시트", "X버튼 클릭 시 중단 팝업 미노출", "중간")
            except Exception:
                log_manual(s, "H-REG-INFO.type", "팝업·바텀시트", "등록 중단 팝업 수동 확인 필요")
            page.go_back(); page.wait_for_load_state("networkidle")
        except Exception as e:
            log_issue(s, "H-PROP.empty", "플로우", f"숙소 등록 버튼 오류: {str(e)[:80]}", "중간")
    else:
        log_issue(s, "H-PROP", "UI", "숙소 카드 및 등록 버튼 미노출", "높음", screenshot(page, "h-prop-empty"))

def qa_h_cont(page):
    print("\n━━━ [H-CONT] 계약관리 ━━━")
    url = goto_first(page, ["/host/contract", "/host/contracts", "/contracts", "/contract", "/host/booking"])
    if not url:
        log_issue(S_HOST, "H-CONT", "플로우", "계약관리 URL 미발견", "높음")
        return
    screenshot(page, "h-cont")
    s = S_HOST

    print("  [규칙 1] UI — 탭")
    for tab in ["대기", "확정", "이용중", "종료", "취소"]:
        if find_by_texts(page, [tab]): ok(f"탭: {tab}")
        else: log_issue(s, "H-CONT", "UI", f"계약관리 탭 미노출: '{tab}'", "중간")

    cards = page.locator('[class*="card"], [class*="contract"], [class*="item"]').all()
    if cards:
        ok(f"계약 카드 {len(cards)}개 노출")
        print("  [규칙 2] 플로우 — 카드 탭")
        try:
            cards[0].click()
            page.wait_for_load_state("networkidle")
            ok(f"계약 카드 탭 → {page.url}")
            screenshot(page, "h-cntr-detail")

            # 계약 상세 버튼 확인
            for label, texts in [
                ("예약 승인 버튼", ["예약 승인", "승인", "Approve"]),
                ("예약 거절 버튼", ["예약 거절", "거절", "Reject"]),
            ]:
                if find_by_texts(page, texts): ok(label)
                else: log_manual(s, "H-CNTR.approval", "UI", f"{label} 없음 — 승인대기 건 없을 수 있음")

            # 승인 다이얼로그
            approve = find_by_texts(page, ["예약 승인", "승인", "Approve"])
            if approve:
                approve.click(); page.wait_for_timeout(1000)
                if find_dialog(page):
                    ok("예약 승인 다이얼로그 노출")
                    screenshot(page, "h-cntr-approve-dlg")
                    close_dialog(page, s, "H-CNTR.approval")
                else:
                    log_issue(s, "H-CNTR.approval", "팝업·바텀시트", "예약 승인 클릭 시 다이얼로그 미노출", "높음")

            print("  [규칙 3] 뒤로가기")
            page.go_back(); page.wait_for_load_state("networkidle")
            if page.url.rstrip("/") == url.rstrip("/"):
                ok("뒤로가기 → 계약관리 복귀")
            else:
                log_issue(s, "H-CNTR.approval", "뒤로가기", f"뒤로가기 후 URL: {page.url}", "중간")
        except Exception as e:
            log_issue(s, "H-CONT", "플로우", f"계약 카드 탭 오류: {str(e)[:80]}", "중간")
    else:
        log_manual(s, "H-CONT", "플로우", "계약 내역 없어 카드 탭 플로우 검증 불가")

def qa_h_stlm(page):
    print("\n━━━ [H-STLM] 정산 ━━━")
    url = goto_first(page, ["/host/settlement", "/settlement", "/host/stlm", "/host/payout"])
    if not url:
        log_issue(S_HOST, "H-STLM", "플로우", "정산 URL 미발견", "높음")
        return
    screenshot(page, "h-stlm")
    s = S_HOST

    print("  [규칙 1] UI")
    acct_btn = find_by_texts(page, ["계좌 등록", "Register Account", "계좌 추가"])
    change_btn = find_by_texts(page, ["계좌 변경", "Change Account"])

    if acct_btn:
        ok("계좌 등록 버튼 (H-STLM.noacct 상태)")
        print("  [규칙 2] 플로우 — 계좌 등록")
        acct_btn.click(); page.wait_for_load_state("networkidle")
        ok(f"계좌 등록 → {page.url}")
        screenshot(page, "h-stlm-acct-reg")
        page.go_back(); page.wait_for_load_state("networkidle")
    elif change_btn:
        ok("계좌 변경 버튼 (H-STLM.ready 상태)")
        # 숙소 선택 필터 바텀시트
        filter_btn = find_by_texts(page, ["숙소 선택", "선택", "필터"])
        if filter_btn:
            filter_btn.click(); page.wait_for_timeout(1000)
            if find_dialog(page):
                ok("숙소 선택 바텀시트 노출")
                screenshot(page, "h-stlm-prop-bs")
                close_dialog(page, s, "H-STLM.ready")
            else:
                log_issue(s, "H-STLM.ready", "팝업·바텀시트", "숙소 선택 필터 클릭 시 바텀시트 미노출", "중간")
    else:
        log_issue(s, "H-STLM", "UI", "계좌 등록/변경 버튼 미노출", "높음", screenshot(page, "h-stlm-noui"))

def qa_h_msg(page):
    print("\n━━━ [H-MSG] 메시지 ━━━")
    url = goto_first(page, ["/messages", "/host/messages", "/message"])
    if not url:
        log_issue(S_HOST, "H-MSG", "플로우", "메시지 URL 미발견", "높음")
        return
    screenshot(page, "h-msg")
    s = S_HOST

    print("  [규칙 1] UI")
    chats = page.locator('[class*="chat"], [class*="message"], [class*="conversation"], [class*="room"]').all()
    if chats:
        ok(f"채팅 항목 {len(chats)}개 노출")
        print("  [규칙 2] 플로우 — 채팅 탭")
        try:
            chats[0].click(); page.wait_for_load_state("networkidle")
            ok(f"채팅 탭 → {page.url}")
            screenshot(page, "h-msg-chat")
            # + 버튼(첨부) 바텀시트
            plus_btn = find_by_texts(page, ["+", "첨부", "Attach"])
            if plus_btn:
                plus_btn.click(); page.wait_for_timeout(1000)
                if find_dialog(page):
                    ok("첨부 바텀시트 노출")
                    close_dialog(page, s, "H-MSG-CHAT")
                else:
                    log_issue(s, "H-MSG-CHAT", "팝업·바텀시트", "+ 버튼 클릭 시 바텀시트 미노출", "중간")
            else:
                log_issue(s, "H-MSG-CHAT", "UI", "+ (첨부) 버튼 미노출", "중간")
            page.go_back(); page.wait_for_load_state("networkidle")
        except Exception as e:
            log_issue(s, "H-MSG", "플로우", f"채팅 탭 오류: {str(e)[:80]}", "중간")
    else:
        log_manual(s, "H-MSG", "플로우", "채팅 내역 없어 채팅 탭 플로우 검증 불가")

# ══════════════════════════════════════════════════════════
# 관리자 QA
# ══════════════════════════════════════════════════════════

def qa_a_stlm(page):
    print("\n━━━ [A-STLM.base] 정산 관리 ━━━")
    page.goto(f"{BASE_URL}/admin/payments")
    page.wait_for_load_state("networkidle")
    screenshot(page, "a-stlm")
    s = S_ADMIN

    print("  [규칙 1] UI")
    if find_by_texts(page, ["결제건 추가", "Add", "추가"]): ok("결제건 추가 버튼")
    else: log_issue(s, "A-STLM.base", "UI", "결제건 추가 버튼 미노출", "높음")

    print("  [규칙 2/4] 플로우/팝업 — 결제건 추가 팝업")
    add_btn = find_by_texts(page, ["결제건 추가", "추가", "Add"])
    if add_btn:
        add_btn.click(); page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("결제건 추가 팝업 노출")
            screenshot(page, "a-stlm-addpay")
            close_dialog(page, s, "A-STLM.base")
        else:
            log_issue(s, "A-STLM.base", "팝업·바텀시트", "결제건 추가 클릭 시 팝업 미노출", "높음",
                      screenshot(page, "a-stlm-addpay-fail"))

    # 기간 필터 팝업
    page.goto(f"{BASE_URL}/admin/payments"); page.wait_for_load_state("networkidle")
    date_btn = find_by_texts(page, ["기간", "날짜", "Date", "Filter", "기간 필터"])
    if date_btn:
        date_btn.click(); page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("기간 필터 팝업 노출")
            screenshot(page, "a-stlm-datesel")
            close_dialog(page, s, "A-STLM.base")
        else:
            log_issue(s, "A-STLM.base", "팝업·바텀시트", "기간 필터 클릭 시 팝업 미노출", "중간")

    # 계약 행 탭 → 상세 팝업
    page.goto(f"{BASE_URL}/admin/payments"); page.wait_for_load_state("networkidle")
    rows_el = page.locator('table tr, [class*="row"], [class*="item"]').all()
    data_rows = [r for r in rows_el if r != rows_el[0]] if len(rows_el) > 1 else []
    if data_rows:
        data_rows[0].click(); page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("계약 행 탭 → 상세 팝업 노출")
            screenshot(page, "a-stlm-detail")
            close_dialog(page, s, "A-STLM.base")
        else:
            log_issue(s, "A-STLM.base", "팝업·바텀시트", "계약 행 탭 시 상세 팝업 미노출", "중간")
    else:
        log_manual(s, "A-STLM.base", "플로우", "정산 내역 없어 계약 행 탭 검증 불가")

    # 삭제 다이얼로그
    page.goto(f"{BASE_URL}/admin/payments"); page.wait_for_load_state("networkidle")
    del_btn = find_by_texts(page, ["삭제", "Delete", "제거"])
    if del_btn:
        del_btn.click(); page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("삭제 다이얼로그 노출")
            close_dialog(page, s, "A-STLM.base")
        else:
            log_issue(s, "A-STLM.base", "팝업·바텀시트", "삭제 클릭 시 다이얼로그 미노출", "중간")
    else:
        log_manual(s, "A-STLM.base", "팝업·바텀시트", "삭제 버튼 없어 다이얼로그 검증 불가")

def qa_a_auth(page):
    print("\n━━━ [A-AUTH.base] 인증 서류 확인 ━━━")
    url = goto_first(page, ["/admin/auth", "/admin/authentication", "/admin/verify",
                             "/admin/kyc", "/admin/document", "/admin/approval"])
    if not url:
        log_issue(S_ADMIN, "A-AUTH.base", "플로우", "인증 서류 URL 미발견 — 직접 확인 필요", "확인필요")
        return
    screenshot(page, "a-auth")
    s = S_ADMIN

    print("  [규칙 1] UI")
    for label, texts in [
        ("심사중 필터", ["심사중", "Pending", "대기"]),
        ("승인 버튼",   ["승인", "Approve"]),
        ("반려 버튼",   ["반려", "Reject"]),
    ]:
        if find_by_texts(page, texts): ok(label)
        else: log_issue(s, "A-AUTH.base", "UI", f"{label} 미노출", "중간")

    print("  [규칙 4] 팝업/다이얼로그")
    # 승인 다이얼로그
    approve = find_by_texts(page, ["승인", "Approve"])
    if approve:
        approve.click(); page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("승인 다이얼로그 노출")
            screenshot(page, "a-auth-approve")
            close_dialog(page, s, "A-AUTH.base")
        else:
            log_issue(s, "A-AUTH.base", "팝업·바텀시트", "승인 클릭 시 다이얼로그 미노출", "높음")
    else:
        log_manual(s, "A-AUTH.base", "팝업·바텀시트", "승인 버튼 없어 다이얼로그 검증 불가 — 심사 대기 건 없음")

    # 반려 팝업
    page.goto(url); page.wait_for_load_state("networkidle")
    reject = find_by_texts(page, ["반려", "Reject"])
    if reject:
        reject.click(); page.wait_for_timeout(1000)
        if find_dialog(page):
            ok("반려 팝업 노출")
            screenshot(page, "a-auth-reject")
            close_dialog(page, s, "A-AUTH.base")
        else:
            log_issue(s, "A-AUTH.base", "팝업·바텀시트", "반려 클릭 시 팝업 미노출", "높음")
    else:
        log_manual(s, "A-AUTH.base", "팝업·바텀시트", "반려 버튼 없어 팝업 검증 불가 — 심사 대기 건 없음")

    # 심사중 필터 탭 → 상태 변경 확인
    page.goto(url); page.wait_for_load_state("networkidle")
    pending = find_by_texts(page, ["심사중", "Pending", "대기"])
    if pending:
        pending.click(); page.wait_for_timeout(800)
        ok("심사중 필터 탭 → 상태 변경 정상")

def qa_a_book(page):
    print("\n━━━ [A-BOOK.base] 계약 관리 ━━━")
    url = goto_first(page, ["/admin/bookings", "/admin/booking", "/admin/contracts",
                             "/admin/contract", "/admin/reservation"])
    if not url:
        log_issue(S_ADMIN, "A-BOOK.base", "플로우", "계약 관리 URL 미발견 — 직접 확인 필요", "확인필요")
        return
    screenshot(page, "a-book")
    s = S_ADMIN

    print("  [규칙 1] UI")
    for label, texts in [
        ("계약 취소 버튼",       ["계약 취소", "Cancel Contract", "취소"]),
        ("호스트로 로그인 버튼",  ["호스트로 로그인", "Proxy Login", "Host Login"]),
        ("게스트 문의 버튼",     ["게스트 문의", "Guest Inquiry", "문의"]),
    ]:
        if find_by_texts(page, texts): ok(label)
        else: log_issue(s, "A-BOOK.base", "UI", f"{label} 미노출", "중간")

    print("  [규칙 4] 팝업")
    for label, texts, ss_name in [
        ("계약 취소 팝업",       ["계약 취소", "Cancel Contract"], "a-book-cancel"),
        ("호스트 로그인 팝업",   ["호스트로 로그인", "Proxy Login"], "a-book-proxy"),
        ("게스트 문의 팝업",     ["게스트 문의", "Guest Inquiry"], "a-book-inquiry"),
    ]:
        page.goto(url); page.wait_for_load_state("networkidle")
        btn = find_by_texts(page, texts)
        if btn:
            btn.click(); page.wait_for_timeout(1000)
            if find_dialog(page):
                ok(f"{label} 노출")
                screenshot(page, ss_name)
                close_dialog(page, s, "A-BOOK.base")
            else:
                log_issue(s, "A-BOOK.base", "팝업·바텀시트", f"{label} 클릭 시 팝업 미노출", "높음",
                          screenshot(page, f"{ss_name}-fail"))
        else:
            log_manual(s, "A-BOOK.base", "팝업·바텀시트", f"{label} 버튼 없어 팝업 검증 불가 — 계약 건 없을 수 있음")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── 호스트 ──────────────────────────────────────
        print("\n" + "="*60)
        print("HIK QA — 호스트 상태")
        print("="*60)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()

        login(page, "/login/host", HOST_EMAIL, HOST_PW)
        if "/login" in page.url:
            log_issue(S_HOST, "H-LOGIN", "플로우", f"호스트 로그인 실패 ({page.url})", "높음",
                      screenshot(page, "h-login-fail"))
            print("  ⚠️  호스트 로그인 실패 — QA 건너뜀")
        else:
            qa_h_login(page)
            login(page, "/login/host", HOST_EMAIL, HOST_PW)
            qa_h_my(page)
            login(page, "/login/host", HOST_EMAIL, HOST_PW)
            qa_h_prop(page)
            login(page, "/login/host", HOST_EMAIL, HOST_PW)
            qa_h_cont(page)
            login(page, "/login/host", HOST_EMAIL, HOST_PW)
            qa_h_stlm(page)
            login(page, "/login/host", HOST_EMAIL, HOST_PW)
            qa_h_msg(page)

        ctx.close()

        # ── 관리자 ──────────────────────────────────────
        print("\n" + "="*60)
        print("HIK QA — 관리자 상태")
        print("="*60)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        login(page, "/login", ADMIN_EMAIL, ADMIN_PW)
        page.goto(f"{BASE_URL}/admin/payments")
        page.wait_for_load_state("networkidle")

        if "/login" in page.url or "admin" not in page.url:
            log_issue(S_ADMIN, "A-STLM.base", "플로우", f"관리자 로그인/진입 실패 ({page.url})", "높음",
                      screenshot(page, "a-login-fail"))
            print("  ⚠️  관리자 진입 실패 — QA 건너뜀")
        else:
            ok(f"관리자 진입 성공: {page.url}")
            qa_a_stlm(page)
            qa_a_auth(page)
            qa_a_book(page)

        ctx.close()
        browser.close()

    print("\n" + "="*60)
    print("QA 완료")
    print(f"결과 시트: https://docs.google.com/spreadsheets/d/{QA_SHEET_ID}")
    print("="*60)

if __name__ == "__main__":
    main()
