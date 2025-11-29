# ハンズオン: 取引キャンセル理由記録機能の実装

このハンズオンでは、Spec Kit を使って実際に新機能を実装し、テストが全てパスするまでを体験します。

## 目次

1. [ハンズオンの概要](#ハンズオンの概要)
2. [前提条件](#前提条件)
3. [学習目標](#学習目標)
4. [機能要件](#機能要件)
5. [実装の流れ](#実装の流れ)
6. [Step 1: 仕様作成](#step-1-仕様作成)
7. [Step 2: 実装計画](#step-2-実装計画)
8. [Step 3: タスク分解](#step-3-タスク分解)
9. [Step 4: 実装](#step-4-実装)
10. [Step 5: テスト実行](#step-5-テスト実行)
11. [まとめ](#まとめ)

---

## ハンズオンの概要

### 実装する機能

**取引キャンセル理由記録機能**

POSシステムで取引がキャンセルされた際に、その理由を記録し、後からレポートで分析できるようにする機能を実装します。

### 対象サービス

- **master-data サービス**: キャンセル理由マスターの管理
- **cart サービス**: キャンセル処理にキャンセル理由を追加
- **journal サービス**: キャンセル理由を含むトランザクションログの記録
- **report サービス**: キャンセル理由別集計レポートの追加

### 難易度

⭐⭐☆☆☆（中級）

### 所要時間

3〜4時間

---

## 前提条件

### 必須

- [ ] Claude Code がインストール済み
- [ ] Spec Kit が初期化済み
- [ ] プロジェクト憲章が作成済み（`.specify/memory/constitution.md`）
- [ ] Docker と Docker Compose が利用可能
- [ ] Python 3.12+ がインストール済み

### 確認コマンド

```bash
# Claude Code の確認
claude --version

# Spec Kit の確認
specify --help

# Docker の確認
docker --version
docker compose version

# Python の確認
python --version
```

### 環境準備

```bash
# プロジェクトルートに移動
cd /home/masa/proj/kugelpos-public/worktree/ai-coding-lesson

# サービスが起動していない場合は起動
cd ../../../
./quick_start.sh

# 元のディレクトリに戻る
cd worktree/ai-coding-lesson
```

---

## 学習目標

このハンズオンを通じて以下を習得します：

### Spec Kit ワークフロー

- [ ] `/speckit.specify` による仕様書の作成
- [ ] `/speckit.plan` による実装計画の生成
- [ ] `/speckit.tasks` によるタスク分解
- [ ] `/speckit.implement` による実装実行

### Kugelpos アーキテクチャ

- [ ] マイクロサービス間の連携
- [ ] イベント駆動通信（Pub/Sub）
- [ ] Repository パターンの理解
- [ ] プラグインアーキテクチャ（レポートプラグイン）

### テスト駆動開発（TDD）

- [ ] テストファースト開発の実践
- [ ] pytest による単体テスト
- [ ] 統合テストの作成
- [ ] テストの実行とデバッグ

---

## 機能要件

> **注意**: 以下は機能要件のサンプルです。実際のハンズオンでは `/speckit.specify` コマンドで生成される仕様書の内容に従ってください。

### ユーザーストーリー（サンプル）

以下は期待される仕様の例です。実際の仕様作成では、AI が対話を通じてより詳細な内容を生成します。

#### US1: キャンセル理由マスターの管理（優先度: P1）

**目的**: システム管理者がキャンセル理由を管理できるようにする

**主なシナリオ**:
- キャンセル理由の CRUD 操作
- テナントごとの管理
- 有効/無効の切り替え

---

#### US2: キャンセル時に理由を記録（優先度: P1）

**目的**: 取引キャンセル時にスタッフが理由を選択して記録できるようにする

**主なシナリオ**:
- キャンセル API でキャンセル理由を指定
- イベント経由で journal に記録
- バリデーション処理

---

#### US3: キャンセル理由別レポート（優先度: P2）

**目的**: 管理者がキャンセル理由別の統計を確認できるようにする

**主なシナリオ**:
- 期間指定での集計
- キャンセル理由ごとの件数・金額表示

---

### 技術要件（参考）

実際の実装では、`/speckit.plan` で生成される計画に従います。

#### データモデル例

```python
# キャンセル理由マスター（イメージ）
{
    "cancel_reason_code": "CR001",
    "cancel_reason_name": "顧客都合",
    "display_order": 1,
    "is_active": true,
    "tenant_code": "TENANT001"
}
```

#### API エンドポイント例

- `POST /api/v1/cancel-reasons` - キャンセル理由登録
- `GET /api/v1/cancel-reasons` - キャンセル理由一覧
- その他 CRUD エンドポイント

---

## 実装の流れ

### 全体フロー

```
Step 1: 仕様作成 (/speckit.specify)
    ↓
Step 2: 実装計画 (/speckit.plan)
    ↓
Step 3: タスク分解 (/speckit.tasks)
    ↓
Step 4: 実装 (/speckit.implement)
    ↓
Step 5: テスト実行 (全テストパス確認)
```

### タイムライン

| ステップ | 所要時間 | 内容 |
|---------|---------|------|
| Step 1 | 30分 | 仕様書作成、要件の明確化 |
| Step 2 | 30分 | 実装計画の生成、技術選定 |
| Step 3 | 30分 | タスク分解、依存関係の整理 |
| Step 4 | 90分 | コード実装、テスト作成 |
| Step 5 | 30分 | テスト実行、デバッグ |

---

## Step 1: 仕様作成

### 目的

機能要件を明確にし、テスト可能な仕様書を作成します。

### 手順

1. **Claude Code を起動**

   ```bash
   # プロジェクトルートで起動
   claude
   ```

2. **仕様作成コマンドを実行**

   Claude Code のプロンプトで以下を入力：

   ```
   /speckit.specify 取引キャンセル時に理由を記録し、レポートで分析できる機能を追加
   ```

3. **AI との対話**

   AI が以下について質問する可能性があります：

   - キャンセル理由の種類は？
   - キャンセル理由は必須か任意か？
   - 既存のキャンセル処理への影響は？
   - レポートの集計単位は？

   **推奨回答例**:
   ```
   - キャンセル理由はマスターデータとして管理し、店舗が自由に追加・編集できる
   - キャンセル時にキャンセル理由の指定は必須とする
   - 既存のキャンセル API を拡張し、cancel_reason_code パラメータを追加
   - レポートは日次・期間指定で集計できるようにする
   ```

4. **生成された仕様書を確認**

   以下のファイルが生成されます：
   ```
   specs/NNN-cancel-reason-tracking/spec.md
   ```

   確認ポイント：
   - [ ] ユーザーストーリーが3つ定義されている
   - [ ] 各ストーリーに Given-When-Then シナリオがある
   - [ ] 機能要件（FR-001〜）が列挙されている
   - [ ] 成功基準（SC-001〜）が測定可能

### チェックポイント

生成された仕様書が以下を満たしているか確認：

- [ ] **ユーザーストーリー**: 3つのストーリー（US1: マスター管理、US2: 理由記録、US3: レポート）
- [ ] **機能要件**: 最低10個の FR（Functional Requirement）
- [ ] **エッジケース**: 無効な理由コード、テナント分離など
- [ ] **成功基準**: 測定可能な指標

### トラブルシューティング

**問題**: 仕様が曖昧

**解決**: `/speckit.clarify` を使用して質問に答える

```bash
/speckit.clarify
```

---

## Step 2: 実装計画

### 目的

技術的な実装方針を決定し、詳細な計画を作成します。

### 手順

1. **実装計画コマンドを実行**

   ```
   /speckit.plan
   ```

2. **AI が生成する成果物**

   以下のファイルが生成されます：
   ```
   specs/NNN-cancel-reason-tracking/plan.md
   specs/NNN-cancel-reason-tracking/research.md
   specs/NNN-cancel-reason-tracking/data-model.md
   specs/NNN-cancel-reason-tracking/contracts/
   ```

3. **生成された計画を確認**

   **plan.md** の確認ポイント：
   - [ ] Constitution Check が実行されている
   - [ ] 技術スタック（Python, FastAPI, MongoDB）が明記
   - [ ] サービス構成が定義されている
   - [ ] データモデルが設計されている

   **data-model.md** の確認ポイント：
   - [ ] CancelReason モデルが定義されている
   - [ ] TransactionLog の拡張が記載されている
   - [ ] リレーションシップが明確

   **contracts/** の確認ポイント：
   - [ ] API エンドポイント定義がある
   - [ ] リクエスト/レスポンススキーマがある
   - [ ] イベントスキーマがある

### Constitution Check

計画が以下の原則に準拠しているか確認：

- [ ] **マイクロサービスアーキテクチャ**: 各サービスの責任が明確
- [ ] **テストファースト**: テストケースが先に定義されている
- [ ] **共有 Commons ライブラリ**: Repository パターンを使用
- [ ] **サーキットブレーカー**: 外部通信に DaprClientHelper を使用
- [ ] **イベント駆動**: Pub/Sub でサービス間通信
- [ ] **プラグインアーキテクチャ**: レポートプラグインとして実装

### トラブルシューティング

**問題**: Constitution Check で違反が検出された

**解決**: 違反理由を確認し、計画を修正するか、憲章の例外として正当化

---

## Step 3: タスク分解

### 目的

実装をタスクに分解し、実行順序を決定します。

### 手順

1. **タスク分解コマンドを実行**

   ```
   /speckit.tasks
   ```

2. **生成されたタスクを確認**

   以下のファイルが生成されます：
   ```
   specs/NNN-cancel-reason-tracking/tasks.md
   ```

3. **生成されたタスクを確認**

   > **注意**: 以下はタスク分解の例です。実際には `/speckit.tasks` が生成する内容に従ってください。

   期待されるタスクの概要（サンプル）：

   - **Phase 1**: Setup（環境確認）
   - **Phase 2**: Foundational（US1: キャンセル理由マスター管理）
     - モデル、リポジトリ、サービス、API の実装
     - テストの作成
   - **Phase 3**: US2（キャンセル理由の記録）
     - Cart API 拡張、イベント連携、Journal 記録
   - **Phase 4**: US3（レポート機能）
     - レポートプラグイン実装
   - **Phase 5**: Polish（テスト実行、ドキュメント更新）

   詳細なタスクリストは AI が生成します。

### 依存関係の確認

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← US1 の完了が US2, US3 の前提
    ↓
Phase 3 (US2) ← 並列実行可能 → Phase 4 (US3)
    ↓
Phase 5 (Polish)
```

### チェックポイント

- [ ] タスクが 15〜20 個程度に分解されている
- [ ] 各タスクに [P] （並列実行可能）マークがある
- [ ] ファイルパスが具体的に記載されている
- [ ] テストタスクが実装タスクより前にある

---

## Step 4: 実装

### 目的

タスクに従ってコードを実装します。

### 手順

1. **実装コマンドを実行**

   ```
   /speckit.implement
   ```

2. **AI が順次実装**

   AI が以下の順序で実装を進めます：

   1. **テストの作成** （テストファースト）
   2. **モデルの実装**
   3. **リポジトリの実装**
   4. **サービスロジックの実装**
   5. **API エンドポイントの実装**
   6. **イベント連携の実装**

3. **実装中の確認**

   各タスク完了後、以下を確認：

   - [ ] ファイルが正しい場所に作成されている
   - [ ] 型ヒントが付与されている
   - [ ] docstring が記載されている
   - [ ] エラーハンドリングが適切

### 実装の詳細

> **注意**: 以下は実装イメージのサンプルです。実際のコードは AI が生成します。

AI が自動的に以下のようなコンポーネントを実装します：

**主な実装内容**:
- **master-data サービス**: CancelReason モデル、リポジトリ、API エンドポイント
- **cart サービス**: キャンセル API の拡張、イベント送信
- **journal サービス**: TransactionLog へのフィールド追加
- **report サービス**: キャンセル理由別レポートプラグイン

**実装パターン**:
- BaseDocumentModel を継承したモデルクラス
- AbstractRepository を継承したリポジトリクラス
- Pydantic を使った API スキーマ
- FastAPI ルーターでの API 実装
- pytest による単体・統合テスト

### 進捗確認

実装中、定期的に以下を確認：

```bash
# ファイルが作成されているか確認
ls -la services/master-data/app/models/
ls -la services/master-data/app/repositories/

# 構文エラーがないか確認（各サービスで）
cd services/master-data
pipenv run python -m py_compile app/models/cancel_reason.py
```

### トラブルシューティング

**問題**: インポートエラーが発生

**解決**: `__init__.py` ファイルを確認、必要に応じて追加

**問題**: 型エラーが発生

**解決**: 型ヒントを確認、mypy でチェック

```bash
pipenv run mypy app/
```

---

## Step 5: テスト実行

### 目的

実装した機能が正しく動作することを確認します。

### 手順

#### 1. Commons ライブラリの更新

```bash
# プロジェクトルートで実行
./scripts/update_common_and_rebuild.sh
```

#### 2. サービスの再起動

プロジェクトルートで以下を実行：

```bash
# サービスを停止
./scripts/stop.sh

# ビルドして起動（quick_start.sh が全て実行）
./quick_start.sh
```

**quick_start.sh の処理内容**:
- Python 環境のビルド（`./scripts/rebuild_pipenv.sh`）
- Docker イメージのビルド（`./scripts/build.sh`）
- サービスの起動（`./scripts/start.sh`）

#### 3. テストの実行

**master-data サービスのテスト**:

```bash
cd services/master-data
./run_all_tests.sh
```

期待される結果:
```
test_clean_data.py::test_clean_all_data PASSED
test_setup_data.py::test_setup_master_data PASSED
test_cancel_reason.py::test_create_cancel_reason PASSED
test_cancel_reason.py::test_get_cancel_reasons PASSED
test_cancel_reason.py::test_update_cancel_reason PASSED
test_cancel_reason.py::test_delete_cancel_reason PASSED

========== 6 passed in 2.34s ==========
```

**cart サービスのテスト**:

```bash
cd services/cart
./run_all_tests.sh
```

期待される結果:
```
test_cart_cancel.py::test_cancel_with_reason PASSED
test_cart_cancel.py::test_cancel_invalid_reason PASSED

========== 2 passed in 1.87s ==========
```

**journal サービスのテスト**:

```bash
cd services/journal
./run_all_tests.sh
```

期待される結果:
```
test_journal_cancel.py::test_record_cancel_reason PASSED

========== 1 passed in 1.23s ==========
```

**report サービスのテスト**:

```bash
cd services/report
./run_all_tests.sh
```

期待される結果:
```
test_cancel_reason_report.py::test_generate_cancel_reason_report PASSED

========== 1 passed in 1.56s ==========
```

#### 4. 全サービスのテスト

```bash
# プロジェクトルートで実行
./scripts/run_all_tests_with_progress.sh
```

### テスト失敗時の対応

#### デバッグ手順

1. **エラーメッセージの確認**

   ```bash
   # 詳細ログ付きで実行
   cd services/master-data
   pipenv run pytest tests/test_cancel_reason.py -v -s
   ```

2. **サービスログの確認**

   ```bash
   # master-data サービスのログ
   cd services
   docker compose logs -f master-data
   ```

3. **データベースの確認**

   ```bash
   # MongoDB に接続
   docker exec -it mongodb mongosh

   # データベース選択
   use kugelpos_TENANT001

   # コレクション確認
   db.cancel_reasons.find().pretty()
   ```

4. **API の手動テスト**

   ```bash
   # キャンセル理由作成
   curl -X POST http://localhost:8002/api/v1/cancel-reasons \
     -H "Content-Type: application/json" \
     -H "X-Tenant-Code: TENANT001" \
     -d '{
       "cancel_reason_code": "CR001",
       "cancel_reason_name": "顧客都合",
       "description": "顧客の都合によるキャンセル",
       "display_order": 1
     }'
   ```

#### よくあるエラーと解決方法

**エラー1: ModuleNotFoundError**

```
ModuleNotFoundError: No module named 'app.models.cancel_reason'
```

**解決**:
- `__init__.py` ファイルが存在するか確認
- インポートパスが正しいか確認
- `pipenv install` を再実行

**エラー2: Collection not found**

```
pymongo.errors.OperationFailure: Collection 'cancel_reasons' not found
```

**解決**:
- `test_setup_data.py` でコレクションが作成されているか確認
- テスト実行順序が正しいか確認（clean → setup → feature tests）

**エラー3: ValidationError**

```
pydantic.error_wrappers.ValidationError: 1 validation error for CancelReason
```

**解決**:
- Pydantic スキーマと実際のデータが一致しているか確認
- 必須フィールドが全て含まれているか確認

### チェックポイント

全てのテストがパスしたら、以下を確認：

- [ ] master-data サービス: 全テストパス
- [ ] cart サービス: 全テストパス
- [ ] journal サービス: 全テストパス
- [ ] report サービス: 全テストパス
- [ ] 全サービスのテスト: 全テストパス
- [ ] サービスログにエラーがない
- [ ] API が正常に動作する

---

## まとめ

### 達成したこと

このハンズオンを通じて、以下を達成しました：

- [ ] Spec Kit を使った仕様駆動開発の実践
- [ ] マイクロサービスアーキテクチャの理解
- [ ] イベント駆動通信の実装
- [ ] テスト駆動開発（TDD）の実践
- [ ] Repository パターンの活用
- [ ] プラグインアーキテクチャの実装

### 学んだ技術

#### Spec Kit ワークフロー

1. **Specify**: 仕様書作成で要件を明確化
2. **Plan**: 実装計画で技術選定と設計
3. **Tasks**: タスク分解で実装を整理
4. **Implement**: AI 支援での実装

#### Kugelpos アーキテクチャ

- **マイクロサービス間連携**: master-data → cart → journal → report
- **イベント駆動**: Pub/Sub による疎結合
- **Repository パターン**: データアクセスの抽象化
- **プラグイン**: 拡張可能なレポート機能

#### テスト戦略

- **テストファースト**: 実装前にテストを書く
- **テスト種類**: 単体テスト、統合テスト、契約テスト
- **テスト実行順序**: clean → setup → feature tests

### 成果物

以下のファイルが作成されました：

```
specs/NNN-cancel-reason-tracking/
├── spec.md              # 機能仕様
├── plan.md              # 実装計画
├── tasks.md             # タスクリスト
├── research.md          # 調査結果
├── data-model.md        # データモデル
└── contracts/           # API 契約

services/master-data/
├── app/models/cancel_reason.py
├── app/repositories/cancel_reason_repository.py
├── app/services/cancel_reason_service.py
├── app/schemas/cancel_reason_schema.py
├── app/routers/cancel_reason.py
└── tests/test_cancel_reason.py

services/cart/
├── app/schemas/cart_schema.py (拡張)
├── app/services/cart_service.py (拡張)
└── tests/test_cart_cancel.py

services/journal/
├── app/models/transaction_log.py (拡張)
└── tests/test_journal_cancel.py

services/report/
├── app/plugins/cancel_reason_report.py
└── tests/test_cancel_reason_report.py
```

### 次のステップ

さらに学習を進めるために：

1. **機能拡張**: キャンセル理由にカテゴリ分類を追加
2. **パフォーマンス**: レポート生成の最適化（インデックス追加）
3. **UI 実装**: キャンセル理由選択画面の実装
4. **監視**: キャンセル率のアラート機能追加

### 他の機能に挑戦

- [ ] ポイントカード機能（中級）
- [ ] 時間帯別料金設定（中級）
- [ ] 在庫自動発注機能（上級）
- [ ] セール・プロモーション管理（上級）

---

## 参考資料

### ドキュメント

- [プロジェクト憲章](../.specify/memory/constitution.md)
- [CLAUDE.md](../../CLAUDE.md)
- [README.md](../../README.md)

### Spec Kit リソース

- 公式サイト: <https://speckit.org/>
- GitHub: <https://github.com/github/spec-kit>
- ブログ記事: <https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/>

### Kugelpos アーキテクチャ

- マイクロサービスパターン
- イベント駆動アーキテクチャ
- Repository パターン
- サーキットブレーカーパターン

---

**最終更新**: 2025年11月29日

**作成者**: Kugelpos 開発チーム

**フィードバック**: 改善提案や質問があれば Issue を作成してください
