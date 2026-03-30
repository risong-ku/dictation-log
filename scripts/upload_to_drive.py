"""
音声ディクテーション → Google Drive アップロード
GitHub Actions から環境変数経由で実行される
"""

import os
from google.auth.exceptions import RefreshError
from drive_helper import save_to_drive


def main():
    text = os.environ.get('DICTATION_TEXT', '').strip()
    timestamp = os.environ.get('DICTATION_TIMESTAMP', '')
    source = os.environ.get('DICTATION_SOURCE', 'iPhone Siri')
    root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')

    if not text:
        print("⚠️  警告: DICTATION_TEXT が空です")
        return

    if not root_folder_id:
        raise ValueError("環境変数 GOOGLE_DRIVE_FOLDER_ID が設定されていません")

    save_to_drive(text, timestamp, source, root_folder_id)


if __name__ == '__main__':
    try:
        main()
    except ValueError as e:
        print(f"❌ 入力エラー: {e}")
        exit(1)
    except RefreshError:
        print("❌ Google Drive 認証エラー: refresh_token が無効な可能性があります")
        exit(1)
    except Exception as e:
        print(f"❌ エラー: {e}")
        exit(1)
