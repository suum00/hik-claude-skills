---
name: hik-qa-img
description: Use when comparing homesinkorea live URL screenshots with Figma designs for QA — detects layout differences and image distortion, records results in Google Sheet
---

# HIK QA Image Comparison

## Overview
라이브 URL과 Figma 디자인을 자동 비교해 QA 결과를 Google Sheet에 기록하는 워크플로.

## QA 확인 항목
1. **레이아웃/디자인 차이** — 라이브 full_page 캡처 vs Figma 전체 프레임 픽셀 비교, 차이 구간 크롭해서 Drive 업로드
2. **이미지 비율 오류 (찌그러짐)** — `<img>` 태그 + CSS `mask-image` SVG 아이콘 대상, 비율 차이 5% 초과 시 감지 (object-fit: cover/contain 제외, 소셜 미디어 SVG 제외)

## Rules
1. 외부 파일 공유/업로드 금지 — Google Drive, Git만 허용
2. Playwright 캡처 포맷: JPEG
3. Playwright 캡처: `full_page=True`, `wait_until='load'`
4. Drive 업로드: base64 변환 금지 — `MediaFileUpload` 스트리밍 방식 사용
5. 동작 전 반드시 규칙 1–4 확인 후 실행

## 재검수 규칙
같은 화면을 다시 QA할 때 기존 시트 내용을 덮어쓰거나 삭제하지 않는다.

- **중복 판단 기준**: `screen_id` + `E열(차이점)` 텍스트가 모두 동일한 행이 이미 존재하면 추가하지 않는다
- **새로운 이슈**: 기존에 없는 차이점이면 행 추가
- **이미 있는 이슈**: 그대로 유지, 아무것도 하지 않음

```python
def is_duplicate(ws, screen_id, diff_text):
    rows = ws.get_all_values()
    for row in rows[1:]:  # 헤더 제외
        if len(row) >= 5 and row[0] == screen_id and row[4] == diff_text:
            return True
    return False

# 시트 기록 전 중복 체크
for issue in issue_defs:
    if not is_duplicate(ws, screen_id, issue['diff']):
        # 새 행 추가
    # else: 스킵
```

## Key Config
| 항목 | 값 |
|------|-----|
| Figma file key | `7DEB0l3BEOeJWLwbkpxgir` |
| FIGMA_TOKEN | `~/.zshrc`의 `$FIGMA_TOKEN` |
| QA Sheet ID | `1GimM2Q9QCicwrePMpWzNRKx6ooSChEIfAzNSQ4FYNe0` |
| Drive folder ID | `1zoYjur3ZKxcGKy0z2FdZbWSnF5-WoTgF` ("HIK QA Screenshots") |
| Screen ID Sheet | `1slpPeuWhxFc4OVd_GzQ8x0hks2jd_5KcNQU9gsI1WXk` |
| Service account key | `/Users/sujin/Desktop/dev/swift-implement-498523-i1-5c79643ce521.json` |
| OAuth client | `/Users/sujin/Desktop/dev/client_secret_51575743124-hhvdq3qpo1bi9nca3r2g60d4tg9tcbrt.apps.googleusercontent.com.json` |
| OAuth token (cached) | `/Users/sujin/Desktop/dev/drive_token.pkl` |

## 라이브 사이트 URL 및 계정
**Base URL:** `https://homesinkorea-git-develop-homesinkorea.vercel.app`

| 역할 | 진입 URL | ID | PW |
|------|---------|----|----|
| 게스트 | `/login` | guesttest01@gmail.com | Guestpass1234! |
| 호스트 | `/login/host?next=%2Fhost` | hostuser01@gmail.com | Hostpass1234! |
| 관리자 | `/login` 로그인 후 `/admin/payments` 입력 | admintest01@gmail.com | Adminpass1234! |

## QA 시트 탭 선택 기준
| 화면 ID 접두사 | 시트 탭 |
|-------------|--------|
| G- | 게스트 |
| H- | 호스트 |
| A- | 관리자 |
| C-COMM- | 비로그인 |

## Sheet Columns (A–J)
A: 화면 ID / B: 화면 설명 / C: URL 이미지 / D: 피그마 이미지 / E: 차이점 / F: 요청사항 / G: 수정완료 / H: 확인완 / I: 반려 / J: 반려사유

