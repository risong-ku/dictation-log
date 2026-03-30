"""
Google Drive 共通ヘルパー
upload_to_drive.py と ocr_to_drive.py から共通利用される
"""

import io
import os
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload


def get_credentials() -> Credentials:
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("環境変数 GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN が設定されていません")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret
    )
    creds.refresh(Request())
    return creds


def get_drive_service(creds: Credentials):
    return build('drive', 'v3', credentials=creds)


def ensure_folder_exists(service, parent_id: str, folder_name: str) -> str:
    try:
        results = service.files().list(
            q=f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id)',
            pageSize=1
        ).execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        folder = service.files().create(
            body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]},
            fields='id'
        ).execute()
        return folder.get('id')
    except HttpError as e:
        raise RuntimeError(f"フォルダ操作エラー: {e}")


def get_or_create_daily_file(service, folder_id: str, filename: str) -> tuple:
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and name='{filename}' and mimeType='text/plain' and trashed=false",
            spaces='drive',
            fields='files(id)',
            pageSize=1
        ).execute()
        files = results.get('files', [])
        if not files:
            return ('', '')
        file_id = files[0]['id']
        content = service.files().get_media(fileId=file_id).execute().decode('utf-8')
        return (file_id, content)
    except HttpError as e:
        raise RuntimeError(f"ファイル取得エラー: {e}")


def upload_or_update_file(service, folder_id: str, filename: str, content: str, file_id: str = None) -> str:
    try:
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode('utf-8')),
            mimetype='text/plain',
            resumable=False
        )
        if file_id:
            service.files().update(
                fileId=file_id, body={'name': filename}, media_body=media, fields='id'
            ).execute()
            return file_id
        else:
            file = service.files().create(
                body={'name': filename, 'mimeType': 'text/plain', 'parents': [folder_id]},
                media_body=media, fields='id'
            ).execute()
            return file.get('id')
    except HttpError as e:
        raise RuntimeError(f"ファイルアップロードエラー: {e}")


def format_entry(text: str, timestamp: str, source: str) -> str:
    return f"[{timestamp}] ({source})\n{text}\n---\n"


def parse_timestamp(timestamp_str: str) -> datetime:
    """様々な日付形式に対応: 2026-03-29, 2026/3/29, 2026/03/29 等"""
    if not timestamp_str:
        return datetime.now()
    date_part = timestamp_str.split()[0].replace('/', '-')
    parts = date_part.split('-')
    if len(parts) == 3:
        date_part = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return datetime.fromisoformat(date_part)


def save_to_drive(text: str, timestamp: str, source: str, root_folder_id: str):
    """テキストを Google Drive の日付ベースファイルに保存する共通関数"""
    print("🔐 Google Drive に接続中...")
    creds = get_credentials()
    service = get_drive_service(creds)

    dt = parse_timestamp(timestamp)
    year = dt.strftime('%Y')
    month = dt.strftime('%Y-%m')
    filename = dt.strftime('%Y-%m-%d') + '.txt'

    print(f"📁 フォルダ構成を作成中: {year}/{month}")
    dictations_id = ensure_folder_exists(service, root_folder_id, 'dictations')
    year_id = ensure_folder_exists(service, dictations_id, year)
    month_id = ensure_folder_exists(service, year_id, month)

    file_id, existing_content = get_or_create_daily_file(service, month_id, filename)
    new_entry = format_entry(text, timestamp, source)

    if file_id:
        if existing_content and not existing_content.endswith('\n'):
            existing_content += '\n'
        final_content = existing_content + new_entry
        print(f"✏️  既存ファイルに追記: {filename}")
    else:
        header = f"# {dt.strftime('%Y-%m-%d')} ディクテーションログ\n\n"
        final_content = header + new_entry
        print(f"📝 新規ファイルを作成: {filename}")

    upload_or_update_file(service, month_id, filename, final_content, file_id)
    print(f"✅ Google Drive にアップロード完了")
    print(f"📍 保存場所: dictations/{year}/{month}/{filename}")
