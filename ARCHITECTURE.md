# dictation-log アーキテクチャ & ノウハウ集

---

## 1. 開発目的

毎日手書きでディクテーション（1日の振り返り）を行っていたが、以下の課題があった：

- 手書きのためデジタルデータとして残らない
- 忙しい日は書く時間が取れない

これを解決するため、以下を実現するシステムを構築した：

- **音声入力**: 忙しい時でも iPhone に話しかけるだけで記録できる
- **手書きOCR**: 手書きメモを写真で撮るだけでデジタル化できる
- **自動保存**: Google Drive に日付単位で自動整理・保存される
- **サーバーレス**: 維持費ゼロ・メンテナンス不要で永続運用できる

---

## 2. 機能一覧

| 機能 | 説明 |
|------|------|
| 音声入力ディクテーション | iPhone Siri で話した内容を Google Drive に保存 |
| 手書きOCR ディクテーション | 手書きメモを写真撮影し、Gemini AI で文字起こしして保存 |
| 日付別ファイル管理 | 年/月/日 の階層で Google Drive を自動整理 |
| 同日追記 | 同日に複数回記録しても同じファイルに追記 |

---

## 3. 用語集

### OAuth2 / refresh_token
Google などの外部サービスに安全にアクセスするための認証方式。

- **access_token**: 実際にAPIを呼び出すための一時的なトークン（有効期限1時間）
- **refresh_token**: access_token を再発行するための長期トークン（有効期限なし）
- **なぜ refresh_token を使うか**: GitHub Actions はサーバーレスで毎回新しい環境で動くため、ファイルに access_token を保存できない。refresh_token を GitHub Secrets に保存しておけば、毎回 access_token を再発行できる

### GitHub Actions
GitHub が提供する CI/CD（自動化）サービス。コードのテストやデプロイを自動化するだけでなく、HTTPリクエストをトリガーにして任意のスクリプトを実行できる。本システムではサーバーの代わりとして使用。

### repository_dispatch
GitHub Actions を外部の HTTP リクエストから起動するためのイベント。iPhoneから `POST https://api.github.com/repos/{owner}/{repo}/dispatches` を呼ぶことで、GitHub Actions のワークフローをトリガーできる。

### Netlify Functions
Netlify が提供するサーバーレス関数サービス。Node.js（JavaScript）で書いた関数を URL として公開できる。本システムでは iPhone Shortcuts の制限を回避するための中継サーバーとして使用。

### サーバーレス
物理的なサーバーを持たずに、クラウドサービスのコンピューティングリソースを必要な時だけ使う仕組み。維持費がかからず、スケールも自動。

### Base64エンコード
バイナリデータ（画像等）をテキストで表現する変換方式。JSONはテキストしか扱えないため、画像をJSONで送信する際に使用する。

### GitHub Secrets
GitHub リポジトリに暗号化して保存できる機密情報。APIキーやトークンをコードに直接書かずに安全に管理できる。GitHub Actions の実行時のみ環境変数として展開される。

### PAT（Personal Access Token）
GitHub APIを呼び出すための認証トークン。パスワードの代わりに使用する。スコープ（権限範囲）を絞って発行できる。

---

## 4. 使用サービス概要

### GitHub
世界最大のコードホスティングサービス。コードのバージョン管理だけでなく、GitHub Actions による自動化も提供。
- 公式サイト: https://github.com
- 本システムでの役割: コード管理、スクリプト実行環境

### GitHub Actions
GitHub が提供する CI/CD サービス。YAMLファイルでワークフローを定義し、様々なイベントをトリガーに自動実行できる。
- 無料枠: パブリックリポジトリは無制限
- 本システムでの役割: Python スクリプトの実行（サーバー代わり）

### Netlify
静的サイトホスティングとサーバーレス関数を提供するサービス。GitHub と連携して自動デプロイが可能。
- 公式サイト: https://netlify.com
- 無料枠: 月125,000リクエスト
- 本システムでの役割: iPhone Shortcuts と GitHub API の中継サーバー

### Google Cloud Console
Google が提供するクラウドサービス管理画面。OAuth2 の認証情報（クライアントID/シークレット）の発行に使用。
- 公式サイト: https://console.cloud.google.com
- 本システムでの役割: Google Drive API の認証情報管理