## Workflow

### Step 1 — 화면 ID → Figma node ID 조회
Screen ID 시트에서 화면 ID로 Figma node ID 확인.

**역할별 홈 화면 (Screen ID 명명 규칙상 H-HOME이 없으므로 주의)**
| 역할 | 홈 화면 ID | Figma node ID | 라이브 URL |
|------|-----------|--------------|-----------|
| 게스트 | G-HOME.base | `2976:10609` | `https://homesinkor.com/` |
| 호스트 | H-CONT.pending | `4719:12978` | `https://homesinkor.com/host` (로그인 필요) |
| 관리자 | A-BOOK.base | `5465:38228` | 별도 확인 필요 |

**Figma node ID 조회 방법** (위 표에 없는 화면):
```bash
source ~/.zshrc
# 1. 완료페이지 섹션 ID 확인
# - 게스트: 4916:15764 / 호스트: 4916:15763 / 관리자+기타: 4916:15765
# 2. 해당 섹션 children에서 화면 ID로 검색
curl -s "https://api.figma.com/v1/files/7DEB0l3BEOeJWLwbkpxgir/nodes?ids={SECTION_ID}" \
  -H "X-Figma-Token: $FIGMA_TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
doc = list(d['nodes'].values())[0]['document']
for c in doc.get('children', []):
    if c['name'] == '{SCREEN_ID}':
        print(c['id'])
"
```

### Step 2 — 캡처 (Playwright + Figma 동시 실행)
Playwright 로딩 중 Figma 다운로드를 백그라운드 스레드로 병렬 실행해 대기 시간을 줄인다.

