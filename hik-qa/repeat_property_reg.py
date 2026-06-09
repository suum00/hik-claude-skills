"""숙소등록 반복 테스트 — 10회, 회차마다 사진 2~15장 순환
- 각 회차 독립 컨텍스트(storage_state 재사용)로 드래프트 오염 방지
- 실패 시 → 반복테스트 탭 + QA Issues (호스트) 탭 동시 기록
"""
import sys, os, tempfile
sys.path.insert(0, '/Users/sujin/hik-qa-test')
from qa_runner import BASE_URL, log_repeat_test, log_issue, SCREENSHOT_DIR
from playwright.sync_api import sync_playwright

ASSETS = os.path.expanduser("~/hik-qa-test/assets")
ALL_IMGS = sorted([os.path.join(ASSETS, f"test_room_{i}.jpg") for i in range(1, 16)])
REPEAT = 10


# ─────────────────────────────────────────────────
# Kakao 주소 팝업 처리
# ─────────────────────────────────────────────────
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
    val = page.locator('input[placeholder*="주소찾기"]').first.input_value()
    if not val:
        raise Exception("주소 입력 실패")


def click_next(page, label=""):
    btn = page.locator('button:has-text("다음으로")').last
    btn.wait_for(state="visible", timeout=5000)
    d = btn.get_attribute("data-disabled")
    dis = btn.get_attribute("disabled")
    if d is not None or dis is not None:
        raise Exception(f"다음으로 버튼 비활성{(' — '+label) if label else ''} (URL={page.url})")
    btn.click()
    page.wait_for_timeout(1500)


def wait_btn_active(page, text, timeout_ms=12000):
    for _ in range(timeout_ms // 500):
        page.wait_for_timeout(500)
        btn = page.locator(f'button:has-text("{text}")').last
        try:
            if btn.get_attribute("data-disabled") is None:
                return btn
        except Exception:
            pass
    raise Exception(f"'{text}' 버튼 활성화 타임아웃")


def upload_and_activate(page, imgs, btn_text):
    file_input = page.locator('input[type="file"]').first
    file_input.wait_for(state="attached", timeout=5000)
    file_input.set_input_files(imgs)
    return wait_btn_active(page, btn_text)


# ─────────────────────────────────────────────────
# 한 회차 등록 실행 (독립 context 안에서)
# ─────────────────────────────────────────────────
def run_one_registration(context, idx, photo_count):
    page = context.new_page()
    room_imgs = ALL_IMGS[:photo_count]
    prop_imgs = ALL_IMGS[:photo_count]

    # Step1
    page.goto(f"{BASE_URL}/properties/new")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    page.get_by_text("쉐어하우스", exact=False).first.click()
    page.wait_for_timeout(400)
    page.get_by_text("성별 무관", exact=False).first.click()
    page.wait_for_timeout(400)
    click_next(page, "step1")

    # Step2: 주소
    fill_address_kakao(context, page)
    page.locator('input[placeholder*="상세 주소"]').first.fill("101호")
    page.wait_for_timeout(300)
    click_next(page, "step2")

    # Step3: 방 추가
    page.locator('button:has-text("방 추가")').first.wait_for(state="visible", timeout=5000)
    page.locator('button:has-text("방 추가")').first.click()
    page.wait_for_timeout(1000)

    page.locator('input[placeholder*="Room"]').first.fill(f"QA방-{idx+1:02d}")
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

    # 방 사진 업로드
    add_btn = upload_and_activate(page, room_imgs, "추가하기")
    add_btn.click()
    page.wait_for_timeout(2000)

    # Step3 목록 → Step4
    click_next(page, "step3-list")

    # Step4: 공용시설 (선택사항)
    click_next(page, "step4-options")

    # Step5: 규칙
    click_next(page, "step5-rules")

    # Step6: 숙소 이름 + 소개
    try:
        page.locator('input[placeholder*="쉐어하우스"]').first.fill(
            f"QA테스트 쉐어하우스 {idx+1:02d}호"
        )
        page.wait_for_timeout(200)
    except Exception:
        pass
    try:
        page.locator('textarea').first.fill(
            "QA 자동화 테스트용 숙소. 강남 중심부 위치. 교통 편리."
        )
        page.wait_for_timeout(200)
    except Exception:
        pass
    click_next(page, "intro")

    # 숙소 사진 업로드
    done_btn = upload_and_activate(page, prop_imgs, "등록 완료")
    done_btn.click()
    # 등록 처리에 최대 20초 소요 — complete 페이지 또는 목록으로 이동 대기
    try:
        page.wait_for_url(
            lambda u: "complete" in u or ("/properties/" in u and "new" not in u),
            timeout=20000
        )
    except Exception:
        pass
    page.wait_for_timeout(1000)

    url = page.url
    if "complete" not in url and ("new" in url or "/properties/new" in url):
        raise Exception(f"등록 완료 후 이동 실패 (URL={url})")

    page.close()
    return url


# ─────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ── 1. 호스트 로그인 후 storage_state 저장 ──
    print("▶ 호스트 로그인 (storage_state 저장)...")
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
    print(f"  로그인: {login_page.url}")

    # storage_state를 임시 파일로 저장
    state_file = tempfile.mktemp(suffix=".json")
    login_ctx.storage_state(path=state_file)
    login_ctx.close()
    print(f"  세션 저장: {state_file}")

    # ── 2. 10회 반복 ──
    print(f"\n  ▶ 숙소등록 반복테스트 {REPEAT}회 시작...")
    failures = []

    for i in range(REPEAT):
        photo_count = (i % 14) + 2   # 2, 3, 4, ..., 15, 2, 3, ...
        print(f"\n  [회차 {i+1}/{REPEAT}] 사진 {photo_count}장")

        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            storage_state=state_file,
        )
        ss_path = None
        try:
            result_url = run_one_registration(ctx, i, photo_count)
            print(f"    {i+1}회: ✅ → {result_url}")
        except Exception as e:
            err_msg = str(e)
            # 스크린샷 — 현재 열린 페이지에서 촬영
            try:
                pages = ctx.pages
                if pages:
                    ss_path = os.path.join(SCREENSHOT_DIR, f"reg_fail_{i+1}.png")
                    pages[-1].screenshot(path=ss_path)
            except Exception:
                ss_path = None

            failures.append((i + 1, err_msg, ss_path))
            print(f"    {i+1}회: ❌ {err_msg[:80]}")

            # QA Issues (호스트) 기록
            try:
                pages = ctx.pages
                url_short = ""
                if pages:
                    url_short = pages[-1].url.split(
                        "homesinkorea-git-develop-homesinkorea.vercel.app"
                    )[-1]
                description = (
                    f"[{i+1}회차/사진{photo_count}장] "
                    f"{err_msg[:100]} (URL: {url_short})"
                )
                log_issue(
                    state="호스트",
                    screen="H-REG (숙소등록 반복)",
                    issue_type="플로우",
                    description=description,
                    severity="높음",
                    screenshot_path=ss_path,
                )
            except Exception as log_err:
                print(f"    QA 기록 실패: {log_err}")
        finally:
            ctx.close()

    # ── 3. 반복테스트 탭 기록 ──
    log_repeat_test("숙소등록", REPEAT, failures)

    # 임시 파일 정리
    try:
        os.unlink(state_file)
    except Exception:
        pass

    browser.close()

print("\n완료")
