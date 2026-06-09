"""사진 엣지케이스 2가지 테스트
  1) 사진 16장 등록 가능 여부 (제한이 있는지 확인)
  2) 이미지 외 파일(.txt / .pdf / .mp4) 업로드 시 등록 가능 여부
"""
import sys, os, tempfile, struct
sys.path.insert(0, '/Users/sujin/hik-qa-test')
from qa_runner import BASE_URL, log_issue, SCREENSHOT_DIR
from playwright.sync_api import sync_playwright

ASSETS = os.path.expanduser("~/hik-qa-test/assets")
SS_DIR = os.path.join(SCREENSHOT_DIR, "photo-edge")
os.makedirs(SS_DIR, exist_ok=True)

# 16장: test_room.jpg + test_room_1~15.jpg
ALL_16 = (
    [os.path.join(ASSETS, "test_room.jpg")]
    + sorted([os.path.join(ASSETS, f"test_room_{i}.jpg") for i in range(1, 16)])
)

# ── 비이미지 파일 생성 ──────────────────────────────────────────────────
FAKE_DIR = os.path.join(SS_DIR, "fake_files")
os.makedirs(FAKE_DIR, exist_ok=True)

def make_fake_txt():
    p = os.path.join(FAKE_DIR, "fake.txt")
    with open(p, "w") as f:
        f.write("This is a fake text file, not an image.\n" * 10)
    return p

def make_fake_pdf():
    p = os.path.join(FAKE_DIR, "fake.pdf")
    # 최소 PDF 구조
    with open(p, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 1\n0000000000 65535 f\ntrailer<</Size 1>>\n%%EOF\n")
    return p

def make_fake_mp4():
    p = os.path.join(FAKE_DIR, "fake.mp4")
    # ftyp box 흉내 (4바이트 크기 + 4바이트 'ftyp')
    with open(p, "wb") as f:
        f.write(b"\x00\x00\x00\x1cftypmp42\x00\x00\x00\x00mp42mp41isom")
        f.write(b"\x00" * 1000)
    return p

def make_fake_exe():
    p = os.path.join(FAKE_DIR, "fake.exe")
    with open(p, "wb") as f:
        f.write(b"MZ" + b"\x00" * 512)
    return p

FAKE_FILES = {
    ".txt": make_fake_txt(),
    ".pdf": make_fake_pdf(),
    ".mp4": make_fake_mp4(),
    ".exe": make_fake_exe(),
}
print(f"비이미지 테스트 파일 생성: {list(FAKE_FILES.keys())}\n")


# ──────────────────────────────────────────────────────────────────────
# 공통 헬퍼
# ──────────────────────────────────────────────────────────────────────
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
        raise Exception(f"다음으로 버튼 비활성 — {label}")
    btn.click()
    page.wait_for_timeout(1500)


def wait_btn_active(page, text, timeout_ms=15000):
    for _ in range(timeout_ms // 500):
        page.wait_for_timeout(500)
        btn = page.locator(f'button:has-text("{text}")').last
        try:
            if btn.get_attribute("data-disabled") is None:
                return btn
        except Exception:
            pass
    return None  # 타임아웃 — None 반환 (raise 대신)


def go_to_room_photo_page(context, page, room_name):
    """Step1~Step3-options까지 진행해서 방 사진 업로드 페이지에 도달"""
    page.goto(f"{BASE_URL}/properties/new")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    page.get_by_text("쉐어하우스", exact=False).first.click()
    page.wait_for_timeout(400)
    page.get_by_text("성별 무관", exact=False).first.click()
    page.wait_for_timeout(400)
    click_next(page, "step1")

    fill_address_kakao(context, page)
    page.locator('input[placeholder*="상세 주소"]').first.fill("101호")
    page.wait_for_timeout(300)
    click_next(page, "step2")

    page.locator('button:has-text("방 추가")').first.wait_for(state="visible", timeout=5000)
    page.locator('button:has-text("방 추가")').first.click()
    page.wait_for_timeout(1000)
    page.locator('input[placeholder*="Room"]').first.fill(room_name)
    for inp in page.locator('input[placeholder*="KRW"]').all()[:2]:
        inp.fill("500"); page.wait_for_timeout(100)
    try:
        page.locator('input[placeholder*="청소비"]').first.fill("50")
    except Exception:
        pass
    page.wait_for_timeout(300)
    click_next(page, "방-정보")

    try:
        page.locator('input[placeholder="층"]').first.fill("1"); page.wait_for_timeout(200)
    except Exception:
        pass
    try:
        page.locator('input[placeholder*="m²"]').first.fill("10"); page.wait_for_timeout(200)
    except Exception:
        pass
    click_next(page, "space")

    try:
        page.get_by_text("Wi-Fi", exact=True).first.click(); page.wait_for_timeout(300)
    except Exception:
        pass
    click_next(page, "room-options")
    # 이제 방 사진 업로드 페이지


def complete_registration(page, prop_files, label):
    """
    방 사진 이후 단계 마무리.
    반환: (result, detail, ss_path)
      result: "registered" | "btn_disabled" | "error" | "upload_rejected"
    """
    # Step3 목록 → Step4
    try:
        click_next(page, "step3-list")
    except Exception as e:
        ss = os.path.join(SS_DIR, f"{label}_step3_blocked.png")
        page.screenshot(path=ss, full_page=True)
        return ("btn_disabled", f"step3→step4 차단: {e}", ss)

    click_next(page, "step4")  # 공용시설
    click_next(page, "step5")  # 규칙

    # Step6: 소개
    try:
        page.locator('input[placeholder*="쉐어하우스"]').first.fill(f"엣지케이스 테스트 {label}")
        page.wait_for_timeout(200)
    except Exception:
        pass
    try:
        page.locator('textarea').first.fill("엣지케이스 테스트용 숙소입니다.")
        page.wait_for_timeout(200)
    except Exception:
        pass
    click_next(page, "intro")

    # 숙소 사진 업로드
    page.wait_for_timeout(1000)
    ss_before = os.path.join(SS_DIR, f"{label}_prop_photo_before.png")
    page.screenshot(path=ss_before, full_page=True)

    file_input = page.locator('input[type="file"]').first
    file_input.wait_for(state="attached", timeout=5000)
    file_input.set_input_files(prop_files)
    page.wait_for_timeout(3000)

    ss_after = os.path.join(SS_DIR, f"{label}_prop_photo_after.png")
    page.screenshot(path=ss_after, full_page=True)

    done_btn = wait_btn_active(page, "등록 완료")
    if done_btn is None:
        # 버튼이 비활성 — 에러 메시지 수집
        err_msg = ""
        for sel in ['[role="alert"]', '[class*="toast"]', '[class*="error"]', 'p']:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=1000)
                t = el.inner_text().strip()[:80]
                if t:
                    err_msg = t
                    break
            except Exception:
                pass
        return ("btn_disabled", f"'등록 완료' 비활성 (msg={err_msg or '없음'})", ss_after)

    # 버튼 활성 — 클릭
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
    ss_final = os.path.join(SS_DIR, f"{label}_after_submit.png")
    page.screenshot(path=ss_final, full_page=True)

    if "complete" in url or ("/properties/" in url and "new" not in url):
        return ("registered", f"등록 완료 URL={url}", ss_final)

    err_msg = ""
    for sel in ['[role="alert"]', '[class*="toast"]', '[class*="error"]']:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=1500)
            err_msg = el.inner_text().strip()[:80]
            break
        except Exception:
            pass
    return ("upload_rejected", f"클릭 후 미완료 (URL={url.split('/')[-1]}, msg={err_msg or '없음'})", ss_final)


