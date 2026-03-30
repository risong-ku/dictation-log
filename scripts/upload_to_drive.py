"""
Google Drive へのディクテーションアップロード
GitHub Actions から環境変数経由で実行される
"""

import io
import os
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload


def get_credentials() -> Credentials:
    """
    環境変数 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN から
    OAuth2 Credentials オブジェクトを構築
    """
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

    request = Request()
    creds.refresh(request)

    return creds


def get_drive_service(creds: Credentials):
    """Google Drive API サービスを取得"""
    return build('drive', 'v3', credentials=creds)


def ensure_folder_exists(service, parent_id: str, folder_name: str) -> str:
    """
    parent_id 内に folder_name という名前のフォルダが存在するか確認。
    存在しなければ作成。フォルダIDを返す。
    """
    try:
        results = service.files().list(
            q=f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()

        files = results.get('files', [])
        if files:
            return files[0]['id']

        # フォルダが存在しないので作成
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    except HttpError as e:
        raise RuntimeError(f"フォルダ操作エラー: {e}")


def get_or_create_daily_file(service, folder_id: str, filename: str) -> tuple:
    """
    folder_id 内に filename というファイルが存在するか検索。
    存在すれば (file_id, existing_content) を返す。
    存在しなければ ('', '') を返す。
    """
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and name='{filename}' and mimeType='text/plain' and trashed=false",
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()

        files = results.get('files', [])
        if not files:
            return ('', '')

        file_id = files[0]['id']

        # ファイル内容を取得
        content = service.files().get_media(fileId=file_id).execute().decode('utf-8')
        return (file_id, content)

    except HttpError as e:
        raise RuntimeError(f"ファイル取得エラー: {e}")


def upload_or_update_file(service, folder_id: str, filename: str, content: str, file_id: str = None) -> str:
    """
    file_id がある場合: ファイルを上書き更新
    file_id がない場合: 新規ファイルを作成
    アップロード後のファイルIDを返す
    """
    try:
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode('utf-8')),
            mimetype='text/plain',
            resumable=False
        )

        if file_id:
            # 既存ファイルを更新
            service.files().update(
                fileId=file_id,
                body={'name': filename},
                media_body=media,
                fields='id'
            ).execute()
            return file_id
        else:
            # 新規ファイルを作成
            file_metadata = {
                'name': filename,
                'mimeType': 'text/plain',
                'parents': [folder_id]
            }
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id')

    except HttpError as e:
        raise RuntimeError(f"ファイルアップロードエラー: {e}")


def format_entry(text: str, timestamp: str, source: str) -> str:
    """
    1エントリをフォーマット
    """
    return f"[{timestamp}] ({source})\n{text}\n---\n"


def main():
    """メイン処理"""
    # 環境変数から入力を取得
    dictation_text = os.environ.get('DICTATION_TEXT', '').strip()
    dictation_timestamp = os.environ.get('DICTATION_TIMESTAMP', '')
    dictation_source = os.environ.get('DICTATION_SOURCE', 'siri')
    root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')

    if not dictation_text:
        print("⚠️  警告: DICTATION_TEXT が空です")
        return

    if not root_folder_id:
        raise ValueError("環境変数 GOOGLE_DRIVE_FOLDER_ID が設定されていません")

    # OAuth2 認証
    print("🔐 Google Drive に接続中...")
    creds = get_credentials()
    service = get_drive_service(creds)

    # 日付ベースのフォルダ構成を作成
    if dictation_timestamp:
        # 様々な日付形式に対応: 2026-03-29, 2026/3/29, 2026/03/29 等
        date_part = dictation_timestamp.split()[0].replace('/', '-')
        # 月・日が1桁の場合を補完 (2026-3-29 → 2026-03-29)
        parts = date_part.split('-')
        if len(parts) == 3:
            date_part = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        dt = datetime.fromisoformat(date_part)
    else:
        dt = datetime.now()
    year = dt.strftime('%Y')
    month = dt.strftime('%Y-%m')
    filename = dt.strftime('%Y-%m-%d') + '.txt'

    print(f"📁 フォルダ構成を作成中: {year}/{month}")
    year_folder_id = ensure_folder_exists(service, root_folder_id, 'dictations')
    year_folder_id = ensure_folder_exists(service, year_folder_id, year)
    month_folder_id = ensure_folder_exists(service, year_folder_id, month)

    # ファイルを取得または作成
    file_id, existing_content = get_or_create_daily_file(service, month_folder_id, filename)

    # エントリをフォーマット
    new_entry = format_entry(dictation_text, dictation_timestamp, dictation_source)

    # 追記またはまかし作成
    if file_id:
        # 既存ファイルに追記
        if existing_content and not existing_content.endswith('\n'):
            existing_content += '\n'
        final_content = existing_content + new_entry
        print(f"✏️  既存ファイルに追記: {filename}")
    else:
        # 新規ファイルを作成
        header = f"# {filename.replace('.txt', '')} ディクテーションログ\n\n"
        final_content = header + new_entry
        print(f"📝 新規ファイルを作成: {filename}")

    # アップロード
    file_id = upload_or_update_file(service, month_folder_id, filename, final_content, file_id)
    print(f"✅ Google Drive にアップロード完了")
    print(f"📍 保存場所: dictations/{year}/{month}/{filename}")


if __name__ == '__main__':
    try:
        main()
    except ValueError as e:
        print(f"❌ 入力エラー: {e}")
        exit(1)
    except RefreshError:
        print("❌ Google Drive 認証エラー: refresh_token が無効な可能性があります")
        print("auth_setup.py を再実行してください")
        exit(1)
    except Exception as e:
        print(f"❌ エラー: {e}")
        exit(1)
