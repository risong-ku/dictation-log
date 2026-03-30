"""
手書き画像 OCR → Google Drive アップロード
GitHub Actions から環境変数経由で実行される
Gemini API で画像を文字起こしし、Google Drive に保存する
"""

import os
import base64
import json
import urllib.request
import urllib.error
from google.auth.exceptions import RefreshError
from drive_helper import save_to_drive


def ocr_with_gemini(image_base64: str, gemini_api_key: str) -> str:
    """Gemini API で画像を文字起こし"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}"

    payload = {
        "contents": [{
            "parts": [
                {
                    "text": "この画像に書かれている手書き文字をそのまま文字起こしてください。文字起こしの結果のみを返してください。余計な説明は不要です。"
                },
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
        }]
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))

    return result['candidates'][0]['content']['parts'][0]['text'].strip()


def main():
    image_base64 = os.environ.get('DICTATION_IMAGE_BASE64', '')
    timestamp = os.environ.get('DICTATION_TIMESTAMP', '')
    source = os.environ.get('DICTATION_SOURCE', 'iPhone OCR')
    root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
    gemini_api_key = os.environ.get('GEMINI_API_KEY', '')

    if not image_base64:
        print("⚠️  警告: DICTATION_IMAGE_BASE64 が空です")
        return

    if not root_folder_id:
        raise ValueError("環境変数 GOOGLE_DRIVE_FOLDER_ID が設定されていません")

    if not gemini_api_key:
        raise ValueError("環境変数 GEMINI_API_KEY が設定されていません")

    print("🔍 Gemini で画像を文字起こし中...")
    text = ocr_with_gemini(image_base64, gemini_api_key)
    print(f"📝 文字起こし結果: {text[:50]}...")

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
