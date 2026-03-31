---
title: 【完全無料】iPhone音声入力＋手書きOCRをGitHub Actions×Gemini AIでGoogle Driveに自動保存した話【Claude Codeで全部作った】
tags:
  - GitHubActions
  - Netlify
  - GeminiAPI
  - iPhoneShortcuts
  - ClaudeCode
---

## はじめに

毎日手書きでディクテーション（1日の振り返り）をしていますが、こんな課題がありました。

- 手書きだとデジタルデータとして残らない
- 忙しい日は書く時間が取れない

そこで「**iPhoneで話しかけるだけ**」「**手書きメモを写真で撮るだけ**」でGoogle Driveに自動保存されるシステムを作りました。

しかも**完全無料・サーバーなし**で動きます。さらにこのシステム、**Claude Code（AIコーディングエージェント）だけで全部実装**しました。後半ではClaude Codeをより使いこなすための教訓もまとめています。

## 作ったもの

| 機能 | 操作 |
|------|------|
| 音声入力ディクテーション | iPhoneに話しかける → Google Driveに自動保存 |
| 手書きOCRディクテーション | 手書きメモを撮影 → Gemini AIが文字起こし → 自動保存 |
| 日付別自動整理 | `2026/2026-03/2026-03-30.txt` の階層で整理 |
| 同日追記 | 同日に複数回記録しても同じファイルに追記 |

---

## システム構成

```
📱 iPhone Shortcuts
    ↓ HTTP POST
☁️  Netlify Functions（中継 + Gemini OCR）
    ↓ HTTP POST（JSON）
🐙 GitHub API（repository_dispatch）
    ↓ トリガー
⚙️  GitHub Actions（Python実行）
    ↓ Google Drive API
📂 Google Drive（日付別テキストファイル）
```

### 使用サービスと無料枠

| サービス | 役割 | 無料枠 | 月間使用量 |
|---------|------|--------|----------|
| GitHub Actions | Pythonスクリプト実行（サーバー代わり） | 無制限（Public repo） | 約30回 |
| Netlify Functions | 中継・OCR処理 | 125,000回/月 | 約30回 |
| Gemini API | 手書き文字起こし | 1,500回/日 | 約30回 |
| Google Drive | 保存先 | 15GB | 微量 |

**個人用途なら永続的に完全無料で運用できます。**

---

## 2つのフロー詳細

### フロー①：音声入力

```
iPhone Shortcuts
  1. テキストを音声入力（日本語）
  2. 日付をフォーマット（yyyy-MM-dd HH:mm:ss）
  3. POST → Netlify Functions /dictation
        ↓
Netlify Functions（dictation.js）
  - フォームデータをJSONに変換
  - GitHub API に POST
        ↓
GitHub Actions → upload_to_drive.py → Google Drive
```

**なぜNetlifyを中継するか？**
iPhone ShortcutsはネストしたJSON（`{"client_payload": {...}}`）を直接作れないため、Netlifyでフォームデータを変換します。

### フロー②：手書きOCR

```
iPhone Shortcuts
  1. 写真を撮る
  2. 2560pxにリサイズ（重要）
  3. Base64エンコード
  4. POST → Netlify Functions /ocr
        ↓
Netlify Functions（ocr.js）
  - Gemini APIで手書き文字起こし ← ここでOCR
  - テキストのみGitHub APIにPOST
        ↓
GitHub Actions → upload_to_drive.py → Google Drive
```

**なぜNetlifyでOCRするか？**
iPhone写真をBase64にすると数MBになり、GitHub APIのペイロード上限（数百KB）を超えて422エラーになります。Netlify側でOCRを実行してテキストのみ送ることで解決しました。

---

## コードのポイント

### Netlify Function（ocr.js）

