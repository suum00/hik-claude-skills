---
name: hik-flowchart
description: Use when user provides a URL and a flow name (e.g. "홈>검색 플로우 만들어줘") and wants a task flowchart automatically created in an existing Google Spreadsheet via gspread and the Sheets API.
---

# Google Sheets 태스크 플로우차트 자동 생성

## Overview
URL을 읽어 특정 플로우를 추출하고, Google Sheets API(gspread)로 기존 시트에 가로형 플로우차트를 자동 생성한다.

## Prerequisites
- `pip3 install gspread google-auth`
- 서비스 계정 JSON 키 파일 경로 확인
- 대상 스프레드시트를 서비스 계정 이메일로 공유 (편집자 권한)

```python
# 서비스 계정 이메일 확인
import json
print(json.load(open(CREDS_FILE))['client_email'])
```

## Workflow

1. URL + 플로우 헤드라인 수신 (예: "홈>검색 플로우 만들어줘")
2. WebFetch로 해당 섹션만 파싱
3. 플로우 노드 / 분기 / 연결 구조화
4. Python 스크립트로 **플로우 이름 탭**에 작성 (기존 탭 유지)

## Layout

```
행 1: 타이틀 (전체 열 병합)
행 2: [START] → [노드] → [노드] → ... → [END]
행 3:           (노트)   (노트)
```

- **가로형** — 노드는 좌→우
- **3행 고정** — 공백 행 없음
- **단일 탭** — `sh.get_worksheet(0)` 하나의 탭에 플로우를 위아래로 쌓기
- 플로우 사이 구분선: 높이 10px, `#EEEEEE` 배경 행

```python
# 새 플로우는 기존 내용 아래에 추가
# 구분선 행(10px, 회색) → 다음 플로우 (3행)
ws = sh.get_worksheet(0)
```

## 색상 기준

| 색상 | 의미 | 적용 |
|------|------|------|
| `#DCFCE7` 연두 | 선택 + 입력 | 조건 설정, 실행, 카드 선택 등 |
| `#DBEAFE` 블루 | 페이지 이동 | 홈화면, 결과, 상세페이지 등 |
| `#FEF3C7` 앰버 | 판단 (분기) | Yes/No 분기점 |
| `#F1F5F9` 슬레이트 | 시작 / 끝 | START, END |

**공통 규칙:**
- Border(아웃라인) 없음
- 모든 텍스트: `#212121` (검은색)
- 노트 배경: 노드 색보다 더 연하게 (`#F0FDF4`, `#F0F7FF`, `#FFFBEB`)

## 핵심 코드 패턴

```python
import gspread

gc = gspread.service_account(filename=CREDS_FILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.get_worksheet(0)  # 기존 시트 사용
sid = ws.id

req = []

# 1) 기존 마지막 행 파악 → 그 아래에 추가
all_values = ws.get_all_values()
start_row = len(all_values)  # 0-indexed 시작 행

# 첫 번째 플로우가 아니면 구분선 행(10px, 회색) 추가
if start_row > 0:
    req.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": start_row, "endIndex": start_row + 1},
        "properties": {"pixelSize": 10}, "fields": "pixelSize"
    }})
    req.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": start_row, "endRowIndex": start_row + 1,
                  "startColumnIndex": 0, "endColumnIndex": 25},
        "cell": {"userEnteredFormat": {"backgroundColor": rgb("#EEEEEE")}},
        "fields": "userEnteredFormat"
    }})
    start_row += 1  # 구분선 다음 행부터 플로우 시작

# 이후 모든 행 인덱스는 start_row 기준으로 offset 적용
# title_row = start_row, node_row = start_row+1, note_row = start_row+2

# 2) 열 너비: 여백15 | 노드100~155 | 화살표28 | ... | 여백15
# 3) 행 높이: 타이틀42 | 노드88 | 노트62
# 4) 타이틀 병합 후 셀 작성
# 5) 노드, 화살표(→), 노트 순서로 req에 추가
# 6) sh.batch_update({"requests": req})
```

## 컬럼 구성 예시 (9노드 기준)

```
A(15) B(100) C(28) D(130) E(28) F(155) G(28) H(100) I(28)
J(130) K(28) L(120) M(28) N(120) O(28) P(130) Q(28) R(90) S(15)
```
노드 열: 짝수 인덱스 / 화살표 열: 홀수 인덱스

## 사용자 설정 위치

| 항목 | 위치 |
|------|------|
| 서비스 계정 키 | `~/Downloads/` 또는 사용자 지정 경로 |
| 스프레드시트 ID | URL에서 `/d/` 다음 문자열 |
