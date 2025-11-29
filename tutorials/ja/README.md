# Kugelpos AI コーディングチュートリアル

このディレクトリには、Kugelpos POS バックエンドプロジェクトで AI 支援開発ツールをセットアップするためのステップバイステップのチュートリアルが含まれています。

## 概要

Claude Code と GitHub の Spec Kit を使った仕様駆動型 AI 開発を学び、より速く、より信頼性の高い機能開発を実現します。

## チュートリアル内容

### 0. [事前準備](00_prerequisites.md)

ハンズオン参加前に必要な準備について説明します。

**必要なもの:**

- GitHub アカウント（Codespaces が利用できるもの）
- Visual Studio Code（事前インストール）
- Claude Code 利用ライセンス

**所要時間:** 10〜20分

---

### 1. [Claude Code インストール手順](01_claude_code_installation.md)

Anthropic 公式の AI 支援開発 CLI である Claude Code のインストールと設定方法を学びます。

**学習内容:**

- インストール方法（Homebrew、npm、pip、バイナリ）
- Anthropic API での認証
- 設定とカスタマイズ
- 基本的な使い方と動作確認
- よくある問題のトラブルシューティング

**所要時間:** 10〜15分

---

### 2. [Spec Kit インストールと初期化手順](02_specify_installation.md)

GitHub の Spec Kit をインストールし、Kugelpos プロジェクトで初期化する方法を学びます。

**学習内容:**

- `uv` パッケージマネージャーのインストール
- `specify-cli` のグローバルインストール
- プロジェクトの初期化
- スラッシュコマンドの理解
- 最初の仕様書の作成
- 仕様駆動開発のベストプラクティス

**所要時間:** 15〜20分

---

### 3. [ハンズオン: 取引キャンセル理由記録機能](03_hands_on_cancel_reason.md)

Spec Kit を使って実際に新機能を実装し、テストが全てパスするまでを体験します。

**学習内容:**

- Spec Kit の全ワークフロー実践（Specify → Plan → Tasks → Implement）
- マイクロサービス間連携の実装
- イベント駆動通信（Pub/Sub）の実装
- Repository パターンとプラグインアーキテクチャ
- テスト駆動開発（TDD）の実践
- デバッグとトラブルシューティング

**所要時間:** 3〜4時間

---

### 4. [上級ハンズオン: カテゴリ単位割引機能](04_hands_on_category_discount.md)

プラグインアーキテクチャとルールエンジンを活用した高度な機能実装を体験します。

**学習内容:**

- プラグインアーキテクチャの設計と実装
- Strategy パターンの実践
- ルールエンジンの構築
- 複雑なビジネスロジックの実装
- パフォーマンス最適化
- 拡張可能な設計の実現

**所要時間:** 8〜10時間

**推奨**: 中級ハンズオン完了後に挑戦

---

## クイックスタート

すぐに始めたい場合:

```bash
# 1. Claude Code をインストール（いずれかの方法を選択）
brew install claude                    # macOS/Linux (Homebrew)
npm install -g @anthropics/claude-code # クロスプラットフォーム (npm)

# 2. uv パッケージマネージャーをインストール
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Spec Kit をグローバルインストール
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# 4. システム要件をチェック
specify check

# 5. このプロジェクトで Spec Kit を初期化
cd /home/masa/proj/kugelpos-public/worktree/ai-coding-lesson
specify init --here --ai claude
```

## 仕様駆動開発（Spec-Driven Development）とは？

仕様駆動開発（SDD）は以下の手順で進める開発手法です：

1. **Specify（仕様化）** - 明確でテスト可能な仕様を最初に書く
2. **Plan（計画）** - 詳細な実装計画を生成
3. **Tasks（タスク化）** - 実行可能なタスクに分解
4. **Implement（実装）** - AI がコードを生成

この手法により以下が保証されます：

- コーディング前に明確な要件定義
- 機能間での一貫したアーキテクチャ
- テスト可能でメンテナンスしやすいコード
- 人間と AI の効果的な協働

## 利用可能な Spec Kit コマンド

初期化後、Claude Code で以下のコマンドが使用できます：

### コアワークフロー

```bash
/speckit.constitution  # プロジェクト原則を確立
/speckit.specify       # 機能仕様を作成
/speckit.plan          # 実装計画を生成
/speckit.tasks         # タスクに分解
/speckit.implement     # 実装を実行
```

