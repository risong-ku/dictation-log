# Dictation Log - ディクテーション自動化システム

iPhone の Siri 音声入力から Google Drive への自動保存システムです。毎日のふり返りやメモを、声で記録できます。

## 🎯 機能

- **音声入力**: iPhone の Siri 音声入力で日本語テキスト入力
- **自動保存**: GitHub Actions で Google Drive に日付単位のテキストファイル保存
- **追記対応**: 同日に複数回のディクテーションを自動で追記
- **フォルダ自動整理**: 年/月/日の階層で Google Drive を自動整理

## 📋 前提条件

- iPhone（Siri 音声入力対応）
- GitHub アカウント
- Google アカウント
- Python 3.12（ローカル認証時）

## 🚀 セットアップ

### 1. Google Cloud Console の設定

1. [Google Cloud Console](https://console.cloud.google.com) にアクセス
2. 新規プロジェクトを作成（例: `dictation-log`）
3. **APIs とサービス** → **ライブラリ** → "Google Drive API" を有効化
4. **OAuth 同意画面**を設定
   - ユーザーの種類: 外部
   - アプリ名: `dictation-log`
   - スコープに `https://www.googleapis.com/auth/drive.file` を追加
   - テストユーザーに自分のメールアドレスを追加
5. **認証情報** → **認証情報を作成** → **OAuth クライアント ID**
   - アプリケーションの種類: デスクトップアプリ
   - `credentials.json` をダウンロード

### 2. ローカルで refresh_token を生成

```bash
# このリポジトリをクローン
git clone https://github.com/risong-ku/dictation-log.git
cd dictation-log

# 依存関係をインストール
pip install -r requirements.txt

# Google Cloud Console からダウンロードした credentials.json をカレントディレクトリに置く
# その後以下を実行
python scripts/auth_setup.py
```

ブラウザが開き、Google アカウントでの認証を求められます。認証後、以下の情報がターミナルに表示されます：

```
GOOGLE_CLIENT_ID: xxxxx
GOOGLE_CLIENT_SECRET: xxxxx
GOOGLE_REFRESH_TOKEN: 1//xxxxxx
```

### 3. Google Drive フォルダの作成

Google Drive で `dictation-log` という名前のフォルダを作成し、URL からフォルダ ID を取得します：

```
https://drive.google.com/drive/folders/1BxiMVs0XRA5nFxxxxx
                                        ^^^^^^^^^^^^^^^^^^^^
                                        これが FOLDER_ID
```

### 4. GitHub Secrets に登録

GitHub リポジトリの **Settings** → **Secrets and variables** → **Actions** で以下を登録：

| Secret 名 | 値 |
|---|---|
| `GOOGLE_CLIENT_ID` | auth_setup.py の出力 |
| `GOOGLE_CLIENT_SECRET` | auth_setup.py の出力 |
| `GOOGLE_REFRESH_TOKEN` | auth_setup.py の出力 |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive フォルダ ID |

### 5. GitHub Personal Access Token (PAT) の作成

1. GitHub の **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token** をクリック
3. スコープ: `repo` にチェック
4. トークンをコピー（再表示されません）

### 6. iPhone Shortcuts の設定

iPhone の Shortcuts アプリで以下のステップを実行するショートカットを作成：

**ステップ 1: 音声入力**
- アクション: "テキストを入力" → "音声入力" を選択
- 設定: 日本語、自動停止 ON

**ステップ 2: 日時取得**
- アクション: "日付を取得"
- フォーマット: カスタム → `yyyy-MM-dd HH:mm:ss`

**ステップ 3: JSON ペイロード作成**
- アクション: "テキスト"
- 内容:
```json
{"event_type": "dictation", "client_payload": {"text": "[ステップ1の変数]", "timestamp": "[ステップ2の変数]", "source": "siri"}}
```

**ステップ 4: GitHub API に送信**
- アクション: "URL の内容を取得"
- URL: `https://api.github.com/repos/risong-ku/dictation-log/dispatches`
- メソッド: `POST`
- ヘッダー:
  - `Authorization`: `Bearer [GitHub PAT]`
  - `Accept`: `application/vnd.github.v3+json`
  - `Content-Type`: `application/json`
- リクエスト本文: ステップ 3 のテキスト変数

**ステップ 5: 完了通知**
- アクション: "通知を表示"
- 本文: "ディクテーション送信完了"

## 📝 使用方法

1. iPhone ホーム画面からショートカットをタップ
2. Siri が音声入力を待機（自動）
3. ディクテーション内容を話す
4. "ディクテーション送信完了" 通知が表示
5. Google Drive に自動保存（数秒）

## 📂 Google Drive のファイル構成

```
dictation-log/
└── dictations/
    └── 2026/
        └── 2026-03/
            ├── 2026-03-27.txt
            └── 2026-03-28.txt
```

各ファイルのフォーマット：

```
# 2026-03-28 ディクテーションログ

[2026-03-28 08:30:15] (siri)
今朝の思考をここに記録...
---

[2026-03-28 22:00:00] (siri)
夜の振り返り...
---
```

## 🔐 セキュリティに関する注意

- `refresh_token` は `~/.gitignore` に含まれています。**コミットしないでください**
- GitHub Secrets に登録されたトークンはログに表示されません
- Google Drive スコープは `drive.file`（最小権限）を使用

## 🚧 将来の拡張

- [ ] 手書き文字 OCR 読み取り
- [ ] X（Twitter）への自動投稿
- [ ] 週次 Slack サマリー通知

## 📝 トラブルシューティング

### refresh_token が無効になった場合

6 ヶ月間未使用またはパスワード変更後に失効します。再度 `auth_setup.py` を実行してください。

### ディクテーションが送信されない場合

1. Shortcuts のテスト実行で GitHub API の応答を確認
2. GitHub Actions ログで詳細なエラーを確認
3. Secrets が正しく登録されているか確認

## 📄 ライセンス

MIT

## 👨‍💻 作成者

risong-ku
