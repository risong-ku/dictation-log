# dictation-log - ディクテーション自動化システム

iPhone の音声入力または手書き写真から、Google Drive にディクテーションログを自動保存するシステムです。

## 機能

| 機能 | 説明 |
|------|------|
| 音声入力 | iPhone Siri で話した内容を Google Drive に保存 |
| 手書きOCR | 手書きメモを写真撮影し、Gemini AI で文字起こしして保存 |
| 日付別ファイル管理 | 年/月/日 の階層で Google Drive を自動整理 |
| 同日追記 | 同日に複数回記録しても同じファイルに追記 |

## システム構成

```
iPhone Shortcuts
    ↓ POST
Netlify Functions（中継・OCR処理）
    ↓ POST（JSON）
GitHub API → GitHub Actions
    ↓ Python スクリプト
Google Drive（日付別テキストファイル）
```

詳細は [ARCHITECTURE.md](ARCHITECTURE.md) を参照してください。

## 前提条件

- iPhone（Shortcuts アプリ）
- GitHub アカウント
- Google アカウント
- Netlify アカウント（無料）
- Python 3.12（初回セットアップ時のみ）

## セットアップ

### 1. Google Cloud Console の設定

1. [Google Cloud Console](https://console.cloud.google.com) で新規プロジェクトを作成
2. **APIs とサービス** → **ライブラリ** → **Google Drive API** を有効化
3. **OAuth 同意画面**を設定
   - ユーザーの種類: 外部
   - スコープ: `https://www.googleapis.com/auth/drive.file`
   - テストユーザーに自分のメールアドレスを追加（「対象」メニューから）
4. **認証情報** → **OAuth クライアント ID** を作成
   - アプリケーションの種類: デスクトップアプリ
   - `credentials.json` をダウンロード

### 2. ローカルで refresh_token を生成

```bash
cd dictation-log
conda run -n devenv pip install -r requirements.txt
# credentials.json をこのディレクトリに置いてから実行
PYTHONIOENCODING=utf-8 python scripts/auth_setup.py
```

ブラウザが開き Google 認証後、以下が表示されます：
```
GOOGLE_CLIENT_ID: xxxxx
GOOGLE_CLIENT_SECRET: xxxxx
GOOGLE_REFRESH_TOKEN: 1//xxxxxx
```

### 3. Google Drive フォルダの作成

Google Drive で `dictation-log` フォルダを作成し、URL からフォルダ ID を取得：
```
https://drive.google.com/drive/folders/1BxiMVs0XRA5nFxxxxx
                                        ^^^^^^^^^^^^^^^^^^^^
                                        これが FOLDER_ID
```

### 4. GitHub リポジトリの設定

**リポジトリを作成**してコードをプッシュ後、Settings → Secrets and variables → Actions に以下を登録：

| Secret 名 | 値 |
|-----------|-----|
| `GOOGLE_CLIENT_ID` | auth_setup.py の出力 |
| `GOOGLE_CLIENT_SECRET` | auth_setup.py の出力 |
| `GOOGLE_REFRESH_TOKEN` | auth_setup.py の出力 |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive フォルダ ID |

### 5. Gemini API キーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey) にアクセス
2. **「Create API key」** → **「新しいプロジェクトを作成」** を選択
   - ※ 既存の課金プロジェクトを選ぶと無料枠が使えないので注意
3. 請求階層が「無料枠」になっていることを確認

### 6. Netlify のセットアップ

1. [Netlify](https://app.netlify.com) で GitHub アカウントでログイン
2. **「Add new site」** → **「Import an existing project」** → GitHub の `dictation-log` リポジトリを選択
3. **Functions directory** が `netlify/functions` になっていることを確認してデプロイ
4. Site configuration → Environment variables に以下を追加：

| 変数名 | 値 |
|--------|-----|
| `GITHUB_PAT` | GitHub Personal Access Token（`repo` スコープ） |
| `GEMINI_API_KEY` | Gemini API キー（無料プロジェクトのもの） |

5. 環境変数追加後に **Deploys → Trigger deploy** で再デプロイ

### 7. GitHub Personal Access Token の作成

Settings → Developer settings → Personal access tokens → Tokens (classic) で作成：
- スコープ: `repo` のみ

### 8. iPhone Shortcuts の設定

#### 音声入力ショートカット

| # | アクション | 設定 |
|---|-----------|------|
| 1 | テキストを音声入力 | 言語: 日本語、停止: 停止後 |
| 2 | 日付を書式設定 | カスタム: `yyyy-MM-dd HH:mm:ss` |
| 3 | URLの内容を取得 | 下記参照 |
| 4 | URLの内容を表示 | デバッグ確認用 |

URLの内容を取得の設定：
- URL: `https://[netlify-url]/.netlify/functions/dictation`
- 方法: `POST`
- 本文を要求: **フォーム**
  - `text` = 音声入力の出力
  - `timestamp` = フォーマット済みの日付
  - `source` = `iPhone Siri`

#### 手書きOCRショートカット

| # | アクション | 設定 |
|---|-----------|------|
| 1 | 写真を撮る | 背面カメラ、1枚 |
| 2 | イメージのサイズを変更 | 幅: 2560、高さ: 自動 |
| 3 | 日付を書式設定 | カスタム: `yyyy-MM-dd HH:mm:ss` |
| 4 | Base64エンコード | 入力: サイズ変更済みの画像 |
| 5 | URLの内容を取得 | 下記参照 |
| 6 | URLの内容を表示 | デバッグ確認用 |

URLの内容を取得の設定：
- URL: `https://[netlify-url]/.netlify/functions/ocr`
- 方法: `POST`
- 本文を要求: **JSON**
  - `image_base64` = Base64エンコードの出力
  - `timestamp` = フォーマット済みの日付
  - `source` = `iPhone OCR`

## 使用方法

**音声入力**
1. iPhone で「ディクテーション」ショートカットを実行
2. 話しかける
3. 数秒後に Google Drive に自動保存

**手書きOCR**
1. iPhone で「手書きOCRディクテーション」ショートカットを実行
2. 手書きメモを撮影
3. Gemini AI が文字起こし → Google Drive に自動保存

## Google Drive のフォルダ構成

```
dictation-log/
└── dictations/
    └── 2026/
        └── 2026-03/
            └── 2026-03-30.txt
```

ファイルフォーマット：
```
# 2026-03-30 ディクテーションログ

[2026-03-30 08:30:00] (iPhone Siri)
今日の振り返り...
---

[2026-03-30 20:00:00] (iPhone OCR)
手書きメモの内容...
---
```

## セキュリティ

- `credentials.json` / `token.json` は `.gitignore` で除外済み
- 機密情報は GitHub Secrets / Netlify 環境変数に暗号化して保存
- Google Drive スコープは `drive.file`（最小権限）を使用
- リポジトリが Public でも Secrets の値は外部から参照不可

## トラブルシューティング

詳細は [ARCHITECTURE.md](ARCHITECTURE.md#11-トラブルシューティング集) を参照。

主なトラブルと対策：
- **GitHub Actions が起動しない**: Netlify の `GITHUB_PAT` を確認
- **Gemini が 429 エラー**: 課金プロジェクトではなく無料プロジェクトのキーを使用
- **写真が 422 エラー**: Shortcuts でリサイズ（2560px）してから送信

## 将来の拡張

- [ ] 週次サマリーを Slack に通知
- [ ] X（Twitter）への自動投稿