### 拡張コマンド

```bash
/speckit.clarify       # 曖昧な要件を明確化
/speckit.analyze       # クロスアーティファクトの一貫性チェック
/speckit.checklist     # 品質チェックリストを生成
/speckit.taskstoissues # タスクを GitHub Issue に変換
```

## 例：新機能の追加

仕様駆動開発を使って新機能を追加する方法：

```bash
# 1. Claude Code を起動
claude

# 2. 仕様を作成
/speckit.specify トランザクションイベント用の Webhook 通知を追加

# 3. 実装計画を作成
/speckit.plan

# 4. タスクを生成
/speckit.tasks

# 5. 実装
/speckit.implement
```

## Kugelpos 固有の Constitution（憲章）

このプロジェクトには以下を定義した憲章があります：

### コア原則（必須・変更不可）

1. **マイクロサービスアーキテクチャ** - サービス分離、マルチテナンシー、Dapr 通信
2. **テストファースト開発** - TDD ワークフロー、pytest-asyncio、Red-Green-Refactor
3. **共有 Commons ライブラリ** - 一元化された抽象化、重複なし
4. **サーキットブレーカーパターン** - 3 回失敗でオープン、60 秒タイムアウト
5. **イベント駆動通信** - Pub/sub トピック、冪等性
6. **プラグインアーキテクチャ** - 支払い方法、レポートジェネレーター
7. **可観測性** - 構造化ログ、ヘルスエンドポイント

### 標準規約

- **データベース**: MongoDB（Motor 非同期ドライバー）、リポジトリパターン
- **API**: FastAPI（Pydantic スキーマ）、`/api/v1/` バージョニング
- **テスト**: pytest、統合テスト、契約テスト
- **コード品質**: PEP 8、型ヒント、ruff リンティング

詳細は [.specify/memory/constitution.md](../.specify/memory/constitution.md) を参照してください。

## 事前準備

ハンズオン参加前に、以下をご準備ください：

- **GitHub アカウント**: Codespaces が利用できるもの
- **Visual Studio Code**: 事前インストール
- **Claude Code 利用ライセンス**: Anthropic API キーまたは他の利用可能なライセンス

詳細は [事前準備ガイド](00_prerequisites.md) を参照してください。

## サポートとリソース

### 公式ドキュメント

- Claude Code: <https://docs.anthropic.com/claude-code>
- Spec Kit: <https://github.com/github/spec-kit>
- Spec Kit ウェブサイト: <https://speckit.org/>

### コミュニティ

- Anthropic コミュニティ: <https://community.anthropic.com/>
- Spec Kit Issues: <https://github.com/github/spec-kit/issues>

### Kugelpos ドキュメント

- メイン README: [../../README.md](../../README.md)
- CLAUDE.md: [../../CLAUDE.md](../../CLAUDE.md)
- Constitution: [../.specify/memory/constitution.md](../.specify/memory/constitution.md)

## トラブルシューティング

よくある問題と解決方法：

### Claude Code が見つからない

```bash
# インストールを確認
which claude

# 必要に応じて再インストール
brew reinstall claude
```

### Specify コマンドが見つからない

```bash
# uv のインストールを確認
which uv

# specify-cli を再インストール
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git --force
```

### API キーの問題

```bash
# API キーを明示的に設定
export ANTHROPIC_API_KEY="your-api-key-here"

# 永続化のためシェルプロファイルに追加
echo 'export ANTHROPIC_API_KEY="your-api-key"' >> ~/.bashrc
source ~/.bashrc
```

## 次のステップ

チュートリアル完了後：

1. [プロジェクト憲章](../.specify/memory/constitution.md)を確認
2. シンプルな機能仕様を作成してみる
3. 実装計画を生成
4. タスクに分解
5. AI 支援で実装

## 貢献

これらのチュートリアルで問題を見つけたり、改善提案がある場合：

1. 既存の Issue を確認
2. 詳細な説明付きで新しい Issue を作成
3. 修正の Pull Request を提出

## ライセンス

これらのチュートリアルは Kugelpos プロジェクトの一部であり、同じライセンス（Apache License 2.0）に従います。

---

**最終更新**: 2025年11月29日

**メンテナー**: Kugelpos 開発チーム