### Google Drive API
Google Drive をプログラムから操作するためのAPI。ファイルの作成・読み取り・更新が可能。
- 本システムでの役割: ディクテーションログの保存先

### Gemini API
Google が提供する AI API。テキスト生成だけでなく、画像認識・文字起こしも可能。
- 公式サイト: https://aistudio.google.com
- 無料枠: 1,500リクエスト/日（無料プロジェクトの場合）
- 本システムでの役割: 手書き画像の文字起こし（OCR）

### iPhone Shortcuts（ショートカット）
iPhone に標準搭載されているオートメーションアプリ。音声入力・カメラ・HTTP通信など様々な操作を組み合わせてショートカットを作成できる。
- 本システムでの役割: ユーザーのインターフェース（音声入力・撮影・API送信）

---

## 5. システム全体構成

### 構成図

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【音声入力フロー】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📱 iPhone Shortcuts
  ┌─────────────────────┐
  │ 1. テキストを音声入力  │
  │ 2. 日付をフォーマット  │
  │ 3. POST（フォーム形式）│
  └──────────┬──────────┘
             │ HTTP POST
             ▼
  ☁️  Netlify Functions（dictation.js）
  ┌─────────────────────┐
  │ フォームデータを受取   │
  │ JSON に変換          │
  └──────────┬──────────┘
             │ HTTP POST（JSON）
             ▼
  🐙 GitHub API
  ┌─────────────────────┐
  │ repository_dispatch  │
  │ イベントを発火        │
  └──────────┬──────────┘
             │ トリガー
             ▼
  ⚙️  GitHub Actions（dictation.yml）
  ┌─────────────────────┐
  │ Python スクリプト実行 │
  │ upload_to_drive.py   │
  └──────────┬──────────┘
             │ Google Drive API
             ▼
  📂 Google Drive
  ┌─────────────────────┐
  │ dictations/          │
  │   2026/              │
  │     2026-03/         │
  │       2026-03-30.txt │
  └─────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【手書きOCRフロー】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📱 iPhone Shortcuts
  ┌─────────────────────┐
  │ 1. 写真を撮る         │
  │ 2. 2560pxにリサイズ    │
  │ 3. Base64エンコード   │
  │ 4. POST（JSON形式）   │
  └──────────┬──────────┘
             │ HTTP POST（image_base64）
             ▼
  ☁️  Netlify Functions（ocr.js）
  ┌─────────────────────┐
  │ 画像を受取            │
  │ Gemini API で OCR    │← 🤖 Gemini AI
  │ テキストのみ抽出      │
  └──────────┬──────────┘
             │ HTTP POST（text のみ）
             ▼
  🐙 GitHub API → ⚙️ GitHub Actions → 📂 Google Drive
  （音声入力フローと同じ）
