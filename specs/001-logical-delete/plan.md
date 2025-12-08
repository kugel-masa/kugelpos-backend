# 実装計画: 商品カテゴリマスターの論理削除

**Branch**: `001-logical-delete` | **Date**: 2025-12-08 | **Spec**: [spec.md](spec.md)
**Input**: 商品カテゴリマスターに論理削除機能を追加する仕様

## 概要

商品カテゴリマスターの削除方式を物理削除から論理削除に変更する。is_deletedとdeleted_atフィールドを追加し、削除時にフラグを設定することで、過去のトランザクションデータとの整合性を保ちながらカテゴリを非表示にする。削除済みカテゴリの取得および復元機能も提供する。

## 技術コンテキスト

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, Motor (MongoDB async driver), Pydantic, pytest-asyncio
**Storage**: MongoDB（テナント毎にデータベース分離、Motor async driver使用）
**Testing**: pytest, pytest-asyncio（テスト実行順序: test_clean_data.py → test_setup_data.py → 機能テスト）
**Target Platform**: Linux server（Docker container）
**Project Type**: マイクロサービス（master-dataサービスの機能拡張）
**Performance Goals**: 既存API応答時間を維持（<200ms p95）
**Constraints**: 後方互換性を保つ（既存APIエンドポイント維持）、マイグレーション実行が必要
**Scale/Scope**: 単一サービス（master-data）内の変更、既存データベーススキーマの拡張

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ マイクロサービスアーキテクチャ（必須・変更不可）
- master-dataサービス内の変更のみ
- サービス間通信は不要（このサービス内で完結）
- データベースはテナント毎に分離されている既存構造を維持

### ✅ テストファースト開発（必須・変更不可）
- すべての機能実装前にテストを作成
- テスト実行順序を遵守: test_clean_data.py → test_setup_data.py → 機能テスト
- pytest-asyncioを使用

### ✅ サーキットブレーカーパターン（必須・変更不可）
- この機能では外部HTTP呼び出しやDapr通信は不要
- 既存のパターンに影響なし

### ✅ イベント駆動通信
- この機能ではイベント発行は不要
- カテゴリマスターは他のサービスから参照されるが、変更通知は不要

### ✅ プラグインアーキテクチャ
- この機能はプラグインではない
- 既存のプラグインアーキテクチャに影響なし

### ✅ 共通ライブラリ（commons）
- AbstractRepository, AbstractDocumentを使用
- エラーコード: 70YYZZ（70=master-data, YY=カテゴリ機能, ZZ=特定エラー）
- 既存のエラーハンドリングパターンを踏襲

### ✅ 言語ポリシー
- ドキュメント（plan.md, tasks.md）は日本語
- コード（変数名、関数名、クラス名）は英語
- コメントは日本語

### ✅ 技術標準
- Python 3.12+ with FastAPI
- 非同期処理（async/await）
- 型ヒント使用
- MongoDB（Motor async driver）
- Pydanticスキーマ
- エンドポイントバージョン管理: /api/v1/

**結論**: すべての必須原則に準拠。憲章違反なし。

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
services/master-data/
├── app/
│   ├── models/
│   │   ├── documents/
│   │   │   └── category_master_document.py      # is_deleted, deleted_at追加
│   │   └── repositories/
│   │       └── category_master_repository.py    # 論理削除対応クエリ追加
│   ├── services/
│   │   └── category_master_service.py           # 論理削除・復元ロジック追加
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   └── category_master.py           # 復元エンドポイント追加、include_deleted対応
│   │   │   └── schemas.py                       # レスポンススキーマ拡張
│   │   └── common/
│   │       └── schemas.py                       # 共通スキーマ拡張
│   └── exceptions/
│       └── master_data_exceptions.py            # エラーコード追加
└── tests/
    ├── test_clean_data.py                       # データクリーンアップ
    ├── test_setup_data.py                       # テストデータセットアップ
    ├── test_category_master_logical_delete.py  # 論理削除テスト
    ├── test_category_master_restore.py         # 復元テスト
    └── test_category_master_include_deleted.py # 削除済み取得テスト

scripts/
└── migrations/
    └── add_logical_delete_to_category_master.py # マイグレーションスクリプト