```python
import os, threading, requests
from playwright.sync_api import sync_playwright

FILE_KEY = '7DEB0l3BEOeJWLwbkpxgir'
FIGMA_TOKEN = os.popen('source ~/.zshrc 2>/dev/null && echo $FIGMA_TOKEN').read().strip()

figma_error = [None]
def download_figma(node_id):
    # requests 사용 — urllib은 macOS Python 3.14에서 SSL 인증서 오류 발생
    try:
        node_enc = node_id.replace(':', '%3A')
        resp = requests.get(
            f'https://api.figma.com/v1/images/{FILE_KEY}?ids={node_enc}&format=jpg&scale=1',
            headers={'X-Figma-Token': FIGMA_TOKEN}, timeout=30)
        img_url = resp.json()['images'][node_id]
        with open('/tmp/figma.jpg', 'wb') as f:
            f.write(requests.get(img_url, timeout=30).content)
    except Exception as e:
        figma_error[0] = e

# Figma 다운로드를 백그라운드 스레드로 시작
figma_thread = threading.Thread(target=download_figma, args=(node_id,))
figma_thread.start()

with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        page.goto(url, wait_until='load', timeout=30000)
        # load 이벤트 후 이미지 로딩 완료 대기 (최대 1초)
        page.wait_for_timeout(1000)

        # 이미지 비율 체크 ①: <img> 태그 — 소셜 미디어 SVG 제외
        distortion_issues = page.evaluate("""() => {
            const SOCIAL_KEYWORDS = ['insta', 'instagram', 'tiktok', 'tik_tok', 'facebook', 'fb', 'twitter', 'youtube', 'linkedin', 'whatsapp', 'kakaotalk'];
            return Array.from(document.querySelectorAll('img')).map(img => {
                const src = img.src.split('/').pop().split('?')[0].toLowerCase();
                if (src.endsWith('.svg') && SOCIAL_KEYWORDS.some(k => src.includes(k))) return null;
                const rect = img.getBoundingClientRect();
                const style = window.getComputedStyle(img);
                if (style.objectFit === 'cover' || style.objectFit === 'contain') return null;
                const nW = img.naturalWidth, nH = img.naturalHeight;
                const rW = rect.width, rH = rect.height;
                if (!nW || !nH || !rW || !rH) return null;
                const diff = Math.abs((nW/nH) - (rW/rH)) / (nW/nH);
                if (diff > 0.05) return {
                    src: src,
                    issue: `비율 오류 (원본 ${nW}x${nH} → 렌더링 ${Math.round(rW)}x${Math.round(rH)})`,
                    top: rect.top, bottom: rect.bottom
                };
                return null;
            }).filter(Boolean);
        }""")

        # 이미지 비율 체크 ②: CSS mask-image SVG 아이콘 (nav bar 등) — img 태그로 감지 불가
        # preserveAspectRatio="none" + 비정방형 viewBox → 정방형 컨테이너에서 찌그러짐
        # top/left/bottom/right 위치 정보도 함께 수집 — 나중에 크롭에 사용
        mask_srcs = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('span[style*="mask-image"], div[style*="mask-image"]'))
                .map(el => {
                    const style = el.getAttribute('style') || '';
                    const m = style.match(/mask-image:\s*url\(["']?([^"')]+\.svg[^"')]*?)["']?\)/i);
                    if (!m) return null;
                    const rect = el.getBoundingClientRect();
                    return { src: m[1], rW: Math.round(rect.width), rH: Math.round(rect.height),
                             top: Math.round(rect.top), left: Math.round(rect.left),
                             bottom: Math.round(rect.bottom), right: Math.round(rect.right) };
                }).filter(Boolean);
        }""")

        import re as _re
        BASE_URL = 'https://homesinkorea-git-develop-homesinkorea.vercel.app'
        mask_issues = []  # 위치 정보 포함해서 따로 보관
        seen_mask = set()
        for item in mask_srcs:
            key = item['src'].split('/')[-1].split('?')[0]
            if key in seen_mask: continue
            seen_mask.add(key)
            full_url = BASE_URL + item['src'] if item['src'].startswith('/') else item['src']
            try:
                svg_text = requests.get(full_url, timeout=10).text
                vb = _re.search(r'viewBox=["\']0 0 ([\d.]+) ([\d.]+)["\']', svg_text)
                if not vb: continue
                vbW, vbH = float(vb.group(1)), float(vb.group(2))
                rW, rH = item['rW'], item['rH']
                if rW == 0 or rH == 0: continue
                diff = abs((vbW/vbH) - (rW/rH)) / (vbW/vbH)
                if diff > 0.05:
                    distortion_issues.append({
                        'src': key,
                        'issue': f'비율 오류 (viewBox {vbW:.0f}×{vbH:.0f} → 렌더링 {rW}×{rH})',
                        'top': item['top'], 'bottom': item['bottom']
                    })
                    mask_issues.append({**item, 'key': key,
                                        'vbW': vbW, 'vbH': vbH, 'diff': diff})
            except Exception:
                pass

        # fixed 요소 숨기기 전에 뷰포트 스크린샷 먼저 촬영 — distortion 아이콘 크롭용
        page.screenshot(path='/tmp/viewport.jpg', type='jpeg', quality=85, full_page=False)

        # fixed/sticky 숨김 후 full_page 캡처
        page.evaluate("""() => {
            document.querySelectorAll('*').forEach(el => {
                const pos = window.getComputedStyle(el).position;
                if (pos === 'fixed' || pos === 'sticky') {
                    el.setAttribute('data-qa-hidden', el.style.visibility || '');
                    el.style.setProperty('visibility', 'hidden', 'important');
                }
            });
        }""")
        page.screenshot(path='/tmp/live.jpg', type='jpeg', quality=85, full_page=True)
        page.evaluate("""() => {
            document.querySelectorAll('[data-qa-hidden]').forEach(el => {
                el.style.visibility = el.getAttribute('data-qa-hidden');
                el.removeAttribute('data-qa-hidden');
            });
        }""")
        browser.close()

figma_thread.join()
if figma_error[0]:
    raise figma_error[0]
```

