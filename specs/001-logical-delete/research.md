# リサーチ: 商品カテゴリマスターの論理削除

**日付**: 2025-12-08
**フィーチャー**: 001-logical-delete

## 概要

商品カテゴリマスターに論理削除機能を追加するための技術的な調査と設計決定を文書化する。

## 技術決定事項

### 1. 論理削除のフィールド設計

**決定**: `is_deleted` (boolean) と `deleted_at` (datetime, optional) を使用

**理由**:
- **is_deleted**: 削除状態を明確に示すフラグ。クエリでのフィルタリングが容易。
- **deleted_at**: 削除日時を記録することで、監査・トラブルシューティングに対応。
- MongoDB のインデックスに適している（is_deleted + 他のフィールドの複合インデックス）

**検討した代替案**:
- deleted_at のみを使用（NULL = 有効、NOT NULL = 削除済み）
  - 却下理由: クエリが複雑になり、パフォーマンスが低下する可能性がある
- status フィールド（enum: active, deleted, archived）
  - 却下理由: 現時点でアーカイブ機能は不要（Out of Scope）

### 2. データベースクエリの最適化

**決定**: is_deleted フィールドに単一インデックスを作成

**理由**:
- デフォルトのクエリ（is_deleted=False）のパフォーマンス向上
- 既存の category_code + tenant_id の複合一意インデックスは維持

**検討した代替案**:
- 複合インデックス (tenant_id, is_deleted, category_code)
  - 却下理由: tenant_id + category_code の既存インデックスで十分カバーされる
- インデックスなし
  - 却下理由: 全件スキャンによるパフォーマンス低下

### 3. API エンドポイント設計

**決定**:
- 削除: 既存の DELETE エンドポイントを論理削除に変更（後方互換性維持）
- 復元: 新規 POST `/api/v1/category-master/{category_code}/restore` エンドポイント追加
- 取得: 既存エンドポイントに `include_deleted` クエリパラメータ追加

**理由**:
- RESTful な設計に準拠
- 既存クライアントコードの変更不要（削除エンドポイントは同じ）
- 復元は副作用を伴う操作なので POST が適切

**検討した代替案**:
- PATCH で復元
  - 却下理由: PATCH は部分更新に使用するのが一般的
- DELETE で物理削除、PUT で論理削除
  - 却下理由: 後方互換性が失われる

### 4. エラーハンドリング

**決定**:
- 削除済みカテゴリ取得: 404 Not Found
- 削除されていないカテゴリ復元: 400 Bad Request
- 削除済みカテゴリ更新: 400 Bad Request
- 削除済みカテゴリと同コードで新規作成: 409 Conflict

**理由**:
- HTTP標準に準拠
- クライアント側のエラーハンドリングが明確

**検討した代替案**:
- すべて 400 Bad Request
  - 却下理由: エラーの種類が区別できない
- カスタムエラーコード（2xx）
  - 却下理由: HTTP標準から逸脱

### 5. マイグレーション戦略

**決定**: 既存データに対して `is_deleted=False`, `deleted_at=None` を設定するマイグレーションスクリプトを作成

**理由**:
- 既存データとの整合性を保つ
- アプリケーションコードでデフォルト値を設定するだけでは既存データに適用されない

**検討した代替案**:
- アプリケーションコードでデフォルト値のみ設定
  - 却下理由: 既存データが取得できなくなる
- マイグレーション不要（NULL を False として扱う）
  - 却下理由: クエリが複雑になり、インデックスが効かない

### 6. テスト戦略

**決定**:
- 論理削除テスト（test_category_master_logical_delete.py）
- 復元テスト（test_category_master_restore.py）
- include_deleted テスト（test_category_master_include_deleted.py）
- 各テストで全エッジケースをカバー

**理由**:
- テストファースト開発（憲章必須要件）
- エッジケースの完全なカバレッジ
- テスト実行順序の遵守

**検討した代替案**:
- 単一のテストファイル
  - 却下理由: テストが大きくなりすぎる、メンテナンス性が低下

## ベストプラクティス

### MongoDBでの論理削除

1. **インデックス戦略**:
   ```python
   # is_deleted フィールドに単一インデックス
   await collection.create_index("is_deleted")
   ```

2. **クエリパターン**:
   ```python
   # デフォルト: 削除済みを除外
   query = {"tenant_id": tenant_id, "is_deleted": False}

   # include_deleted=True: すべて取得
   if include_deleted:
       query = {"tenant_id": tenant_id}
   ```

3. **削除操作**:
   ```python
   # 論理削除
   await collection.update_one(
       {"tenant_id": tenant_id, "category_code": code},
       {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
   )
   ```

4. **復元操作**:
   ```python
   # 復元
   await collection.update_one(
       {"tenant_id": tenant_id, "category_code": code, "is_deleted": True},
       {"$set": {"is_deleted": False}, "$unset": {"deleted_at": ""}}
   )
   ```

### FastAPI での論理削除

1. **Pydantic モデル**:
   ```python
   class CategoryMasterDocument(AbstractDocument):
       is_deleted: bool = False
       deleted_at: Optional[datetime] = None
   ```

2. **クエリパラメータ**:
   ```python
   @router.get("/categories")
   async def get_categories(
       include_deleted: bool = Query(False, description="削除済みカテゴリを含む")
   ):
       ...
   ```

3. **エラーレスポンス**:
   ```python
   # 404 Not Found
   raise HTTPException(status_code=404, detail="Category not found")

   # 400 Bad Request
   raise HTTPException(status_code=400, detail="Category is not deleted")

   # 409 Conflict
   raise HTTPException(status_code=409, detail="Category code already exists")
   ```

## 未解決の質問

なし。すべての技術的決定が完了しました。

## 次のステップ

Phase 1: 設計とコントラクト
- data-model.md の作成
- API コントラクト（OpenAPI スキーマ）の作成
- quickstart.md の作成
