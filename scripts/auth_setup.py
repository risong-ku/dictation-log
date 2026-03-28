"""
Google Drive OAuth2 初回認証スクリプト
ローカルでのみ実行。refresh_token を取得して GitHub Secrets に登録する。
"""

import json
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Drive API に必要なスコープ
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def setup_oauth2():
    """OAuth2 フローを実行して credentials を取得"""
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',
        SCOPES
    )
    creds = flow.run_local_server(port=0)

    # トークン情報を表示
    print("\n" + "="*60)
    print("✅ OAuth2 認証が完了しました")
    print("="*60)
    print("\n以下の値を GitHub Secrets に登録してください:\n")

    print(f"GOOGLE_CLIENT_ID: {creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET: {creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN: {creds.refresh_token}")

    print("\n" + "="*60)
    print("GOOGLE_DRIVE_FOLDER_ID は以下のステップで取得してください:")
    print("1. Google Drive にアクセス")
    print("2. 'dictation-log' フォルダを作成")
    print("3. フォルダを開く")
    print("4. URL から ID を抽出")
    print("   例: https://drive.google.com/drive/folders/1BxiMVs0XRA5nF...Bs")
    print("       1BxiMVs0XRA5nF...Bs が GOOGLE_DRIVE_FOLDER_ID")
    print("="*60)

    return creds

if __name__ == '__main__':
    try:
        setup_oauth2()
    except FileNotFoundError:
        print("❌ エラー: credentials.json が見つかりません")
        print("\nGoogle Cloud Console から credentials.json をダウンロードして、")
        print("このスクリプトと同じディレクトリに置いてください")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