### Step 3 — 픽셀 비교 및 구간 크롭
```python
from PIL import Image, ImageChops

live = Image.open('/tmp/live.jpg').convert('RGB')
figma = Image.open('/tmp/figma.jpg').convert('RGB')

min_h = min(live.size[1], figma.size[1])
live_r = live.crop((0, 0, 390, min_h))
figma_r = figma.crop((0, 0, 390, min_h))

diff = ImageChops.difference(live_r, figma_r)

band_size = 50
scores = []
for i in range(0, min_h, band_size):
    band = diff.crop((0, i, 390, min(i+band_size, min_h)))
    score = sum(sum(p) for p in band.get_flattened_data())
    scores.append((i, score))

max_score = max(s for _, s in scores)
threshold = max_score * 0.3  # 최대값의 30% 이상 구간만 포함

# 인접 밴드 병합 (80px 이내) — 동일 컴포넌트 내 연속 밴드만 병합, 떨어진 섹션은 별도 행으로 분리
hot_bands = sorted([y for y, s in scores if s >= threshold])
regions = []
for y in hot_bands:
    if regions and y - regions[-1][1] <= 80:
        regions[-1] = (regions[-1][0], y + band_size)
    else:
        regions.append((y, y + band_size))

# fixed 탭바 오탐 필터 후 구간 크롭
# - 뷰포트 하단 근처(y=764~894): full_page 캡처 시 fixed 탭바가 찍히는 위치
# - 라이브 페이지 최하단 200px: Figma 프레임 최하단 고정 탭바 vs 라이브 empty 오탐
VIEWPORT_H = 844
crops = []
for idx, (r_start, r_end) in enumerate(regions):
    is_fixed_nav = (r_start >= VIEWPORT_H - 80 and r_end <= VIEWPORT_H + 50) or (r_start >= min_h - 200)
    if is_fixed_nav:
        continue
    crop_start = max(0, r_start - 100)
    crop_end = min(min_h, r_end + 100)
    live_path = f'/tmp/diff_live_{idx}.jpg'
    figma_path = f'/tmp/diff_figma_{idx}.jpg'
    live_r.crop((0, crop_start, 390, crop_end)).save(live_path, 'JPEG', quality=85)
    figma_r.crop((0, crop_start, 390, crop_end)).save(figma_path, 'JPEG', quality=85)
    crops.append({'live': live_path, 'figma': figma_path, 'y': f'{crop_start}~{crop_end}'})
```

### Step 4 — 사이드바이사이드 이미지 생성 후 차이점 작성
live/figma 이미지를 좌우로 합쳐 한 이미지로 만들어 Read 툴로 한 번에 보고 차이점 작성.
```python
from PIL import Image

def make_side_by_side(live_path, figma_path, out_path):
    l = Image.open(live_path).convert('RGB')
    f = Image.open(figma_path).convert('RGB')
    h = max(l.size[1], f.size[1])
    combined = Image.new('RGB', (l.size[0] + f.size[0] + 4, h), (200, 200, 200))
    combined.paste(l, (0, 0))
    combined.paste(f, (l.size[0] + 4, 0))
    combined.save(out_path, 'JPEG', quality=85)

for idx, c in enumerate(crops):
    make_side_by_side(c['live'], c['figma'], f'/tmp/side_{idx}.jpg')
    # Read 툴로 /tmp/side_{idx}.jpg 읽어 차이점 기술
    # c['diff_summary'] = "..."  # 좌: 라이브, 우: 피그마 기준으로 작성
    # c['request_text'] = "..."
```
- 좌측: 라이브, 우측: 피그마
- 차이점: 보이는 내용 구체적으로 기술 (예: "회사명 한글 표기 vs 영문 표기")
- 요청사항: 피그마 기준으로 수정 요청 작성

