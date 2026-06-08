---
name: hik-qa
description: Use when doing QA on HomeSinKorea web service — checking UI matches Figma, flows match the flow document, back navigation, and popup/bottom sheet behavior across non-logged-in, guest, host, and admin states
---

# HIK Web Service QA

## Overview
Playwright 기반 QA 스킬. 6가지 규칙을 4개 상태별로 순차 검증하고, 이슈를 Google Sheet에 기록한다.

## 고정 설정값

| 항목 | 값 |
|------|-----|
| 서비스 URL | https://homesinkorea-git-develop-homesinkorea.vercel.app |
| Figma 파일키 | 7DEB0l3BEOeJWLwbkpxgir |
| Google Sheet ID | 1-n6YwMjppwANQRiT3qIytOzRt-pUvoIushUzgT4sef8 |
| 서비스 계정 키 | /Users/sujin/Downloads/swift-implement-498523-i1-4c673fb266fe.json |

## 테스트 계정

| 상태 | ID | PW | 진입 |
|------|----|----|------|
| 게스트 | guesttest01@gmail.com | (팀 내부 공유) | /login |
| 호스트 | hostuser01@gmail.com | (팀 내부 공유) | /login/host |
| 관리자 | admintest01@gmail.com | (팀 내부 공유) | /login → /admin/payments |

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
| 이용문의 | 숙소 상세 → Chat 버튼 → `/inquiry/:id` | 메시지 전송 성공 팝업 노출 |
| 숙소등록 | 호스트 대시보드 → 숙소 등록 | 등록 완료 후 목록에 노출 |
| 방 등록 | 숙소 관리 → 방 추가 | 방 정보 저장 후 목록에 노출 |
| 채팅 | `/messages` → 채팅방 진입 → 메시지 전송 | 전송 메시지가 상대방 채팅방에 노출 |

- 10회 중 1회라도 실패하면 이슈 기록 (심각도: 높음)
- 성공률을 설명 컬럼에 기재: 예) `10회 중 2회 실패 (성공률 80%)`
- 실패한 회차의 스크린샷 첨부

```python
def repeat_flow_test(page, flow_name, test_fn, repeat=10):
    failures = []
    for i in range(repeat):
        try:
            test_fn(page)
        except Exception as e:
            screenshot_path = f"{SCREENSHOT_DIR}/{flow_name}_fail_{i+1}.png"
            page.screenshot(path=screenshot_path)
            failures.append((i + 1, str(e), screenshot_path))
    if failures:
        desc = f"{repeat}회 중 {len(failures)}회 실패 (성공률 {(repeat-len(failures))*10}%)"
        log_issue("공통", flow_name, "플로우", desc, severity="높음",
                  screenshot_path=failures[0][2])
    else:
        ok(f"{flow_name} {repeat}회 전체 성공")
```

## QA 시작 트리거

사용자가 **"QA 시작"** 이라고 하면 아래 순서로 동작한다:
1. 플로우 문서(Sheet ID: `1m9PqwYK9-nT35-2Nv3spQAgsJybneWn81yMfBTkHAKc`) 읽기
2. 5개 컬럼(출발 화면 ID / 출발 화면 이름 / 트리거 / 동작 유형 / 도착 화면 ID)이 모두 채워진 행만 QA 대상으로 선정
3. 이전 QA 결과와 비교 — 변경된 행이 있으면 해당 화면 재QA, 새 행이 있으면 신규 QA
4. 대상 화면에 대해 전체 규칙 검증 실행

## QA 실행 순서

```
1. 비로그인 상태 → 전체 규칙 검증
2. 게스트 로그인 → 전체 규칙 검증
3. 호스트 로그인 → 전체 규칙 검증
4. 관리자 로그인 → 전체 규칙 검증
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
| 스크린샷 | catbox.moe 업로드 후 IMAGE() 함수로 삽입 |

## 이슈 심각도 기준

| 심각도 | 기준 |
|--------|------|
| 높음 | 화면 이동 불가, 404, 크래시, 팝업 미노출 |
| 중간 | 잘못된 화면으로 이동, 뒤로가기 오작동, 팝업 미닫힘 |

## Google Sheet 기록 코드 패턴

```python
import gspread
from google.oauth2 import service_account
from datetime import datetime

KEY_FILE = '/Users/sujin/Downloads/swift-implement-498523-i1-4c673fb266fe.json'
SHEET_ID = '1-n6YwMjppwANQRiT3qIytOzRt-pUvoIushUzgT4sef8'

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(creds)
ws = gc.open_by_key(SHEET_ID).worksheet('QA Issues')

def log_issue(state, screen, issue_type, description, severity):
    rows = ws.get_all_values()
    num = len(rows)  # 헤더 제외 순번
    ws.append_row([
        num, state, screen, issue_type, description, severity,
        datetime.now().strftime('%Y-%m-%d %H:%M')
    ])
```

## Playwright 로그인 패턴

```python
# 게스트
page.goto('/login')
page.fill('input[type="email"]', 'guesttest01@gmail.com')
page.fill('input[type="password"]', 'Guestpass1234!')
page.click('button[type="submit"]')
page.wait_for_load_state('networkidle')

# 관리자 (로그인 후 직접 진입)
# admintest01@gmail.com / Adminpass1234! 로 /login 로그인 후
page.goto('/admin/payments')
```
