# Spec Kit (Specify) インストールと初期化手順

このガイドでは、仕様駆動型 AI 開発のための GitHub の Spec Kit のインストールと初期化方法を説明します。

## 前提条件

- Python 3.8 以上
- Git がインストールされ設定済み
- Claude Code がインストール済み（[Claude Code インストールガイド](01_claude_code_installation.md)参照）
- `uv` または `uvx` パッケージマネージャー（推奨）

## Spec Kit とは？

Spec Kit は、GitHub のオープンソース仕様駆動開発（SDD）ツールキットです。以下のワークフローで開発を進めます：

1. 最初に仕様を書く
2. AI が実装計画を生成
3. 実行可能なタスクに分解
4. AI がコードを実装

### コアワークフロー

```
Specify（仕様化） → Plan（計画） → Tasks（タスク化） → Implement（実装）
```

## uv のインストール（パッケージマネージャー）

まず、Spec Kit に推奨されるパッケージマネージャー `uv` をインストールします：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# インストールの確認
uv --version
```

## Specify CLI のインストール

### グローバルインストール（推奨）

すべてのプロジェクトで使用できるように `specify-cli` をグローバルインストールします：

```bash
# GitHub リポジトリからインストール
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# インストールの確認
specify --help
```

Specify のバナーと利用可能なコマンドが表示されるはずです：

```
              ███████╗██████╗ ███████╗ ██████╗██╗███████╗██╗   ██╗
              ...
              GitHub Spec Kit - Spec-Driven Development Toolkit
```

### 代替方法: インストールせずに実行

グローバルインストールせずに Specify を実行することもできます：

```bash
# uvx で直接実行
uvx --from git+https://github.com/github/spec-kit.git specify --help
```

## システムチェック

プロジェクトを初期化する前に、必要なツールがすべてインストールされているか確認します：

```bash
# システムチェックを実行
specify check
```

期待される出力：

- ✅ Git version control（利用可能）
- ✅ Claude Code（利用可能）
- ✅ その他の AI コーディングツール（インストール済みの場合）

## プロジェクトの初期化

### 新規プロジェクト

Spec Kit で新しいプロジェクトを作成する場合：

```bash
# Claude Code で新しいプロジェクトを作成
specify init my-project --ai claude

# プロジェクトに移動
cd my-project
```

### 既存プロジェクト（現在の場所で初期化）

この Kugelpos プロジェクトでは、既存のリポジトリに Spec Kit を初期化します：

```bash
# プロジェクトルートに移動
cd /home/masa/proj/kugelpos-public/worktree/ai-coding-lesson

# 現在のディレクトリで初期化
specify init --here --ai claude
```

**警告**: これによりテンプレートファイルが既存のコンテンツとマージされます。プロンプトが表示されたら：

```
Warning: Current directory is not empty (15 items)
Template files will be merged with existing content and may overwrite existing files
Do you want to continue? [y/N]:
```

`y` を入力して続行します。

## インストールされる内容

初期化後、Spec Kit は以下を追加します：

### 1. コマンドファイル

`.claude/commands/` に配置されます：

- `speckit.constitution.md` - プロジェクトの原則とガバナンス
- `speckit.specify.md` - 機能仕様を作成
- `speckit.clarify.md` - 曖昧な要件を明確化
- `speckit.plan.md` - 実装計画を生成
- `speckit.tasks.md` - タスクに分解
- `speckit.implement.md` - 実装を実行
- `speckit.analyze.md` - 一貫性分析
- `speckit.checklist.md` - 品質チェックリスト
- `speckit.taskstoissues.md` - タスクを GitHub Issue に変換

### 2. ディレクトリ構造

```
.specify/
├── memory/
│   └── constitution.md          # プロジェクト憲章
└── templates/
    ├── spec-template.md         # 仕様テンプレート
    ├── plan-template.md         # 実装計画テンプレート
    ├── tasks-template.md        # タスクテンプレート
    └── checklist-template.md    # チェックリストテンプレート

specs/
└── (ここに機能仕様が作成されます)
```

### 3. スクリプト（該当する場合）

自動化用のシェルスクリプト（プラットフォームにより異なります）：

- `init.sh` / `init.bat`
- `plan.sh` / `plan.bat`
- など

## 利用可能なスラッシュコマンド

初期化後、Claude Code で以下のコマンドが使用できます：

### メインワークフローコマンド

1. `/speckit.constitution` - プロジェクト原則を確立
2. `/speckit.specify` - ベースライン仕様を作成
3. `/speckit.plan` - 実装計画を作成
4. `/speckit.tasks` - 実行可能なタスクを生成
5. `/speckit.implement` - 実装を実行

### 拡張コマンド（オプション）

- `/speckit.clarify` - 曖昧な領域を明確化する質問（`/speckit.plan` の前に使用）
- `/speckit.analyze` - クロスアーティファクト一貫性レポート（`/speckit.tasks` の後に使用）
- `/speckit.checklist` - 品質チェックリストを生成（`/speckit.plan` の後に使用）
- `/speckit.taskstoissues` - タスクを GitHub Issue に変換

## 確認

インストールの確認：

```bash
# インストールされたコマンドを確認
ls -la .claude/commands/

# テンプレートを確認
ls -la .specify/templates/

