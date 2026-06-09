"""사진 없이 숙소 등록 가능한지 20회 시도
- 방 사진 / 숙소 사진 모두 업로드하지 않고 버튼 활성 여부 + 등록 완료 여부 확인
- 성공(등록 완료) / 실패(버튼 비활성·에러) 구분하여 반복테스트 탭에 기록
- 1회라도 등록이 완료되면 QA Issues (호스트)에도 별도 이슈로 기록
"""
import sys, os, tempfile
sys.path.insert(0, '/Users/sujin/hik-qa-test')
from qa_runner import BASE_URL, log_repeat_test, log_issue, SCREENSHOT_DIR
from playwright.sync_api import sync_playwright

ASSETS = os.path.expanduser("~/hik-qa-test/assets")
REPEAT = 20
SS_DIR = os.path.join(SCREENSHOT_DIR, "no-photo-reg")
os.makedirs(SS_DIR, exist_ok=True)


def fill_address_kakao(context, page, address="강남구 테헤란로 152"):
    addr_btn = page.get_by_text("주소찾기").first
    addr_btn.wait_for(state="visible", timeout=5000)
    with context.expect_page(timeout=6000) as popup_info:
        addr_btn.click()
    popup = popup_info.value
    page.wait_for_timeout(2000)
    kakao_frame = None
    for f in popup.frames:
        if "postcode.map.kakao.com" in f.url:
            kakao_frame = f
            break
    if not kakao_frame:
        raise Exception("Kakao iframe 없음")
    kakao_frame.evaluate(
        "(a) => { const inp = document.querySelector('input#region_name'); "
        "if (inp) { inp.value = a; inp.dispatchEvent(new Event('input', {bubbles:true})); } }",
        address
    )
    page.wait_for_timeout(400)
    kakao_frame.locator("input[type='text']").first.press("Enter")
    page.wait_for_timeout(2000)
    li = kakao_frame.locator("li").first
    li.wait_for(state="visible", timeout=6000)
    li.click(force=True)
    page.wait_for_timeout(1500)


def click_next(page, label=""):
    btn = page.locator('button:has-text("다음으로")').last
    btn.wait_for(state="visible", timeout=5000)
    d = btn.get_attribute("data-disabled")
    dis = btn.get_attribute("disabled")
    if d is not None or dis is not None:
        raise Exception(f"다음으로 버튼 비활성{(' — '+label) if label else ''}")
    btn.click()
    page.wait_for_timeout(1500)


def check_btn_state(page, text):
    """버튼 data-disabled / disabled 속성 반환 (활성이면 None)"""
    try:
        btn = page.locator(f'button:has-text("{text}")').last
        btn.wait_for(state="visible", timeout=5000)
        d = btn.get_attribute("data-disabled")
        dis = btn.get_attribute("disabled")
        return d, dis, btn
    except Exception as e:
        return "not_found", "not_found", None