```

### ポイント
- **OCR は Netlify で実行する**: 画像データを GitHub API に送ると 422 エラー（ペイロード上限超過）になるため、Netlify 側で Gemini OCR を実行してテキストのみ GitHub に送る
- **音声入力は Netlify 経由**: iPhone Shortcuts は複雑な JSON（ネスト構造）を直接作れないため、Netlify でフォームデータを JSON に変換する

---

## 6. 使用サービスと選定理由

### GitHub Actions
- **選定理由**: 無料枠が充実、コードと同じリポジトリで管理できる、`repository_dispatch` で外部から HTTP トリガーできる
- **代替案**: AWS Lambda（設定が複雑）、Google Cloud Functions（課金アカウント必要）

### Netlify Functions
- **選定理由**: iPhone Shortcuts の JSON 制限を回避できる、無料枠が充実、GitHub と自動連携
- **代替案**: AWS API Gateway（高コスト）、直接 GitHub API（Shortcuts の制限で不可）

### Google Drive（OAuth2 + refresh_token）
- **選定理由**: 個人の Google Drive に書き込める唯一の方法
- **なぜサービスアカウントを使わないか**: サービスアカウントは独自のストレージクォータを持てないため、個人の Google Drive に書き込めない（共有ドライブが必要になり有料）

### Gemini API（無料プロジェクト）
- **選定理由**: 無料枠が充実、日本語手書き認識精度が高い
- **重要な注意**: APIキーは課金プロジェクトではなく**無料プロジェクト（Default Gemini Project）**で作成する必要がある

---

## 7. ファイル構成

```
dictation-log/
├── .github/
│   └── workflows/
│       ├── dictation.yml      # 音声入力 & OCR → Google Drive
│       └── weekly-summary.yml # 週次サマリー（未実装）
├── netlify/
│   └── functions/
│       ├── dictation.js       # 音声入力の中継（フォーム→JSON変換）
│       └── ocr.js             # OCR処理（Gemini呼び出し）+ 中継
├── scripts/
│   ├── drive_helper.py        # Google Drive 共通ライブラリ
│   ├── upload_to_drive.py     # 音声入力エントリポイント
│   ├── ocr_to_drive.py        # OCRエントリポイント（現在未使用）
│   └── auth_setup.py          # ローカルで refresh_token を取得するツール
├── netlify.toml               # Netlify の設定
├── requirements.txt           # Python 依存ライブラリ
└── .gitignore                 # credentials.json 等を除外
```

### 共通化の設計方針
- `drive_helper.py`: Google Drive への接続・フォルダ作成・ファイル保存のロジックを共通化
- `upload_to_drive.py`: 環境変数の読み取りと `save_to_drive()` の呼び出しのみ（シンプル）
- OCR も最終的には `dictation` イベントで同じワークフローを使用（コード重複なし）

---

## 8. 認証・セキュリティ設計

### GitHub Secrets
| Secret 名 | 用途 |
|-----------|------|
| `GOOGLE_CLIENT_ID` | Google OAuth2 クライアントID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 シークレット |
| `GOOGLE_REFRESH_TOKEN` | Google Drive アクセス用長期トークン |
| `GOOGLE_DRIVE_FOLDER_ID` | 保存先フォルダのID |

### Netlify 環境変数
| 変数名 | 用途 |
|--------|------|
| `GITHUB_PAT` | GitHub API を呼び出すための Personal Access Token |
| `GEMINI_API_KEY` | Gemini OCR API キー |

### リポジトリが Public でも安全な理由
- Secrets の値はコードに書かれていない（`${{ secrets.XXX }}` という参照のみ）
- Secrets は GitHub Actions 実行時のみ環境変数として展開される
- ログにも `***` でマスクされる
- `credentials.json` / `token.json` は `.gitignore` で除外済み

---

## 9. Google Drive のフォルダ構成

```
dictation-log/        ← 手動作成（GOOGLE_DRIVE_FOLDER_ID に設定）
└── dictations/       ← 自動作成
    └── 2026/         ← 自動作成
        └── 2026-03/  ← 自動作成
            └── 2026-03-30.txt  ← 自動作成・追記
```

### ファイルフォーマット
```
# 2026-03-30 ディクテーションログ

[2026-03-30 08:30:00] (iPhone Siri)
今日の振り返りテキスト
---

[2026-03-30 20:00:00] (iPhone OCR)
手書き文字起こし結果
---
```

---

## 10. iPhone Shortcuts の設定

### 音声入力ショートカット
```
アクション1: テキストを音声入力
  - 言語: 日本語
  - 聞き取りを停止: 停止後

アクション2: 日付を書式設定
  - 書式: カスタム（yyyy-MM-dd HH:mm:ss）

アクション3: URLの内容を取得
  - URL: https://[netlify-url]/.netlify/functions/dictation
  - 方法: POST
  - 本文を要求: フォーム
    - text      = 音声入力の出力（青いバッジ）
    - timestamp = フォーマット済みの日付（青いバッジ）
    - source    = iPhone Siri（テキスト）

アクション4: URLの内容を表示（デバッグ確認用）
```

### 手書きOCRショートカット
```
アクション1: 1枚の写真を背面カメラで撮る

アクション2: 写真を 2560 x 自動 のサイズに変更
  ※ 元サイズのままだとデータが大きすぎてエラーになる

アクション3: 日付を書式設定
  - 書式: カスタム（yyyy-MM-dd HH:mm:ss）

アクション4: 写真をBase64でエンコード
  ※ 入力は「サイズ変更済みの画像」を選択（写真そのものではない）

アクション5: URLの内容を取得
  - URL: https://[netlify-url]/.netlify/functions/ocr
  - 方法: POST
  - 本文を要求: JSON
    - image_base64 = Base64エンコードの出力（青いバッジ）
    - timestamp    = フォーマット済みの日付（青いバッジ）
    - source       = iPhone OCR（テキスト）