### Step 5 — Drive 스트리밍 업로드 (병렬)
```python
import pickle, os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

TOKEN_PATH = '/Users/sujin/Desktop/dev/drive_token.pkl'
FOLDER_ID = '1zoYjur3ZKxcGKy0z2FdZbWSnF5-WoTgF'

with open(TOKEN_PATH, 'rb') as f:
    creds = pickle.load(f)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(TOKEN_PATH, 'wb') as f:
        pickle.dump(creds, f)

# httplib2는 스레드 비안전 → upload() 내부에서 서비스를 매번 새로 생성
def upload(name, path):
    svc = build('drive', 'v3', credentials=creds)
    media = MediaFileUpload(path, mimetype='image/jpeg', resumable=True)
    f = svc.files().create(
        body={'name': name, 'parents': [FOLDER_ID]},
        media_body=media, fields='id',
        supportsAllDrives=True).execute()
    svc.permissions().create(fileId=f['id'], body={'role':'reader','type':'anyone'},
        supportsAllDrives=True).execute()
    return f['id']

# distortion 아이콘 크롭 — viewport.jpg에서 잘라내기 (Playwright 재실행 불필요)
from PIL import Image as _PIL_Image
viewport_img = _PIL_Image.open('/tmp/viewport.jpg')
dist_crops = []
for g_idx, mi in enumerate(mask_issues):
    pad = 10
    box = (max(0, mi['left'] - pad), max(0, mi['top'] - pad),
           min(390, mi['right'] + pad), min(844, mi['bottom'] + pad))
    crop = viewport_img.crop(box)
    # 5배 확대해서 저장 — 작은 아이콘도 육안으로 확인 가능
    w, h = crop.size
    crop.resize((w * 5, h * 5), _PIL_Image.NEAREST).save(
        f'/tmp/dist_crop_{g_idx}.jpg', 'JPEG', quality=95)
    dist_crops.append({'live': f'/tmp/dist_crop_{g_idx}.jpg',
                       'figma': f'/tmp/dist_crop_{g_idx}.jpg',
                       'key': mi['key'],
                       'issue': mi['issue'] if 'issue' in mi else
                                f'비율 오류 (viewBox {mi["vbW"]:.0f}×{mi["vbH"]:.0f} → 렌더링 {mi["rW"]}×{mi["rH"]})'})

# 픽셀 diff 이슈 크롭 + distortion 크롭을 한번에 병렬 업로드 (max_workers=4)
# httplib2가 스레드 비안전이므로 upload() 내부에서 서비스를 새로 생성해야 한다
from concurrent.futures import ThreadPoolExecutor

upload_tasks = {}
for c in issue_crops:  # 이슈로 판단된 크롭만 업로드
    upload_tasks[f'c{c["idx"]}_live']  = (f'{screen_id}_live_c{c["idx"]}.jpg',  c['live'])
    upload_tasks[f'c{c["idx"]}_figma'] = (f'{screen_id}_figma_c{c["idx"]}.jpg', c['figma'])
for g_idx, dc in enumerate(dist_crops):
    upload_tasks[f'd{g_idx}_live']  = (f'{screen_id}_dist_live_{g_idx+1}.jpg',  dc['live'])
    upload_tasks[f'd{g_idx}_figma'] = (f'{screen_id}_dist_figma_{g_idx+1}.jpg', dc['figma'])

with ThreadPoolExecutor(max_workers=4) as ex:
    futs = {k: ex.submit(upload, name, path) for k, (name, path) in upload_tasks.items()}
    upload_ids = {k: fut.result() for k, fut in futs.items()}
```

### Step 6 — Sheet에 결과 기록 (구간별 + 이미지 비율 오류)
```python
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_FILE = '/Users/sujin/Desktop/dev/swift-implement-498523-i1-5c79643ce521.json'
creds_sa = service_account.Credentials.from_service_account_file(
    SA_FILE, scopes=['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(creds_sa)
ws = gc.open_by_key('1GimM2Q9QCicwrePMpWzNRKx6ooSChEIfAzNSQ4FYNe0').get_worksheet(0)
sheets_service = build('sheets', 'v4', credentials=creds_sa)

def img_formula(file_id):
    view = f'https://drive.google.com/file/d/{file_id}/view'
    img  = f'https://drive.google.com/uc?export=view&id={file_id}'
    return f'=HYPERLINK("{view}",IMAGE("{img}"))'

# 재검수 중복 체크 — screen_id + E열(차이점)이 동일한 행은 추가하지 않음
existing_rows = ws.get_all_values()
def is_duplicate(sid, diff_text):
    for row in existing_rows[1:]:
        if len(row) >= 5 and row[0] == sid and row[4] == diff_text:
            return True
    return False

new_issues = [iss for iss in issue_defs if not is_duplicate(screen_id, iss['diff'])]
# issue_defs는 픽셀 diff 이슈 + distortion 이슈 + nav_crop 이슈를 모두 포함한 리스트

if not new_issues:
    print("새로운 이슈 없음 — 시트 변경 없이 종료")
else:
    start_row = len(ws.col_values(1)) + 1
    cell_data, row_reqs = [], []

    for idx, iss in enumerate(new_issues):
        row = start_row + idx
        cell_data.extend([
            {'range': f'A{row}', 'values': [[iss['screen_id']]]},
            {'range': f'B{row}', 'values': [[screen_desc]]},
            {'range': f'C{row}', 'values': [[img_formula(iss['live_id'])]]},
            {'range': f'D{row}', 'values': [[img_formula(iss['figma_id'])]]},
            {'range': f'E{row}', 'values': [[iss['diff']]]},
            {'range': f'F{row}', 'values': [[iss['request']]]},
        ])
        row_reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': ws.id, 'dimension': 'ROWS', 'startIndex': row-1, 'endIndex': row},
            'properties': {'pixelSize': 200}, 'fields': 'pixelSize'
        }})

    # USER_ENTERED 모드로 기록 — RAW 모드에서는 =IMAGE() 수식이 문자열로 저장됨
    # 범위에 반드시 탭명 prefix 필요 — 없으면 첫 번째 탭(비로그인)에 기록됨
    # 예: "'게스트'!A7" (작은따옴표 포함)
    sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId='1GimM2Q9QCicwrePMpWzNRKx6ooSChEIfAzNSQ4FYNe0',
        body={'valueInputOption': 'USER_ENTERED', 'data': cell_data}
    ).execute()
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId='1GimM2Q9QCicwrePMpWzNRKx6ooSChEIfAzNSQ4FYNe0',
        body={'requests': row_reqs}
    ).execute()
    print(f"{len(new_issues)}개 새 이슈 기록 완료")
```

