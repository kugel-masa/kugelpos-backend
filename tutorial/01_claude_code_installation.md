# Claude Code インストール手順

このガイドでは、Anthropic 公式の AI 支援開発 CLI である Claude Code のインストール方法を説明します。

## 前提条件

- macOS、Linux、または Windows（WSL2）
- インターネット接続
- ターミナルアクセス

## インストール方法

### 方法1: Homebrew を使用（macOS/Linux - 推奨）

```bash
# Homebrew 経由でインストール
brew install claude

# インストールの確認
claude --version
```

### 方法2: npm を使用（クロスプラットフォーム）

```bash
# npm 経由でグローバルインストール
npm install -g @anthropics/claude-code

# インストールの確認
claude --version
```

### 方法3: pip を使用（Python）

```bash
# pip 経由でインストール
pip install claude-code

# インストールの確認
claude --version
```

### 方法4: バイナリをダウンロード（手動インストール）

1. Claude Code の公式リリースページにアクセス:
   - GitHub: <https://github.com/anthropics/claude-code/releases>

2. お使いのプラットフォームに適したバイナリをダウンロード:
   - macOS: `claude-code-macos-arm64` または `claude-code-macos-x64`
   - Linux: `claude-code-linux-x64`
   - Windows: `claude-code-windows-x64.exe`

3. バイナリを実行可能にする（macOS/Linux）:

   ```bash
   chmod +x claude-code-*
   ```

4. PATH 内のディレクトリに移動:

   ```bash
   # macOS/Linux
   sudo mv claude-code-* /usr/local/bin/claude

   # またはローカル bin に追加
   mv claude-code-* ~/.local/bin/claude
   ```

## 認証設定

インストール後、Anthropic API キーで認証します:

```bash
# Claude Code を起動（初回実行時に API キーの入力を求められます）
claude

# または環境変数で API キーを設定
export ANTHROPIC_API_KEY="your-api-key-here"
```

API キーの取得方法:

1. <https://console.anthropic.com/> にアクセス
2. サインアップまたはログイン
3. 「API Keys」に移動
4. 新しい API キーを作成
5. 安全な場所にコピーして保存

## 設定

Claude Code は `~/.claude/` ディレクトリに設定を保存します:

```bash
# 設定を表示
cat ~/.claude/config.json

# 設定を表示
cat ~/.claude/settings.json
```

### 一般的な設定オプション

`~/.claude/settings.json` を作成または編集:

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.7,
  "max_tokens": 4096
}
```

## 基本的な使い方

```bash
# 現在のディレクトリで Claude Code を起動
claude

# 特定のプロンプトで起動
claude "このコードをリファクタリングするのを手伝ってください"

# 特定のディレクトリで実行
claude --directory /path/to/project

# 特定のモデルを使用
claude --model claude-opus-4-20250514
```

## 動作確認

インストールが正しく動作しているか確認:

```bash
# バージョンチェック
claude --version

# ヘルプを確認
claude --help

# 簡単なプロンプトでテスト
claude "こんにちは、手伝ってもらえますか？"
```

## プロジェクト固有の設定

各プロジェクトに `.claude/` ディレクトリを追加して、プロジェクト固有の設定ができます:

```bash
# プロジェクト固有の設定を作成
mkdir -p .claude
cat > .claude/settings.local.json << 'EOF'
{
  "model": "claude-sonnet-4-5-20250929",
  "context_files": ["README.md", "CLAUDE.md"]
}
EOF
```

## トラブルシューティング

### 問題: コマンドが見つからない

**解決方法**: インストールディレクトリが PATH に含まれていることを確認:

```bash
# ~/.bashrc または ~/.zshrc に追加
export PATH="$PATH:$HOME/.local/bin"

# シェル設定を再読み込み
source ~/.bashrc  # または source ~/.zshrc
```

### 問題: API キーが認識されない

**解決方法**: API キーを明示的に設定:

```bash
# 一時的（現在のセッション）
export ANTHROPIC_API_KEY="your-api-key"

# 永続的（~/.bashrc または ~/.zshrc に追加）
echo 'export ANTHROPIC_API_KEY="your-api-key"' >> ~/.bashrc
source ~/.bashrc
```

### 問題: 接続エラー

**解決方法**: インターネット接続とファイアウォール設定を確認:

```bash
# API 接続をテスト
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":1024,"messages":[{"role":"user","content":"Hello"}]}'
```

## 次のステップ

Claude Code のインストール後:

1. [Specify インストールガイド](02_specify_installation.md)を読む
2. Spec Kit でプロジェクトを初期化
3. AI 支援開発を開始

## 追加リソース

- 公式ドキュメント: <https://docs.anthropic.com/claude-code>
- GitHub リポジトリ: <https://github.com/anthropics/claude-code>
- コミュニティフォーラム: <https://community.anthropic.com/>
- API ドキュメント: <https://docs.anthropic.com/api>

## アンインストール

Claude Code をアンインストールする必要がある場合:

```bash
# Homebrew
brew uninstall claude

# npm
npm uninstall -g @anthropics/claude-code

# pip
pip uninstall claude-code

# 手動インストール
sudo rm /usr/local/bin/claude
rm -rf ~/.claude
```

---

**注意**: このガイドは 2025年11月時点の Claude Code に基づいています。将来のバージョンではコマンドや手順が変更される可能性があります。最新の情報については、常に公式ドキュメントを参照してください。
