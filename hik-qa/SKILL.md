---
name: hik-qa
description: Use when doing QA on HomeSinKorea web service — checking UI matches Figma, flows match the flow document, back navigation, and popup/bottom sheet behavior across non-logged-in, guest, host, and admin states
---

# HIK Web Service QA

## 보안 규칙 (절대 준수)

> **외부 사이트에 문서·이미지 업로드 절대 금지**
> catbox.moe, imgur, pastebin 등 외부 호스팅 서비스에 스크린샷·문서를 업로드하면 안 된다.
> 스크린샷은 로컬 경로로만 관리하거나, 사내 저장소(Supabase 등)만 사용한다.

## Overview
Playwright 기반 QA 스킬. 6가지 규칙을 4개 상태별로 순차 검증하고, 이슈를 Google Sheet에 기록한다.

## 고정 설정값

| 항목 | 값 |
|------|-----|
| 서비스 URL | https://homesinkorea-git-develop-homesinkorea.vercel.app |
| Figma 파일키 | 7DEB0l3BEOeJWLwbkpxgir |
| Google Sheet ID | 1-n6YwMjppwANQRiT3qIytOzRt-pUvoIushUzgT4sef8 |
| 서비스 계정 키 | 환경변수 `$HIK_SA_KEY` (아래 설정 참고) |

## 팀원 초기 설정 (최초 1회)

1. Google Cloud Console에서 서비스 계정 키 JSON 발급
2. `~/.zshrc` (또는 `~/.bashrc`)에 추가:
   ```bash
   export HIK_SA_KEY="$HOME/Downloads/본인키파일이름.json"
   ```
3. 터미널 재시작 또는 `source ~/.zshrc` 실행

## 테스트 계정

| 상태 | ID | PW | 진입 |
|------|----|----|------|
| 게스트 | guesttest01@gmail.com | Guestpass1234! | /login |
| 호스트 | hostuser01@gmail.com | Hostpass1234! | /login/host?next=%2Fhost |
| 관리자 | admintest01@gmail.com | Adminpass1234! | /login → /admin/payments |

## QA 시작 전 필수 입력

- **플로우 문서**: 화면명, 버튼, 이동 대상, 팝업/바텀시트 매핑이 정의된 문서
- 문서가 없으면 규칙 2 (플로우 검증)를 진행할 수 없으므로 반드시 먼저 받아야 한다

## 6가지 QA 규칙

### 규칙 1. 버튼 UI — Figma 이미지와 동일한지
- Figma MCP(`get_screenshot`, `get_design_context`)로 해당 화면 디자인 가져오기
- Playwright로 실제 화면 스크린샷 촬영
- 버튼 텍스트, 색상, 위치, 아이콘을 육안 비교
- **양방향 검증 필수**:
  - Figma에 있는데 실제에 없는 요소 → 이슈 기록
  - 실제에 있는데 Figma에 없는 요소 → 이슈 기록
- 차이가 있으면 이슈로 기록

### 규칙 2. 플로우 — 문서와 동일하게 흘러가는지
- 플로우 문서의 각 단계: `화면 → 버튼 클릭 → 이동 대상` 순서대로 Playwright로 실행
- 이동한 URL/화면이 문서와 다르거나 404면 이슈로 기록

### 규칙 3. 뒤로가기 — 직전 화면으로 이동하는지
- Playwright로 A화면 → B화면 이동 후 `page.go_back()` 실행
- 돌아온 URL이 A화면인지 확인
- 인앱 뒤로가기 버튼(← 아이콘)이 있으면 클릭해서도 확인

### 규칙 4. 팝업/바텀시트 — 올바른 것이 열리고 정상 닫히는지
- 플로우 문서의 `버튼 → 팝업/바텀시트` 매핑대로 Playwright로 트리거
- 열린 팝업/바텀시트의 제목/내용이 문서와 일치하는지 확인
- X버튼, 배경 탭, 닫기 버튼으로 각각 닫기 테스트
- 닫힌 후 원래 화면으로 돌아왔는지 확인