def run_one(context, idx):
    """
    반환: (result, detail, ss_path)
      result: "registered" | "btn_disabled" | "error"
      detail: 상세 설명
    """
    page = context.new_page()
    ss_path = None

    try:
        # Step1
        page.goto(f"{BASE_URL}/properties/new")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)
        page.get_by_text("쉐어하우스", exact=False).first.click()
        page.wait_for_timeout(400)
        page.get_by_text("성별 무관", exact=False).first.click()
        page.wait_for_timeout(400)
        click_next(page, "step1")

        # Step2
        fill_address_kakao(context, page)
        page.locator('input[placeholder*="상세 주소"]').first.fill("101호")
        page.wait_for_timeout(300)
        click_next(page, "step2")

        # Step3: 방 추가
        page.locator('button:has-text("방 추가")').first.wait_for(state="visible", timeout=5000)
        page.locator('button:has-text("방 추가")').first.click()
        page.wait_for_timeout(1000)
        page.locator('input[placeholder*="Room"]').first.fill(f"NoPhoto방-{idx+1:02d}")
        for inp in page.locator('input[placeholder*="KRW"]').all()[:2]:
            inp.fill("500"); page.wait_for_timeout(100)
        try:
            page.locator('input[placeholder*="청소비"]').first.fill("50")
        except Exception:
            pass
        page.wait_for_timeout(300)
        click_next(page, "방-정보")

        # Step3-space
        try:
            page.locator('input[placeholder="층"]').first.fill("1"); page.wait_for_timeout(200)
        except Exception:
            pass
        try:
            page.locator('input[placeholder*="m²"]').first.fill("10"); page.wait_for_timeout(200)
        except Exception:
            pass
        click_next(page, "space")

        # Step3-options
        try:
            page.get_by_text("Wi-Fi", exact=True).first.click(); page.wait_for_timeout(300)
        except Exception:
            pass
        click_next(page, "room-options")

        # ── 방 사진 업로드 없이 버튼 상태 확인 ──
        page.wait_for_timeout(1000)
        ss_path = os.path.join(SS_DIR, f"room_photo_page_{idx+1:02d}.png")
        page.screenshot(path=ss_path, full_page=True)

        d_add, dis_add, add_btn = check_btn_state(page, "추가하기")
        room_btn_active = (d_add is None and dis_add is None and add_btn is not None)

        if room_btn_active:
            # 버튼이 활성화되어 있으면 클릭
            add_btn.click()
            page.wait_for_timeout(2000)
            print(f"  [{idx+1}] 방 사진 없이 '추가하기' 활성 → 클릭 성공")
        else:
            print(f"  [{idx+1}] 방 사진 없이 '추가하기' 비활성 (data-disabled={d_add!r})")

        # Step3 목록 → Step4 시도
        try:
            click_next(page, "step3-list")
        except Exception as e:
            ss_path = os.path.join(SS_DIR, f"step3_blocked_{idx+1:02d}.png")
            page.screenshot(path=ss_path, full_page=True)
            return ("btn_disabled",
                    f"방 사진 없음: 방 추가하기 btn={('활성' if room_btn_active else '비활성')}, step3→step4 막힘 ({e})",
                    ss_path)

        # Step4: 공용시설
        click_next(page, "step4")

        # Step5: 규칙
        click_next(page, "step5")

        # Step6: 숙소 이름 + 소개
        try:
            page.locator('input[placeholder*="쉐어하우스"]').first.fill(
                f"NoPhoto 테스트 {idx+1:02d}호"
            )
            page.wait_for_timeout(200)
        except Exception:
            pass
        try:
            page.locator('textarea').first.fill("사진 없이 등록 테스트")
            page.wait_for_timeout(200)
        except Exception:
            pass
        click_next(page, "intro")

        # ── 숙소 사진 업로드 없이 버튼 상태 확인 ──
        page.wait_for_timeout(1000)
        ss_path = os.path.join(SS_DIR, f"prop_photo_page_{idx+1:02d}.png")
        page.screenshot(path=ss_path, full_page=True)

        d_done, dis_done, done_btn = check_btn_state(page, "등록 완료")
        prop_btn_active = (d_done is None and dis_done is None and done_btn is not None)

        if not prop_btn_active:
            return ("btn_disabled",
                    f"숙소 사진 없음: '등록 완료' 버튼 비활성 (data-disabled={d_done!r}) — 정상 차단",
                    ss_path)

        # 버튼이 활성화된 경우 클릭 시도
        print(f"  [{idx+1}] ⚠️  숙소 사진 없이 '등록 완료' 활성 → 클릭 시도")
        done_btn.click()
        try:
            page.wait_for_url(
                lambda u: "complete" in u or ("/properties/" in u and "new" not in u),
                timeout=20000
            )
        except Exception:
            pass
        page.wait_for_timeout(1000)

        url = page.url
        ss_path = os.path.join(SS_DIR, f"after_submit_{idx+1:02d}.png")
        page.screenshot(path=ss_path, full_page=True)

        if "complete" in url or ("/properties/" in url and "new" not in url):
            return ("registered",
                    f"사진 없이 등록 완료됨! URL={url}",
                    ss_path)
        else:
            # 에러 토스트나 메시지 확인
            err_msg = ""
            for sel in ['[role="alert"]', '[class*="toast"]', '[class*="error"]', 'p[class*="error"]']:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=1500)
                    err_msg = el.inner_text().strip()[:80]
                    break
                except Exception:
                    pass
            return ("btn_disabled",
                    f"클릭 후 등록 미완료 (URL={url.split('/')[-1]}, msg={err_msg or '없음'})",
                    ss_path)

    except Exception as e:
        if page and not page.is_closed():
            ss_path = os.path.join(SS_DIR, f"error_{idx+1:02d}.png")
            try:
                page.screenshot(path=ss_path, full_page=True)
            except Exception:
                ss_path = None
        return ("error", str(e)[:120], ss_path)
    finally:
        page.close()