# 憲章テンプレートを表示
cat .specify/memory/constitution.md
```

## セキュリティの考慮事項

`.claude/` ディレクトリには以下が含まれる可能性があります：

- 認証情報
- API キー
- 個人設定

**推奨**: `.gitignore` に追加：

```bash
# .gitignore に追加
echo ".claude/settings.local.json" >> .gitignore
echo ".claude/*.secret" >> .gitignore
```

## インストール後の最初のステップ

### 1. プロジェクト憲章を作成

```bash
# Claude Code で実行：
/speckit.constitution
```

これにより以下が確立されます：

- コア原則（変更不可のルール）
- アーキテクチャ標準
- テスト要件
- ガバナンスポリシー

Kugelpos の憲章には以下が含まれます：

- マイクロサービスアーキテクチャ
- テストファースト開発
- サーキットブレーカーパターン
- イベント駆動通信
- プラグインアーキテクチャ
- 可観測性標準

### 2. 最初の仕様を作成

```bash
# Claude Code で実行：
/speckit.specify

# 例：
/speckit.specify JWT トークンを使用したユーザー認証を追加
```

### 3. 実装計画を生成

```bash
# Claude Code で実行：
/speckit.plan
```

### 4. タスクに分解

```bash
# Claude Code で実行：
/speckit.tasks
```

### 5. 実装

```bash
# Claude Code で実行：
/speckit.implement
```

## ワークフロー例

新機能を追加する完全な例：

```bash
# 1. Claude Code を起動
claude

# 2. 仕様を作成
/speckit.specify 注文確認用のメール通知システムを追加

# 3. 曖昧さを明確化（オプション）
/speckit.clarify

# 4. 実装計画を作成
/speckit.plan

# 5. 品質チェックリストを生成（オプション）
/speckit.checklist

# 6. タスクを生成
/speckit.tasks

# 7. 一貫性を分析（オプション）
/speckit.analyze

# 8. 実装
/speckit.implement

# 9. GitHub Issue に変換（オプション）
/speckit.taskstoissues
```

## Spec Kit の更新

最新バージョンに更新するには：

```bash
# specify-cli を更新
uv tool upgrade specify-cli --from git+https://github.com/github/spec-kit.git

# プロジェクトテンプレートを更新
specify init --here --force --ai claude
```

## 設定

### プロジェクト固有の設定

プロジェクト固有の設定用に `.specify/config.json` を作成：

```json
{
  "ai_assistant": "claude",
  "constitution_version": "1.0.0",
  "default_branch": "main",
  "spec_directory": "specs"
}
```

### AI アシスタントの選択

Specify は複数の AI アシスタントをサポートしています：

- `claude` - Claude Code（このプロジェクトに推奨）
- `copilot` - GitHub Copilot
- `gemini` - Google Gemini CLI
- `cursor` - Cursor IDE
- その他

## トラブルシューティング

### 問題: Claude Code にコマンドが表示されない

**解決方法**: Claude Code を再起動してコマンドを再読み込み：

```bash
# Claude Code を終了（Ctrl+C または Ctrl+D）
# その後再起動
claude
```

### 問題: テンプレートファイルが上書きされた

**解決方法**: Spec Kit は既存ファイルとマージします。git diff で確認：

```bash
# 変更を確認
git diff .specify/
git diff .claude/

# 必要に応じて復元
git checkout -- .specify/memory/constitution.md
```

### 問題: 憲章テンプレートが入力されていない

**解決方法**: 憲章コマンドを実行：

```bash
# Claude Code で
/speckit.constitution
```

### 問題: uvx コマンドが見つからない

**解決方法**: uv パッケージマネージャーをインストール：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # または source ~/.zshrc
```

## ベストプラクティス

1. **常に `/speckit.constitution` から始める** - 最初にプロジェクトルールを確立
2. **コード前に仕様を書く** - Specify → Plan → Tasks → Implement
3. **複雑な機能には clarify を使う** - 計画前に曖昧さを減らす
4. **ユーザーストーリーに分解** - 機能を独立してテスト可能にする
5. **実装前に analyze を実行** - 早期に不整合を発見
6. **タスクを Issue に変換** - GitHub で進捗を追跡

## Kugelpos との統合

Kugelpos POS バックエンドプロジェクトの場合：

1. **憲章は既に作成済み** - `.specify/memory/constitution.md` を参照
2. **確立された原則**：
   - マイクロサービスアーキテクチャ（必須・変更不可）
   - テストファースト開発（必須・変更不可）
   - サーキットブレーカーパターン（必須・変更不可）
   - イベント駆動通信
   - プラグインアーキテクチャ
   - 可観測性とデバッグ

3. **機能開発の準備完了**：

   ```bash
   # 例：新しい支払い方法を追加
   /speckit.specify カートサービスに QR コード決済方法を追加
   /speckit.plan
   /speckit.tasks
   /speckit.implement
   ```

## 追加リソース

- 公式ドキュメント: <https://github.com/github/spec-kit>
- Spec Kit ウェブサイト: <https://speckit.org/>
- GitHub ブログ: <https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/>
- コミュニティ例: <https://github.com/github/spec-kit/tree/main/examples>

## アンインストール

Spec Kit を削除するには：

```bash
# specify-cli をアンインストール
uv tool uninstall specify-cli

# プロジェクトファイルを削除（オプション）
rm -rf .specify/
rm -rf .claude/commands/speckit.*
rm -rf specs/
```

---

**注意**: このガイドは 2025年11月時点のものです。最新の更新と機能については、公式の Spec Kit リポジトリを参照してください。