### 규칙 5. 미설계 요소 — 실제 화면에 Figma에 없는 요소가 있는지
- Figma 디자인 기준으로 각 화면의 전체 요소 목록 확인
- 실제 화면에서 Figma에 없는 버튼, 메뉴, 텍스트, 링크가 있으면 이슈로 기록
- 규칙 1과 함께 실행 (UI 검증 단계에서 역방향도 동시에 확인)

### 규칙 6. 수동 확인 필요 — 데이터 부족으로 자동 검증 불가한 경우
- 테스트 데이터가 없어 자동 검증이 불가능한 케이스는 건너뛰지 않고 반드시 기록
- 심각도를 `확인필요`로 설정
- Google Sheet 해당 행을 **노란색 배경**으로 표시
- 예: 알림 없어서 알림 있을 때 화면 검증 불가, 예약 내역 없어서 예약 목록 화면 검증 불가
- **테스트 데이터 생성 후 해당 케이스를 검증하면 `확인필요` 행을 삭제하고 실제 결과로 대체**
  - 문제 없음 → 행 삭제
  - 문제 있음 → 행을 삭제하고 정식 이슈(심각도: 높음/중간)로 새로 기록

```python
def log_manual_check(state, screen, issue_type, description):
    # 심각도: 확인필요, 행 배경: 노란색(#FFF9C4)
    log_issue(state, screen, issue_type, description,
              severity='확인필요', highlight_yellow=True)
```

## 핵심 플로우 반복 검증 (문서 독립)

아래 4개 플로우는 플로우 문서와 별개로 **매 QA마다 10회 반복 실행**하여 안정성을 검증한다.

| 플로우 | 진입 | 성공 기준 |
|--------|------|-----------|
| 로그인 | `/login` → 이메일/비밀번호 입력 → 제출 | `/login` 벗어나 홈으로 이동 |
| 회원가입 | `/signup` 또는 회원가입 버튼 → 정보 입력 → 제출 | 가입 완료 후 홈 또는 온보딩 화면 이동 |
| 이용문의 | 숙소 상세 → Chat 버튼 → `/inquiry/:id` | 메시지 전송 성공 팝업 노출 |
| 숙소등록 | 호스트 대시보드 → 숙소 등록 | 등록 완료 후 목록에 노출 |
| 방 등록 | 숙소 관리 → 방 추가 | 방 정보 저장 후 목록에 노출 |
| 채팅 | `/messages` → 채팅방 진입 → 메시지 전송 | 전송 메시지가 상대방 채팅방에 노출 |
| 숙소 예약 | 숙소 상세 → 예약 요청 버튼 클릭 | 호스트에게 승인 요청 전송 완료 팝업 노출 |

## 반복테스트 트리거

- **"반복테스트 시작"** 또는 **"반복테스트 N회 해줘"** 라고 해야 실행 (QA 시작과 별개)
- 횟수를 지정하지 않으면 기본 10회로 동작
- QA 시작 시에는 반복테스트를 자동 실행하지 않음

| 입력 예시 | 동작 |
|-----------|------|
| `반복테스트 시작` | 7개 플로우 각 10회 |
| `반복테스트 5회 해줘` | 7개 플로우 각 5회 |
| `이용문의 반복테스트 3회 해줘` | 이용문의만 3회 |

## 반복테스트 결과 기록 — Google Sheet "반복테스트" 탭

QA Issues 탭과 별도로 **"반복테스트"** 탭에 기록한다.

| 컬럼 | 내용 |
|------|------|
| 번호 | 자동 순번 |
| 플로우 | 로그인 / 회원가입 / 이용문의 / 숙소등록 / 방 등록 / 채팅 / 숙소 예약 |
| 테스트 횟수 | 실행한 총 횟수 |
| 실패 횟수 | 실패한 횟수 |
| 성공률 | `(성공/전체) × 100%` |
| 실패 회차 | 실패한 회차 번호 (예: 3, 7) |
| 마지막 실패 원인 | 에러 메시지 앞 100자 |
| 확인일시 | 자동 기록 |
| 스크린샷 | 첫 번째 실패 회차 스크린샷 IMAGE() 삽입 |

