# dictation-log 開発 総括

Claude Code を使って iPhone → Netlify → GitHub Actions → Google Drive の自動化システムを構築した際の教訓。
「外部サービスとの連携でClaude Codeをどう活用するか」の観点でまとめる。

---

## 今回の非効率の本質

```
Claude Codeが把握できる範囲
└── ローカルファイル（コード、設定）

外部サービス（Claude Codeが直接触れなかった範囲）
└── Netlify Dashboard、GitHub Secrets、Google Cloud Console
    → あなたが手動でブラウザ操作 → 結果をチャットで報告 → 次の指示 ...
```

この往復が遅延の主因。ブラウザ操作をCLI / MCPで代替するほど、AIエージェントの真価が出る。

---

## 1. CLAUDE.md ── 「毎回説明しなくていい前提知識」を書く

毎セッション「このプロジェクトはNetlifyを中継してGitHub Actionsへ...」という文脈説明が必要だった。
CLAUDE.md にアーキテクチャと運用手順を書けば、セッションをまたいでも説明不要になる。

**今回のプロジェクトに適切だったCLAUDE.md:**

```markdown
# dictation-log

## アーキテクチャ
iPhone Shortcuts → Netlify Functions → GitHub API → GitHub Actions → Google Drive

## 開発・テストの流れ
1. Netlifyのローカルテスト: `cd netlify && netlify dev`
2. GitHub Actionsの手動テスト: `gh workflow run dictation.yml`
3. Netlify再デプロイ: `netlify deploy --prod`

## 環境変数の場所
| 変数 | 設定場所 |
|------|---------|
| GITHUB_PAT, GEMINI_API_KEY | Netlify → Site config → Env vars |
| GOOGLE_* | GitHub → Settings → Secrets → Actions |

## 注意事項
- credentials.json / token.json は .gitignore 済み・絶対コミット不可
- Geminiは課金プロジェクトではなく "Default Gemini Project" のキーを使うこと（free tier）
- 画像送信は2560pxにリサイズしてからBase64送信
```

---

## 2. Skills ── 繰り返したデバッグ操作をコマンド化する

「Netlifyの環境変数を追加して再デプロイ」「GitHub Actionsのログ確認」を何度も繰り返した。
Skillにすれば `/check-deployment` 一発になる。

**.claude/skills/check-deployment/SKILL.md:**

```markdown
---
name: check-deployment
description: Netlify最新デプロイとGitHub Actions直近ワークフローの状態確認
allowed-tools: Bash(netlify *), Bash(gh *)
---

以下を順に確認してステータスをまとめる:
1. `netlify status` でサイト状態確認
2. `gh run list --limit 5` でActions直近5件のステータス確認
3. 最新の失敗ランがあれば `gh run view <id> --log-failed` でエラー詳細取得
```

---

## 3. MCP ── ブラウザ操作をClaude Codeに委譲する

今回の最大のボトルネックは「外部サービスの設定変更はブラウザで人間が行う」だった。
MCP（Model Context Protocol）でCLIを接続すれば、Claude Codeが直接操作できる。

**接続できた外部サービス:**

| サービス | MCP経由でできること | 今回どこで詰まったか |
|---------|-----------------|----------------|
| **GitHub MCP** | Secrets登録、Actionsトリガー、ログ取得 | Secrets登録・ワークフロー確認 |
| **Netlify MCP** | 環境変数設定、デプロイトリガー | 環境変数追加・再デプロイ |

**.claude/.mcp.json（プロジェクトに置く）:**

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

GitHubは `gh` CLIがあるため、今すぐ使える。

```bash
# 今回これがあれば：
gh secret set GOOGLE_CLIENT_ID --body "xxxx"  # Claude Codeが直接実行可能
gh workflow run dictation.yml                  # 手動テストもClaude Code経由
gh run view --log-failed                       # エラーログも即取得
```

Netlify MCP は公式サポート中。`NETLIFY_AUTH_TOKEN` さえあれば環境変数設定もデプロイもClaude Code一発。

---

## 4. Hooks ── 失敗を事前に防ぐ仕組み

「認証情報を含むファイルをpushしそうになる」リスクがあった。Hookで自動ブロックできる。

**.claude/settings.json:**

```json
{
  "permissions": {
    "allow": [
      "Bash(git add *)", "Bash(git commit *)",
      "Bash(gh workflow run *)", "Bash(gh secret set *)",
      "Bash(netlify deploy *)", "Bash(netlify env:set *)"
    ],
    "deny": [
      "Bash(git push --force *)",
      "Edit(.env)", "Edit(credentials.json)", "Edit(token.json)"
    ]
  },
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash(git push *)",
      "hooks": [{
        "type": "command",
        "command": "git diff --cached --name-only | grep -E '(credentials|token|.env)' && echo 'BLOCKED: sensitive file detected' && exit 2 || exit 0"
      }]
    }]
  }
}
```

---

## 5. 今回積み上げておくべきだった再利用資産

```
~/.claude/skills/                   ← ユーザーレベル（全プロジェクトで使える）
├── check-github-actions/           "gh run list" + エラーログ取得
├── setup-netlify-env/              環境変数一括設定 + 再デプロイ
└── security-scan/                  機微情報チェック（今回最後にやったやつ）

~/.claude/CLAUDE.md                 ← 全プロジェクト共通の個人ルール
├── 認証情報ファイルは絶対コミット禁止
├── push前は必ずgit statusで確認
└── GitHub/Netlifyの操作はgh CLI / netlify CLIを優先使用

~/.claude/projects/.../memory/      ← 自動蓄積される教訓（プロジェクト固有の学習）
```

---

## 今回 vs 次回の理想形

| 今回やったこと | 次回の理想形 |
|-------------|------------|
| ブラウザでNetlify環境変数設定 | `netlify env:set KEY value` をClaude Codeが実行 |
| ブラウザでGitHub Secrets登録 | `gh secret set KEY --body value` をClaude Codeが実行 |
| Actionsエラーをスクショで報告 | `gh run view --log-failed` でClaude Codeが直接取得 |
| Netlify再デプロイを手動実行 | `/deploy` スキルで完結 |
| push前の機微情報確認を依頼 | Hookで自動ブロック |

---

## 核心的な教訓

**「外部サービスをCLI化すること」がAIエージェント活用の鍵。**

ブラウザでしか操作できないサービスはAIエージェントとの相性が悪い。
`gh` CLI・`netlify` CLI・MCP Serverで「Claudeが直接触れる範囲」を広げるほど、
人間のブラウザ往復が減り、AIエージェントの真価が出る。

### 今回蓄積されたプロジェクト固有の教訓（メモリに保存済み）

- Gemini APIは課金プロジェクトではなく「Default Gemini Project」のキーを使う（free tier確保）
- iPhone Shortcutsから大きな画像をGitHub APIに送ると422エラー → Netlifyで処理してテキストのみ送る
- GitHub ActionsでPythonスクリプトを実行する際は `cd scripts &&` が必要（相対importのため）
- 日付フォーマットは `yyyy/M/d` → `yyyy-MM-dd` への変換処理が必要
- Netlifyの環境変数変更後は必ず「Trigger deploy」で再デプロイ