## 시트 기록 기준
- 차이점이 있을 때만 시트에 행 기록, 차이점이 없으면 기록하지 않음 (정상 확인 마커도 기록 안 함)
- 픽셀 diff 구간과 이미지 비율 오류는 별도 행으로 기록
- B열 화면 설명: 단순 화면명만 ("게스트 홈 화면"). 순번·최초·기본 등 수식어 넣지 않음

## 카드/리스트 영역 diff 판단 기준
카드·리스트 컴포넌트는 실제 데이터(이미지, 텍스트)가 피그마 목업과 다를 수 있다. Step 4(이미지 직접 비교) 시 아래 기준으로 판단:

| 케이스 | 판단 | 처리 |
|--------|------|------|
| 카드 높이/너비, 패딩, 요소 배치 순서가 다름 | 레이아웃 버그 | 차이점 기록, 요청사항 작성 |
| 카드 구조는 동일, 썸네일 이미지·제목·가격 등 콘텐츠만 다름 | 동적 데이터 차이 | 이슈 아님, 기록하지 않음 |

**판단 방법:** 피그마 카드 1장과 라이브 카드 1장을 비교해 컨테이너 크기, 내부 요소 위치가 일치하면 → 동적 데이터 처리. 구조 자체가 다르면 → 레이아웃 버그로 기록.

## 알려진 한계 — fixed 요소 위치 차이
`full_page=True` 캡처 시 `position: fixed` 요소(하단 탭바 등)는 스크롤 전체 높이가 아닌 **뷰포트 기준 위치**에 한 번만 렌더링된다. 피그마 프레임은 단일 뷰포트 기준이므로 탭바 위치가 달라 보일 수 있으나 실제 동작 버그가 아님. 픽셀 비교 시 fixed 요소로 인한 diff는 이슈로 기록하지 않는다.

## 알려진 한계 — 상단 헤더 누락 오탐
캡처 전 모든 `position: fixed/sticky` 요소를 숨기기 때문에 **상단 헤더(로고, 알림 아이콘, 언어 선택 등)가 fixed/sticky인 경우 라이브 스크린샷에서 보이지 않는다.** 피그마 프레임에는 헤더가 그려져 있으므로 상단 구간(y=0~100px)에서 헤더 요소 누락처럼 보이는 diff가 발생할 수 있다.

**이 diff는 실제 버그가 아니다.** Step 4에서 상단 헤더가 라이브에서 보이지 않는 diff가 나오면, fixed/sticky 숨김으로 인한 오탐으로 판단하고 이슈로 기록하지 않는다.

## 요청사항 작성 기준
- 짧고 명확하게 — 무엇을 수정해야 하는지 한 줄로
- 예: "아이콘 비율에 맞게 수정 필요", "영문 표기로 수정 필요", "다운로드 아이콘으로 교체 필요"
- 피그마 디자인 기준이라는 설명 불필요 (당연한 전제이므로 생략)