- 전체 성공(100%) → 해당 행 **연한 초록색 배경** + 확인일시 기록
- 1회라도 실패 → 해당 행 **연한 빨간색 배경** + 실패 원인·스크린샷 기록
- 같은 플로우를 당일 재실행하면 해당 행을 덮어씀 (중복 방지)
- `repeat_flow_test(page, flow_name, test_fn, repeat)` 함수가 실행 및 기록을 담당

## QA 시작 트리거

사용자가 **"QA 시작"** 이라고 하면 아래 순서로 동작한다:

### 1단계 — 파트 확인 (필수)

먼저 사용자에게 어떤 상태를 QA할지 묻는다:

```
어떤 파트를 QA할까요?
1. 비로그인
2. 게스트
3. 호스트
4. 관리자
5. 전체 (1→2→3→4 순서)

번호 또는 이름으로 알려주세요. (예: "2", "게스트", "2,3", "전체")
```

- 복수 선택 가능 (예: "게스트, 호스트")
- 답변을 받기 전에는 플로우 문서 읽기나 QA 실행을 시작하지 않는다

### 2단계 — 플로우 문서 읽기 (파트별)

선택한 파트별로 플로우 문서를 분리해서 읽는다.

**플로우 문서 탭 매핑**

| 상태 | 플로우 문서 탭 | QA Issues 탭 |
|------|--------------|-------------|
| 비로그인 | 비로그인 | QA Issues (비로그인) |
| 게스트 | 게스트 | QA Issues (게스트) |
| 호스트 | 호스트 | QA Issues (호스트) |
| 관리자 | 관리자 | QA Issues (관리자) |

**각 파트별 처리 순서**

1. 해당 상태의 플로우 문서 탭만 읽기 (Sheet ID: `1m9PqwYK9-nT35-2Nv3spQAgsJybneWn81yMfBTkHAKc`)
2. 5개 컬럼(출발 화면 ID / 출발 화면 이름 / 트리거 / 동작 유형 / 도착 화면 ID)이 모두 채워진 행만 QA 대상으로 선정
3. 해당 상태의 QA Issues 탭 기존 결과와 비교 — 변경된 행 재QA, 새 행 신규 QA

> 플로우 문서에 해당 상태 탭이 없으면 사용자에게 알리고 건너뜀.

### 3단계 — QA 실행

선택한 파트만 실행한다. 복수 선택 시 선택 순서대로 진행.

```
예) 게스트 선택
  → 플로우 문서 "게스트" 탭 읽기
  → QA Issues (게스트) 탭에 기록

예) 게스트 + 호스트 선택
  → 플로우 문서 "게스트" 탭 읽기 → 게스트 QA 완료
  → 플로우 문서 "호스트" 탭 읽기 → 호스트 QA 진행
```

각 상태 완료 후 이슈 목록 중간 정리 후 다음 상태로 넘어간다.

## 중복 이슈 방지

Google Sheet에 이슈를 추가하기 전에 **상태 + 화면명 + 이슈유형 + 설명**이 모두 동일한 행이 이미 존재하면 추가하지 않는다.

## 이슈 기록 형식 (Google Sheet)

| 컬럼 | 내용 예시 |
|------|----------|
| 번호 | 자동 순번 |
| 상태 | 비로그인 / 게스트 / 호스트 / 관리자 |
| 화면명 | 홈, 매물상세, 예약확인 등 |
| 이슈유형 | UI / 플로우 / 뒤로가기 / 팝업·바텀시트 |
| 설명 | 예약하기 버튼 클릭 시 404 발생 |
| 심각도 | 높음 / 중간 / 확인필요 |
| 확인일시 | 자동 기록 |
| 스크린샷 | Google Drive 업로드 후 IMAGE() 함수로 삽입 (drive_upload.py 사용) |

## 이슈 심각도 기준

| 심각도 | 기준 |
|--------|------|
| 높음 | 화면 이동 불가, 404, 크래시, 팝업 미노출 |
| 중간 | 잘못된 화면으로 이동, 뒤로가기 오작동, 팝업 미닫힘 |

## Google Sheet 탭 구조