# ──────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────
results = {}  # label → (result, detail, ss_path)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # 호스트 로그인
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
    print("  완료\n")

    # ────────────────────────────────────────────────
    # 테스트 1: 사진 16장
    # ────────────────────────────────────────────────
    print("=" * 50)
    print("테스트 1: 사진 16장 업로드")
    print("=" * 50)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, storage_state=state_file)
    page = ctx.new_page()
    try:
        go_to_room_photo_page(ctx, page, "16장방")

        # 방 사진 16장 업로드
        file_input = page.locator('input[type="file"]').first
        file_input.wait_for(state="attached", timeout=5000)
        file_input.set_input_files(ALL_16)
        page.wait_for_timeout(3000)

        ss = os.path.join(SS_DIR, "16photo_room_after_upload.png")
        page.screenshot(path=ss, full_page=True)

        # 썸네일 개수 확인
        thumb_count = page.locator('img[src*="blob"], img[src*="objectURL"], [class*="thumb"], [class*="preview"]').count()
        print(f"  방 사진 16장 업로드 후 썸네일 수: {thumb_count}")

        # 에러 메시지 확인
        err_on_room = ""
        for sel in ['[role="alert"]', '[class*="toast"]', '[class*="error"]', 'p[class*="error"]']:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=1500)
                t = el.inner_text().strip()[:100]
                if t:
                    err_on_room = t
                    break
            except Exception:
                pass
        if err_on_room:
            print(f"  에러 메시지: {err_on_room!r}")

        add_btn = wait_btn_active(page, "추가하기")
        if add_btn is None:
            result = ("btn_disabled", f"16장 업로드 후 '추가하기' 비활성 (msg={err_on_room or '없음'})", ss)
            print(f"  '추가하기' 비활성")
        else:
            print(f"  '추가하기' 활성 → 클릭")
            add_btn.click()
            page.wait_for_timeout(2000)
            result = complete_registration(page, ALL_16, "16photo")

        results["16장"] = result
        print(f"  결과: {result[0]} — {result[1][:100]}")

    except Exception as e:
        ss = os.path.join(SS_DIR, "16photo_error.png")
        try:
            page.screenshot(path=ss, full_page=True)
        except Exception:
            ss = None
        results["16장"] = ("error", str(e)[:120], ss)
        print(f"  오류: {e}")
    finally:
        page.close()
        ctx.close()

    # ────────────────────────────────────────────────
    # 테스트 2: 비이미지 파일 각 타입별
    # ────────────────────────────────────────────────
    for ext, fake_path in FAKE_FILES.items():
        print(f"\n{'=' * 50}")
        print(f"테스트 2: 비이미지 파일 ({ext})")
        print(f"{'=' * 50}")
        label = f"fakefile_{ext.lstrip('.')}"

        ctx = browser.new_context(viewport={"width": 390, "height": 844}, storage_state=state_file)
        page = ctx.new_page()
        try:
            go_to_room_photo_page(ctx, page, f"비이미지{ext}방")

            # 방 사진 — 비이미지 파일 업로드 시도
            file_input = page.locator('input[type="file"]').first
            file_input.wait_for(state="attached", timeout=5000)

            # 브라우저 파일 input accept 속성 확인
            accept_attr = file_input.get_attribute("accept") or ""
            print(f"  input[accept]={accept_attr!r}")

            file_input.set_input_files(fake_path)
            page.wait_for_timeout(3000)

            ss = os.path.join(SS_DIR, f"{label}_after_upload.png")
            page.screenshot(path=ss, full_page=True)

            # 에러 메시지 확인
            err_msg = ""
            for sel in ['[role="alert"]', '[class*="toast"]', '[class*="error"]', 'p[class*="error"]']:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=1500)
                    t = el.inner_text().strip()[:100]
                    if t:
                        err_msg = t
                        break
                except Exception:
                    pass
            if err_msg:
                print(f"  업로드 후 에러 메시지: {err_msg!r}")

            add_btn = wait_btn_active(page, "추가하기")
            if add_btn is None:
                result = ("btn_disabled", f"{ext} 업로드 후 '추가하기' 비활성 (msg={err_msg or '없음'})", ss)
                print(f"  '추가하기' 비활성 — 업로드 차단됨")
            else:
                print(f"  '추가하기' 활성 → 클릭 (⚠️  비이미지 파일 허용됨)")
                add_btn.click()
                page.wait_for_timeout(2000)
                result = complete_registration(page, [fake_path], label)

            results[ext] = result
            print(f"  결과: {result[0]} — {result[1][:100]}")

        except Exception as e:
            ss = os.path.join(SS_DIR, f"{label}_error.png")
            try:
                page.screenshot(path=ss, full_page=True)
            except Exception:
                ss = None
            results[ext] = ("error", str(e)[:120], ss)
            print(f"  오류: {e}")
        finally:
            page.close()
            ctx.close()

    browser.close()
    try:
        os.unlink(state_file)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────
