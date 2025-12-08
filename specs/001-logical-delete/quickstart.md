# クイックスタート: 商品カテゴリマスターの論理削除

**日付**: 2025-12-08
**フィーチャー**: 001-logical-delete

## 概要

このガイドでは、商品カテゴリマスターの論理削除機能を素早くセットアップして使用する方法を説明します。

## 前提条件

- Docker と Docker Compose がインストールされている
- Python 3.12+ がインストールされている
- Pipenv がインストールされている

## セットアップ

### 1. マイグレーションの実行

既存のカテゴリマスターデータに論理削除フィールドを追加します。

```bash
# プロジェクトルートに移動
cd /workspaces/kugelpos-backend

# master-dataサービスに移動
cd services/master-data

# マイグレーションスクリプトを実行
pipenv run python ../../scripts/migrations/add_logical_delete_to_category_master.py
```

**期待される出力**:
```
Tenant tenant001: 10 documents updated
Tenant tenant002: 5 documents updated
Migration completed successfully
```

### 2. サービスの再起動

master-dataサービスを再起動して変更を反映します。

```bash
# servicesディレクトリに移動
cd /workspaces/kugelpos-backend/services

# master-dataサービスを再起動
docker-compose restart master-data

# ログを確認
docker-compose logs -f master-data
```

### 3. 動作確認

APIエンドポイントをテストします。

```bash
# カテゴリ一覧取得（有効なカテゴリのみ）
curl -X GET "http://localhost:8002/api/v1/category-master" \
  -H "tenant-code: tenant001"

# カテゴリ削除（論理削除）
curl -X DELETE "http://localhost:8002/api/v1/category-master/CAT001" \
  -H "tenant-code: tenant001"

# 削除済みカテゴリを含む一覧取得
curl -X GET "http://localhost:8002/api/v1/category-master?include_deleted=true" \
  -H "tenant-code: tenant001"

# カテゴリ復元
curl -X POST "http://localhost:8002/api/v1/category-master/CAT001/restore" \
  -H "tenant-code: tenant001"
```

## 基本的な使用方法

### カテゴリの削除（論理削除）

```bash
curl -X DELETE "http://localhost:8002/api/v1/category-master/{category_code}" \
  -H "tenant-code: {tenant_code}"
```

**レスポンス**:
```json
{
  "message": "Category deleted successfully",
  "category_code": "CAT001"
}
```

### 削除済みカテゴリの取得

```bash
# include_deleted=trueを指定
curl -X GET "http://localhost:8002/api/v1/category-master?include_deleted=true" \
  -H "tenant-code: {tenant_code}"
```

**レスポンス**:
```json
[
  {
    "category_code": "CAT001",
    "description": "飲料",
    "is_deleted": false,
    "deleted_at": null
  },
  {
    "category_code": "CAT002",
    "description": "食品",
    "is_deleted": true,
    "deleted_at": "2025-12-01T10:30:00Z"
  }
]
```

### カテゴリの復元

```bash
curl -X POST "http://localhost:8002/api/v1/category-master/{category_code}/restore" \
  -H "tenant-code: {tenant_code}"
```

**レスポンス**:
```json
{
  "category_code": "CAT001",
  "description": "飲料",
  "is_deleted": false,
  "deleted_at": null
}
```

## テストの実行

### すべてのテストを実行

```bash
cd services/master-data
./run_all_tests.sh
```

### 論理削除テストのみ実行

```bash
cd services/master-data
pipenv run pytest tests/test_category_master_logical_delete.py -v
```

### 復元テストのみ実行

```bash
cd services/master-data
pipenv run pytest tests/test_category_master_restore.py -v
```

### include_deletedテストのみ実行

```bash
cd services/master-data
pipenv run pytest tests/test_category_master_include_deleted.py -v
```

## エラーケースの確認

### 削除済みカテゴリの取得（404エラー）

```bash
# include_deletedを指定しない場合
curl -X GET "http://localhost:8002/api/v1/category-master/CAT001" \
  -H "tenant-code: tenant001"
```

**レスポンス（削除済みの場合）**:
```json
{
  "detail": "Category not found"
}
```
HTTP ステータス: 404

### 削除されていないカテゴリの復元（400エラー）

```bash
# 有効なカテゴリに対して復元を実行
curl -X POST "http://localhost:8002/api/v1/category-master/CAT001/restore" \
  -H "tenant-code: tenant001"
```

**レスポンス**:
```json
{
  "detail": "Category is not deleted"
}
```
HTTP ステータス: 400

### 削除済みカテゴリの更新（400エラー）

```bash
# 削除済みカテゴリに対して更新を実行
curl -X PUT "http://localhost:8002/api/v1/category-master/CAT001" \
  -H "tenant-code: tenant001" \
  -H "Content-Type: application/json" \
  -d '{"description": "更新後の説明"}'
```

**レスポンス**:
```json
{
  "detail": "Cannot update deleted category"
}
```
HTTP ステータス: 400

### 削除済みカテゴリと同じコードで新規作成（409エラー）

```bash
curl -X POST "http://localhost:8002/api/v1/category-master" \
  -H "tenant-code: tenant001" \
  -H "Content-Type: application/json" \
  -d '{
    "category_code": "CAT001",
    "description": "新しい飲料"
  }'
```

**レスポンス（CAT001が削除済みの場合）**:
```json
{
  "detail": "Category code already exists (deleted category)"
}
```
HTTP ステータス: 409

## トラブルシューティング

### マイグレーションエラー

**症状**: マイグレーションスクリプトが失敗する

**解決方法**:
```bash
# MongoDBが起動しているか確認
docker-compose ps mongodb

# MongoDBのログを確認
docker-compose logs mongodb

# replica setの状態を確認
docker exec -it mongodb mongosh --eval "rs.status()"
```

### テスト失敗

**症状**: テストが失敗する

**解決方法**:
```bash
# テスト用のMongoDBをリセット
./scripts/reset-mongodb.sh

# サービスを再起動
./scripts/start.sh

# テストを再実行
cd services/master-data
./run_all_tests.sh
```

### APIエラー

**症状**: API呼び出しが失敗する

**解決方法**:
```bash
# サービスのログを確認
docker-compose logs -f master-data

# ヘルスチェック
curl http://localhost:8002/health

# データベース接続確認
docker exec -it mongodb mongosh --eval "db.adminCommand('ping')"
```

## 次のステップ

1. **実装**: tasks.mdの手順に従って実装を進める
2. **テスト**: すべてのテストが通ることを確認
3. **レビュー**: PRを作成してレビューを依頼
4. **デプロイ**: 承認後、本番環境にデプロイ

## 参考資料

- [仕様書](spec.md)
- [実装計画](plan.md)
- [データモデル](data-model.md)
- [APIコントラクト](contracts/category_master_api.yaml)
- [CLAUDE.md](../../CLAUDE.md) - プロジェクトの開発ガイド
