"""
Google Cloud Functions - Dictation Log
iPhone Shortcuts からの POST を受け取り Google Drive に保存する
"""

import json
import os
from datetime import datetime, timezone, timedelta

import functions_framework
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
import io

ROOT_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
JST = timezone(timedelta(hours=9))


@functions_framework.http
def dictation(request):
    """HTTP エンドポイント"""
    # CORS 対応
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    if request.method != 'POST':
        return (json.dumps({'status': 'error', 'message': 'POST only'}), 405, headers)

    try:
        data = request.get_json(force=True)
        if not data:
            return (json.dumps({'status': 'error', 'message': 'Invalid JSON'}), 400, headers)

        text = (data.get('text') or '').strip()
        source = data.get('source', 'iPhone Siri')
        timestamp = data.get('timestamp', '')

        if not text:
            return (json.dumps({'status': 'error', 'message': 'text is empty'}), 400, headers)

        if not ROOT_FOLDER_ID:
            return (json.dumps({'status': 'error', 'message': 'GOOGLE_DRIVE_FOLDER_ID not set'}), 500, headers)

        # 現在の JST 日時
        now = datetime.now(JST)
        year = now.strftime('%Y')
        month = now.strftime('%Y-%m')
        date_str = now.strftime('%Y-%m-%d')
        filename = date_str + '.txt'

        if not timestamp:
            timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

        # Google Drive API（デフォルト認証を使用）
        service = build('drive', 'v3')

        # フォルダ構成を作成
        dictations_id = ensure_folder(service, ROOT_FOLDER_ID, 'dictations')
        year_id = ensure_folder(service, dictations_id, year)
        month_id = ensure_folder(service, year_id, month)

        # エントリをフォーマット
        entry = f"[{timestamp}] ({source})\n{text}\n---\n"

        # 既存ファイルを検索
        file_id, existing = get_file(service, month_id, filename)

        if file_id:
            content = existing + ('\n' if not existing.endswith('\n') else '') + entry
            update_file(service, file_id, filename, content)
        else:
            header = f"# {date_str} ディクテーションログ\n\n"
            create_file(service, month_id, filename, header + entry)

        return (json.dumps({'status': 'success', 'file': filename}), 200, headers)

    except Exception as e:
        return (json.dumps({'status': 'error', 'message': str(e)}), 500, headers)


def ensure_folder(service, parent_id, name):
    q = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = service.files().list(q=q, fields='files(id)', pageSize=1).execute()
    files = res.get('files', [])
    if files:
        return files[0]['id']
    folder = service.files().create(
        body={'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]},
        fields='id'
    ).execute()
    return folder['id']


def get_file(service, folder_id, filename):
    q = f"'{folder_id}' in parents and name='{filename}' and mimeType='text/plain' and trashed=false"
    res = service.files().list(q=q, fields='files(id)', pageSize=1).execute()
    files = res.get('files', [])
    if not files:
        return '', ''
    file_id = files[0]['id']
    content = service.files().get_media(fileId=file_id).execute().decode('utf-8')
    return file_id, content


def update_file(service, file_id, filename, content):
    media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
    service.files().update(fileId=file_id, body={'name': filename}, media_body=media, fields='id').execute()


def create_file(service, folder_id, filename, content):
    media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
    service.files().create(
        body={'name': filename, 'mimeType': 'text/plain', 'parents': [folder_id]},
        media_body=media, fields='id'
    ).execute()