# ─────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # 호스트 로그인 → storage_state 저장
    print("▶ 호스트 로그인...")
    login_ctx = browser.new_context(viewport={"width": 390, "height": 844})
    login_page = login_ctx.new_page()
    login_page.goto(f"{BASE_URL}/login/host?next=%2Fhost")
    login_page.wait_for_load_state("domcontentloaded")
    login_page.wait_for_timeout(1500)
    login_page.fill('input[type="email"]', "hostuser01@gmail.com")
    login_page.fill('input[type="password"]', "Hostpass1234!")
    login_page.click('button[type="submit"]')
    try:
        login_page.wait_for_url(lambda u: "/login" not in u, timeout=8000)
    except Exception:
        pass
    login_page.wait_for_timeout(1500)
    state_file = tempfile.mktemp(suffix=".json")
    login_ctx.storage_state(path=state_file)
    login_ctx.close()
    print(f"  로그인 완료, 세션 저장: {state_file}\n")

    print(f"▶ 사진 없이 등록 시도 {REPEAT}회 시작...\n")
    registered_count = 0
    btn_disabled_count = 0
    error_count = 0
    failures = []  # log_repeat_test용 (성공이 아닌 케이스)
    registered_cases = []

    for i in range(REPEAT):
        print(f"  [회차 {i+1}/{REPEAT}]")
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            storage_state=state_file,
        )
        result, detail, ss_path = run_one(ctx, i)
        ctx.close()

        if result == "registered":
            registered_count += 1
            registered_cases.append((i + 1, detail, ss_path))
            print(f"    {i+1}회: 🚨 등록 완료됨! — {detail}")
        elif result == "btn_disabled":
            btn_disabled_count += 1
            print(f"    {i+1}회: ✅ 정상 차단 — {detail[:80]}")
        else:
            error_count += 1
            failures.append((i + 1, detail, ss_path))
            print(f"    {i+1}회: ❌ 오류 — {detail[:80]}")

    browser.close()
    try:
        os.unlink(state_file)
    except Exception:
        pass

# ─────────────────────────────────────────────────
# 결과 요약
# ─────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"결과 요약 ({REPEAT}회)")
print(f"  사진 없이 등록 완료(취약점): {registered_count}회")
print(f"  정상 차단(버튼 비활성):      {btn_disabled_count}회")
print(f"  스크립트 오류:               {error_count}회")
print(f"{'='*50}\n")

# ─────────────────────────────────────────────────
# 반복테스트 탭 기록
# ─────────────────────────────────────────────────
# log_repeat_test는 실패=성공하지 못한 케이스로 정의
# 여기선 "등록 완료"가 취약점(버그), "차단"이 정상이므로
# registered_cases를 failures로 전달 (등록된 게 오히려 실패)
all_failures = registered_cases + failures
log_repeat_test("숙소등록(사진없음)", REPEAT, all_failures)

# ─────────────────────────────────────────────────
# QA Issues 기록 — 취약점 발견 시
# ─────────────────────────────────────────────────
if registered_cases:
    first_ss = registered_cases[0][2] if registered_cases[0][2] else None
    log_issue(
        state="호스트",
        screen="H-REG (숙소등록)",
        issue_type="플로우",
        description=(
            f"사진 없이 숙소 등록 가능 — {REPEAT}회 중 {registered_count}회 등록 완료됨. "
            f"사진 필수 검증 로직 없음"
        ),
        severity="높음",
        screenshot_path=first_ss,
    )
    print("🚨 QA Issues (호스트)에 취약점 기록 완료")
else:
    print("✅ 사진 없이는 등록 불가 — 정상 차단 확인")

print("\n완료")