```javascript
const GEMINI_MODEL = 'gemini-2.5-flash';

async function ocrWithGemini(imageBase64, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{
        parts: [
          { text: 'この画像に書かれている手書き文字をそのまま文字起こしてください。文字起こしの結果のみを返してください。余計な説明は不要です。' },
          { inline_data: { mime_type: 'image/jpeg', data: imageBase64 } }
        ]
      }]
    })
  });
  const result = await response.json();
  return result.candidates[0].content.parts[0].text.trim();
}

exports.handler = async (event) => {
  // Netlifyがボディをbase64エンコードする場合があるので要チェック
  const rawBody = event.isBase64Encoded
    ? Buffer.from(event.body, 'base64').toString('utf-8')
    : event.body;

  const { image_base64, timestamp, source } = JSON.parse(rawBody);
  const text = await ocrWithGemini(image_base64, process.env.GEMINI_API_KEY);

  // テキストのみGitHubに送信（画像は送らない）
  await fetch('https://api.github.com/repos/{owner}/{repo}/dispatches', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${process.env.GITHUB_PAT}`, ... },
    body: JSON.stringify({ event_type: 'dictation', client_payload: { text, timestamp, source } })
  });
};
```

### Google Drive 共通ライブラリ（drive_helper.py）

```python
def save_to_drive(text, timestamp, source, root_folder_id):
    """音声入力・OCR共通のGoogle Drive保存ロジック"""
    creds = get_credentials()
    service = build('drive', 'v3', credentials=creds)

    date_str = parse_timestamp(timestamp)  # "2026/3/30" → "2026-03-30"
    year = date_str[:4]
    month = date_str[:7]   # "2026-03"

    # dictations/2026/2026-03/ の階層を自動作成
    dictations_id = ensure_folder_exists(service, 'dictations', root_folder_id)
    year_id = ensure_folder_exists(service, year, dictations_id)
    month_id = ensure_folder_exists(service, month, year_id)

    filename = f"{date_str}.txt"
    file_id, existing_content = get_or_create_daily_file(service, month_id, filename, date_str)

    # 同日ファイルがあれば追記、なければ新規作成
    new_entry = f"[{timestamp}] ({source})\n{text}\n---\n\n"
    upload_or_update_file(service, month_id, filename, existing_content + new_entry, file_id)
```

### GitHub Actions ワークフロー

```yaml
on:
  repository_dispatch:
    types: [dictation]  # 音声入力・OCR両方がこのイベントを使用

jobs:
  upload:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - env:
          DICTATION_TEXT: ${{ github.event.client_payload.text }}
          DICTATION_TIMESTAMP: ${{ github.event.client_payload.timestamp }}
          DICTATION_SOURCE: ${{ github.event.client_payload.source }}
          GOOGLE_CLIENT_ID: ${{ secrets.GOOGLE_CLIENT_ID }}
          GOOGLE_CLIENT_SECRET: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          GOOGLE_REFRESH_TOKEN: ${{ secrets.GOOGLE_REFRESH_TOKEN }}
          GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}
        run: cd scripts && python upload_to_drive.py
```

**`cd scripts &&` が必要な理由：** `drive_helper.py` を相対インポートするため、スクリプトのディレクトリを作業ディレクトリにする必要があります。

---

## ハマったポイント集

実装中に遭遇したエラーと解決策をまとめます。

### 1. Gemini APIが429エラー（limit: 0）

**原因：** APIキーを課金プロジェクトで作成すると、無料枠のクォータが0になります。

**解決策：** [Google AI Studio](https://aistudio.google.com/apikey) で**「新しいプロジェクトを作成」**を選択し、課金なしの「Default Gemini Project」でAPIキーを作成します。既存の課金プロジェクトを選ばないことが重要。

### 2. 画像送信で422エラー（client_payload is too large）

**原因：** iPhoneの写真をBase64にするとMB単位になり、GitHub APIのペイロード上限超過。

**解決策：**
1. Shortcutsで**2560pxにリサイズ**してからBase64エンコード
2. さらに根本解決として、OCRをNetlify側で実行し**テキストのみGitHubに送る**

### 3. 日本語が文字化け（Netlify）

**原因：** Netlifyがリクエストボディをbase64エンコードする場合があります。

**解決策：**
```javascript
const rawBody = event.isBase64Encoded
  ? Buffer.from(event.body, 'base64').toString('utf-8')
  : event.body;
```

### 4. 日付形式エラー（Invalid isoformat string）

**原因：** iPhoneの日付フォーマットが `2026/3/30`（スラッシュ区切り・ゼロ埋めなし）。

**解決策：** Pythonで正規化。

```python
def parse_timestamp(timestamp: str) -> str:
    date_part = timestamp.split(' ')[0]
    date_part = date_part.replace('/', '-')
    parts = date_part.split('-')
    return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
```

### 5. Google Drive認証でサービスアカウントNG

**原因：** サービスアカウントは独自のストレージクォータを持ち、個人のGoogle Driveに書き込めません（共有ドライブが必要で有料）。

**解決策：** OAuth2 + refresh_token方式で個人アカウントとして認証します。

```python
from google.oauth2.credentials import Credentials