# 결과 요약 + QA 기록
# ──────────────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print("최종 결과 요약")
print(f"{'=' * 60}")

for label, (result, detail, ss_path) in results.items():
    icon = {"registered": "🚨", "btn_disabled": "✅", "upload_rejected": "✅", "error": "❌"}.get(result, "?")
    print(f"  [{label}] {icon} {result}: {detail[:80]}")

# QA Issues 기록
print("\n▶ QA Issues 기록...")

# 16장 결과
r16, d16, ss16 = results.get("16장", ("error", "", None))
if r16 == "registered":
    log_issue(
        state="호스트", screen="H-REG (숙소등록)", issue_type="플로우",
        description="사진 16장 업로드 시 등록 완료 — 최대 허용 장수(15장) 초과 등록 가능",
        severity="높음", screenshot_path=ss16,
    )
elif r16 == "btn_disabled":
    log_issue(
        state="호스트", screen="H-REG (숙소등록)", issue_type="UI",
        description=f"사진 16장 업로드 시 차단됨 — {d16[:80]}",
        severity="중간", screenshot_path=ss16,
    )
    print(f"  16장 차단 이슈 기록")
else:
    print(f"  16장 오류 (기록 없음): {d16[:60]}")

# 비이미지 파일 결과
for ext in FAKE_FILES:
    res, det, ss = results.get(ext, ("error", "", None))
    if res == "registered":
        log_issue(
            state="호스트", screen="H-REG (숙소등록)", issue_type="플로우",
            description=f"비이미지 파일({ext}) 업로드 후 숙소 등록 완료 — 파일 형식 검증 없음",
            severity="높음", screenshot_path=ss,
        )
        print(f"  {ext} 취약점 이슈 기록")
    elif res in ("btn_disabled", "upload_rejected"):
        print(f"  {ext} 정상 차단 (이슈 없음)")
    else:
        print(f"  {ext} 오류 (기록 없음): {det[:60]}")

print("\n완료")
