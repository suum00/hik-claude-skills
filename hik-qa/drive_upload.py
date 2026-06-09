"""
HIK QA 스크린샷 → Google Drive 업로드 유틸리티
모든 QA 탭 공통 사용
"""
import os
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

CLIENT_SECRET = os.path.expanduser(
    '~/Downloads/client_secret_51575743124-hhvdq3qpo1bi9nca3r2g60d4tg9tcbrt.apps.googleusercontent.com.json'
)
TOKEN_FILE = os.path.expanduser('~/.hik_drive_token.pickle')
FOLDER_ID = '1zoYjur3ZKxcGKy0z2FdZbWSnF5-WoTgF'
SCOPES = ['https://www.googleapis.com/auth/drive.file']

_drive_service = None

def get_drive_service():
    global _drive_service
    if _drive_service:
        return _drive_service
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)
    _drive_service = build('drive', 'v3', credentials=creds)
    return _drive_service


def upload_screenshot(local_path: str, filename: str) -> dict:
    """
    스크린샷을 Drive에 업로드하고 시트에 삽입할 URL 딕셔너리 반환.

    Returns:
        {
            'image_url':  =IMAGE()에 쓸 URL (anyone with link),
            'drive_url':  열기 링크,
            'file_id':    Drive file ID
        }
    """
    drive = get_drive_service()
    media = MediaFileUpload(local_path, mimetype='image/png')
    file = drive.files().create(
        body={'name': filename, 'parents': [FOLDER_ID]},
        media_body=media,
        fields='id'
    ).execute()
    file_id = file['id']

    # 링크 있는 사람 공개 (=IMAGE() 작동에 필요)
    drive.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'},
    ).execute()

    return {
        'image_url': f'https://drive.google.com/uc?export=view&id={file_id}',
        'drive_url': f'https://drive.google.com/file/d/{file_id}/view',
        'file_id': file_id,
    }


def apply_screenshot_to_sheet(service, sheet_id: str, ws_id: int, row: int, urls: dict):
    """
    H열: =IMAGE(), I열: '열기' Drive 링크 삽입.
    row는 1-based 시트 행 번호.
    """
    row_idx = row - 1
    requests = [
        {
            'updateCells': {
                'range': {'sheetId': ws_id,
                          'startRowIndex': row_idx, 'endRowIndex': row_idx + 1,
                          'startColumnIndex': 7, 'endColumnIndex': 8},
                'rows': [{'values': [{'userEnteredValue': {
                    'formulaValue': f'=IMAGE("{urls["image_url"]}")'
                }}]}],
                'fields': 'userEnteredValue'
            }
        },
        {
            'updateCells': {
                'range': {'sheetId': ws_id,
                          'startRowIndex': row_idx, 'endRowIndex': row_idx + 1,
                          'startColumnIndex': 8, 'endColumnIndex': 9},
                'rows': [{'values': [{'userEnteredValue': {'stringValue': '열기'},
                                      'userEnteredFormat': {
                                          'textFormat': {
                                              'link': {'uri': urls['drive_url']},
                                              'foregroundColorStyle': {'rgbColor': {
                                                  'red': 0.06, 'green': 0.44, 'blue': 0.78
                                              }},
                                              'underline': True
                                          },
                                          'horizontalAlignment': 'CENTER',
                                          'verticalAlignment': 'MIDDLE'
                                      }}]}],
                'fields': 'userEnteredValue,userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment'
            }
        }
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': requests}
    ).execute()