상태별로 탭이 분리되어 있어 팀원이 동시에 QA를 실행해도 충돌이 없다.

| 탭 이름 | 대상 상태 |
|---------|----------|
| QA Issues (비로그인) | 비로그인 |
| QA Issues (게스트) | 게스트 |
| QA Issues (호스트) | 호스트 |
| QA Issues (관리자) | 관리자 |
| 반복테스트 | 핵심 플로우 반복 검증 |

## Google Sheet 기록 코드 패턴

```python
import os
import sys
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

sys.path.insert(0, os.path.expanduser('~/.claude/skills/hik-qa'))
from drive_upload import upload_screenshot, apply_screenshot_to_sheet

KEY_FILE = os.environ['HIK_SA_KEY']
SHEET_ID = '1-n6YwMjppwANQRiT3qIytOzRt-pUvoIushUzgT4sef8'

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
sheets_service = build('sheets', 'v4', credentials=creds)

STATE_TAB = {
    '비로그인': 'QA Issues (비로그인)',
    '게스트':   'QA Issues (게스트)',
    '호스트':   'QA Issues (호스트)',
    '관리자':   'QA Issues (관리자)',
}

def get_ws(state):
    return sh.worksheet(STATE_TAB.get(state, 'QA Issues'))

def log_issue(state, screen, issue_type, description, severity, screenshot_path=None):
    ws = get_ws(state)
    rows = ws.get_all_values()
    # 중복 체크
    for row in rows[1:]:
        if len(row) >= 5 and row[2] == screen and row[3] == issue_type and row[4] == description:
            return
    num = len(rows)
    ws.append_row([
        num, state, screen, issue_type, description, severity,
        datetime.now().strftime('%Y-%m-%d %H:%M')
    ])

    # 스크린샷이 있으면 Drive에 업로드 후 H/I열 삽입
    if screenshot_path and os.path.exists(screenshot_path):
        sheet_row = num + 1  # 헤더 포함 1-based
        filename = f'{state}_{screen}_{issue_type}_{num}.png'
        urls = upload_screenshot(screenshot_path, filename)
        apply_screenshot_to_sheet(sheets_service, SHEET_ID, ws.id, sheet_row, urls)
```

> **스크린샷 규칙 (두 가지 케이스 구분)**:
>
> **케이스 1 — QA 오류 자동 기록 시**
> Playwright가 스크린샷 촬영 → Drive `HIK QA Screenshots` 폴더에 자동 업로드 → H열 인라인 미리보기 + I열 "열기" 링크 자동 삽입
>
> **케이스 2 — 사용자가 직접 사진을 넣은 경우 ("링크 넣어" 요청)**
> Playwright 촬영 없음. 사용자가 이미 Drive에 올린 파일을 찾아 연결한다.
> 1. 해당 행 이슈 설명 확인
> 2. Drive `HIK QA Screenshots` 폴더에서 `contentSnippet` 키워드 매칭으로 파일 탐색
> 3. I열에만 `=HYPERLINK("https://drive.google.com/file/d/FILE_ID/view","열기")` 삽입
> 4. H열 이미지(사용자가 셀 내 이미지 넣기로 직접 삽입한 것)는 절대 덮어쓰지 않는다.

## Playwright 로그인 패턴

```python
# 게스트
page.goto('https://homesinkorea-git-develop-homesinkorea.vercel.app/login')
page.fill('input[type="email"]', 'guesttest01@gmail.com')
page.fill('input[type="password"]', 'Guestpass1234!')
page.click('button[type="submit"]')
page.wait_for_load_state('networkidle')

# 호스트
page.goto('https://homesinkorea-git-develop-homesinkorea.vercel.app/login/host?next=%2Fhost')
page.fill('input[type="email"]', 'hostuser01@gmail.com')
page.fill('input[type="password"]', 'Hostpass1234!')
page.click('button[type="submit"]')
page.wait_for_load_state('networkidle')

# 관리자 (로그인 후 직접 진입)
# admintest01@gmail.com / Adminpass1234! 로 /login 로그인 후
page.goto('/admin/payments')
```