```

**Structure Decision**: マイクロサービスアーキテクチャに準拠。master-dataサービス内の既存ファイルを拡張し、新規テストファイルとマイグレーションスクリプトを追加する。

## Complexity Tracking

憲章違反なし。このセクションは該当なし。

## Phase 0: リサーチ

**ステータス**: ✅ 完了

**成果物**:
- [research.md](research.md) - 技術的決定事項とベストプラクティス

**主な決定事項**:
1. 論理削除フィールド設計: is_deleted (boolean) + deleted_at (datetime)
2. インデックス戦略: is_deleted フィールドに単一インデックス
3. API設計: RESTful、後方互換性維持、復元エンドポイント追加
4. エラーハンドリング: HTTP標準ステータスコード（404, 400, 409）
5. マイグレーション戦略: 既存データに is_deleted=False, deleted_at=None を設定
6. テスト戦略: 3つの独立したテストファイル

## Phase 1: 設計とコントラクト

**ステータス**: ✅ 完了

**成果物**:
- [data-model.md](data-model.md) - データモデル、状態遷移、検証ルール
- [contracts/category_master_api.yaml](contracts/category_master_api.yaml) - OpenAPI 3.0 仕様
- [quickstart.md](quickstart.md) - セットアップと使用方法ガイド

**設計のハイライト**:

### データモデル
- **新規フィールド**: is_deleted (boolean, default=False), deleted_at (datetime, optional)
- **インデックス**: is_deleted に単一インデックス
- **制約**: (tenant_id, category_code) の一意制約は削除済みも含む

### API エンドポイント
1. **GET /category-master**: include_deleted パラメータ追加
2. **GET /category-master/{category_code}**: include_deleted パラメータ追加
3. **DELETE /category-master/{category_code}**: 論理削除に変更（後方互換性維持）
4. **PUT /category-master/{category_code}**: 削除済みカテゴリは400エラー
5. **POST /category-master/{category_code}/restore**: 新規エンドポイント（復元）

### エラー応答
- **404 Not Found**: 削除済みカテゴリ取得（include_deleted=false）
- **400 Bad Request**: 削除されていないカテゴリ復元、削除済みカテゴリ更新
- **409 Conflict**: 削除済みカテゴリと同コードで新規作成

## Phase 2: タスク分解

**ステータス**: ⏸️ 保留（/speckit.tasksコマンドで実行）

このフェーズでは以下のタスクに分解されます:
1. データモデル更新（CategoryMasterDocument）
2. リポジトリ層更新（CategoryMasterRepository）
3. サービス層更新（CategoryMasterService）
4. API層更新（エンドポイント、スキーマ）
5. テスト作成（論理削除、復元、include_deleted）
6. マイグレーションスクリプト作成
7. ドキュメント更新

**次のコマンド**: `/speckit.tasks` を実行してタスクを生成

## 実装の重要ポイント

### 1. 後方互換性

既存のAPIエンドポイントは変更せず、動作のみ変更:
- DELETE エンドポイント: 物理削除 → 論理削除
- GET エンドポイント: デフォルトで is_deleted=False のみ返す

### 2. テストファースト開発

実装前にテストを作成（憲章必須要件）:
```bash
# テスト実行順序
test_clean_data.py           # データクリーンアップ
test_setup_data.py           # テストデータセットアップ
test_category_master_logical_delete.py  # 論理削除テスト
test_category_master_restore.py         # 復元テスト
test_category_master_include_deleted.py # 削除済み取得テスト
```

### 3. マイグレーション

既存データへのフィールド追加:
```python
# すべてのテナントのデータベースに対して実行
await collection.update_many(
    {"is_deleted": {"$exists": False}},
    {"$set": {"is_deleted": False, "deleted_at": None}}
)

# インデックス作成
await collection.create_index("is_deleted")
```

### 4. パフォーマンス

- is_deleted フィールドにインデックス作成
- デフォルトクエリ（is_deleted=False）のパフォーマンス最適化
- 既存APIの応答時間を維持（<200ms p95）

### 5. エラーハンドリング

すべてのエラーケースで適切なHTTPステータスコードを返す:
```python
# 404 Not Found
if not category or (category.is_deleted and not include_deleted):
    raise HTTPException(status_code=404, detail="Category not found")

# 400 Bad Request
if not category.is_deleted:
    raise HTTPException(status_code=400, detail="Category is not deleted")

# 409 Conflict
if existing_deleted_category:
    raise HTTPException(status_code=409, detail="Category code already exists")
```

## 依存関係

### 内部依存
- commons ライブラリ（AbstractRepository, AbstractDocument）
- 既存の CategoryMasterService, CategoryMasterRepository

### 外部依存
- なし（このサービス内で完結）

## リスクと軽減策

### リスク1: マイグレーション失敗
**軽減策**:
- マイグレーション前にバックアップ取得
- 開発環境で十分にテスト
- ロールバック手順を準備

### リスク2: パフォーマンス低下
**軽減策**:
- is_deleted フィールドにインデックス作成
- クエリパフォーマンステストを実施
- 必要に応じて複合インデックスを検討

### リスク3: 既存クライアントへの影響
**軽減策**:
- 後方互換性を維持（APIエンドポイントは変更なし）
- デフォルト動作は変更なし（is_deleted=False のみ返す）
- 段階的なロールアウト

## 完了基準

以下の条件をすべて満たすこと:

1. ✅ すべてのテストがパス
2. ✅ マイグレーションが成功
3. ✅ APIコントラクトに準拠
4. ✅ 既存APIの応答時間を維持（<200ms p95）
5. ✅ 憲章のすべての必須原則に準拠
6. ✅ コードレビュー承認
7. ✅ ドキュメント更新完了

## 次のステップ

1. **タスク生成**: `/speckit.tasks` コマンドを実行
2. **実装開始**: tasks.md の手順に従って実装
3. **テスト実行**: すべてのテストが通ることを確認
4. **レビュー**: PRを作成してレビュー依頼
5. **デプロイ**: 承認後、本番環境にデプロイ