def get_credentials():
    return Credentials(
        token=None,
        refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
```

---

## Claude Codeで作って気づいた教訓

このシステムはClaude Code（AIコーディングエージェント）で実装しました。その過程で気づいた「もっとこうすればよかった」をまとめます。

### 今回の非効率の構造

```
Claude Codeが把握できる範囲
└── ローカルファイル（コード、設定）

外部サービス（Claude Codeが直接触れなかった範囲）
└── Netlify Dashboard、GitHub Secrets、Google Cloud Console
    → 人間がブラウザ操作 → 結果をチャット報告 → 次の指示 ...
```

この往復に時間がかかりました。**「ブラウザでしか操作できないサービスはAIエージェントとの相性が悪い」**のです。

### 改善策① CLAUDE.md で前提知識を永続化

毎セッション「このプロジェクトはNetlifyを中継して...」という説明が必要でした。CLAUDE.mdに書けばセッションをまたいで不要になります。

```markdown
# dictation-log

## アーキテクチャ
iPhone Shortcuts → Netlify Functions → GitHub API → GitHub Actions → Google Drive

## テストの流れ
1. Netlifyローカル: `cd netlify && netlify dev`
2. ActionsテスT: `gh workflow run dictation.yml`

## 環境変数の場所
- GITHUB_PAT, GEMINI_API_KEY → Netlify環境変数
- GOOGLE_* → GitHub Secrets
```

### 改善策② gh CLI + MCP でブラウザ操作を排除

`gh` CLIとGitHub MCPを使えば、Claude Codeが直接GitHub操作できます。

```bash
# 今回これを使っていれば、ブラウザ操作が不要だった
gh secret set GOOGLE_CLIENT_ID --body "xxxx"  # Secrets登録
gh workflow run dictation.yml                  # Actions手動テスト
gh run view --log-failed                       # エラーログ取得
```

**.claude/.mcp.json:**
```json
{
  "mcpServers": {
    "github": {
      "command": "gh",
      "args": ["mcp", "serve"],
      "env": { "GITHUB_TOKEN": "$GITHUB_TOKEN" }
    }
  }
}
```

Netlify MCPも公式サポートあり。`netlify env:set KEY value` でClaude Codeが直接環境変数を設定できます。

### 改善策③ Hooks で事故を防ぐ

`.claude/settings.json` にHooksを設定すれば、認証情報ファイルのコミットを自動ブロックできます。

```json
{
  "permissions": {
    "deny": ["Edit(.env)", "Edit(credentials.json)", "Edit(token.json)"]
  },
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash(git push *)",
      "hooks": [{
        "type": "command",
        "command": "git diff --cached --name-only | grep -E '(credentials|token|.env)' && exit 2 || exit 0"
      }]
    }]
  }
}
```

### 改善策④ Skills で繰り返し操作をコマンド化

「Netlify再デプロイ」「Actionsログ確認」を何度も繰り返しました。Skillにすれば `/check-deployment` 一発です。

**.claude/skills/check-deployment/SKILL.md:**
```markdown
---
name: check-deployment
description: Netlify + GitHub Actionsのデプロイ状態確認
allowed-tools: Bash(netlify *), Bash(gh *)
---

1. `netlify status` でサイト状態確認
2. `gh run list --limit 5` でActions直近5件確認
3. 失敗ランがあれば `gh run view <id> --log-failed` でエラー取得
```

### 今回 vs 理想形

| 今回やったこと | Claude Code活用の理想形 |
|-------------|---------------------|
| ブラウザでNetlify環境変数設定 | `netlify env:set KEY value` をClaude Codeが実行 |
| ブラウザでGitHub Secrets登録 | `gh secret set KEY --body value` をClaude Codeが実行 |
| ActionsエラーをスクショでAIに報告 | `gh run view --log-failed` でClaude Codeが直接取得 |
| 機微情報確認を手動で依頼 | Hookで自動ブロック |

---

## まとめ

### システム面

- **iPhone → Google Drive の自動化は完全無料で実現できる**
- Netlifyを中継サーバーとして使うことで、Shortcutsの制限（ネストJSON不可・ペイロード上限）を回避できる
- OCRはNetlify側で実行し、テキストのみGitHubに送ることが重要
- Gemini APIは**課金プロジェクトではなく無料プロジェクト**のキーを使うこと

### Claude Code活用面

- **「外部サービスをCLI化すること」がAIエージェント活用の鍵**
- CLAUDE.md でプロジェクト前提知識を永続化する
- gh CLI + MCP でブラウザ操作をAIエージェントに委譲する
- Hooks で事故を自動防止する
- Skills で繰り返し操作をコマンド化する

コードは GitHub で公開しています。

https://github.com/risong-ku/dictation-log