アクション6: URLの内容を表示（デバッグ確認用）
```

---

## 11. トラブルシューティング集

### GitHub Actions が起動しない
- **原因1**: Netlify の `GITHUB_PAT` が期限切れまたは未設定
  - GitHub → Settings → Developer settings で PAT を再発行し、Netlify 環境変数を更新
- **原因2**: PAT のスコープが不足
  - `repo` スコープが必要
- **原因3**: iPhone Shortcuts の JSON フォーマットエラー
  - Shortcuts は複雑な JSON（ネスト構造）を直接作れない → Netlify 経由にする

### Google Drive に書き込めない
- **原因1**: サービスアカウントを使っている
  - サービスアカウントは個人 Drive に書き込めない（共有ドライブが必要で有料）
  - → OAuth2 + refresh_token 方式を使う
- **原因2**: refresh_token が失効した
  - `auth_setup.py` を再実行して新しいトークンを取得し GitHub Secrets を更新
- **原因3**: Google Drive フォルダの共有設定が不足
  - サービスアカウントのメールアドレスに「編集者」権限を付与する

### Gemini API が 429 エラー（limit: 0）
- **原因**: APIキーが課金プロジェクトに紐付いている
  - 課金有効プロジェクトでは無料枠のクォータが 0 になる
  - → `https://aistudio.google.com/apikey` で**新しいプロジェクト**（Default Gemini Project）のキーを作成

### Gemini API が 404 エラー（モデルが見つからない）
- **原因**: 指定したモデル名が存在しない・または利用不可
  - → `https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY` でモデル一覧を確認
  - 現在使用中: `gemini-2.5-pro`

### Gemini API が 400 エラー（Base64デコード失敗）
- **原因**: `image_base64` フィールドに画像データではなくファイル名が送られている
  - Shortcuts で「Base64エンコード」アクションの出力ではなく、別の変数を設定している
  - → `image_base64` フィールドの値を「Base64エンコード」アクションの出力（青いバッジ）に設定

### 422 エラー（client_payload is too large）
- **原因**: iPhone の元サイズ画像をそのまま Base64 エンコードして GitHub API に送ろうとした
  - iPhone の写真は数MB あり、GitHub API のペイロード上限を超える
  - → Shortcuts で写真を **2560px にリサイズ**してから Base64 エンコードする
  - → さらに根本解決として、OCR を Netlify 側で実行してテキストのみ GitHub に送るよう変更

### 日付形式のエラー（Invalid isoformat string）
- **原因**: iPhone の日付フォーマットが `2026/3/30` などスラッシュ区切り
  - → `drive_helper.py` の `parse_timestamp()` で自動変換済み（スラッシュ・ゼロ埋めなし両対応）

### 日本語が文字化けする
- **原因**: Netlify がリクエストボディを Base64 エンコードする場合がある
  - → `event.isBase64Encoded` を確認して `Buffer.from(body, 'base64').toString('utf-8')` でデコード

### Netlify Function が「Internal Error」
- **原因1**: リクエストボディが大きすぎる
  - → OCR を Netlify 側で実行し、テキストのみ GitHub に送る構成に変更
- **原因2**: 環境変数が未設定
  - → 環境変数設定後は**必ず再デプロイ**が必要

### conda 環境で pip が動かない
- `pip install` ではなく `conda run -n devenv pip install -r requirements.txt` を使用
- または devenv 環境を activate した状態で実行

---

## 12. 運用コスト

| サービス | 無料枠 | 月間使用量（推定）| 課金リスク |
|---------|--------|----------------|-----------|
| GitHub Actions | 無制限（Public repo）| 30回/月 | なし |
| Netlify Functions | 125,000回/月 | 30回/月 | なし |
| Google Drive API | 無制限 | 30回/月 | なし |
| Gemini API | 1,500回/日 | 30回/月 | なし |

**個人のディクテーション用途では永続的に無料で運用できる。**

---

## 13. 今後の拡張アイデア

- [ ] 週次サマリーを Slack に通知（`weekly-summary.yml` のスタブ作成済み）
- [ ] X（Twitter）への自動投稿
- [ ] 複数言語対応（Gemini の OCR プロンプトを変更するだけ）
