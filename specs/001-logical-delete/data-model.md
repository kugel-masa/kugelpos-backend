# データモデル: 商品カテゴリマスターの論理削除

**日付**: 2025-12-08
**フィーチャー**: 001-logical-delete

## 概要

商品カテゴリマスター（CategoryMasterDocument）に論理削除機能を追加するためのデータモデル設計。

## エンティティ

### CategoryMasterDocument

商品カテゴリを表すドキュメントクラス。

#### フィールド

| フィールド名 | 型 | 必須 | デフォルト | 説明 |
|------------|---|------|----------|------|
| `_id` | ObjectId | ✅ | auto | MongoDB 内部ID |
| `tenant_id` | str | ✅ | - | テナント識別子（マルチテナント対応） |
| `category_code` | str | ✅ | - | カテゴリコード（tenant_id と組み合わせて一意） |
| `description` | str | ✅ | - | カテゴリの完全な説明 |
| `description_short` | str | ❌ | None | 短縮表示用の説明 |
| `tax_code` | str | ❌ | None | 適用される税コード |
| `is_deleted` | bool | ✅ | False | **[新規]** 論理削除フラグ |
| `deleted_at` | datetime | ❌ | None | **[新規]** 削除日時（UTC） |
| `created_at` | datetime | ✅ | auto | 作成日時 |
| `updated_at` | datetime | ✅ | auto | 更新日時 |

#### 新規フィールドの詳細

**is_deleted** (boolean, デフォルト: False):
- 論理削除状態を示すフラグ
- False: 有効なカテゴリ（通常の取得APIで返される）
- True: 削除済みカテゴリ（通常の取得APIでは返されない）
- インデックス付与（クエリパフォーマンス向上）

**deleted_at** (datetime, オプショナル):
- カテゴリが削除された日時（UTC）
- is_deleted=False の場合は None
- is_deleted=True の場合に設定される
- 監査・トラブルシューティング・データ分析に使用

#### 制約

1. **一意制約**: (tenant_id, category_code) の組み合わせは一意
   - 削除済みカテゴリも一意制約の対象
   - 削除済みカテゴリと同じコードで新規作成不可

2. **状態制約**:
   - is_deleted=True の場合、deleted_at は必須
   - is_deleted=False の場合、deleted_at は None

3. **更新制約**:
   - is_deleted=True のカテゴリは更新不可（復元のみ可能）

#### インデックス

```python
# 既存インデックス
{
    "tenant_id": 1,
    "category_code": 1
}  # unique=True

# 新規インデックス
{
    "is_deleted": 1
}
```

## 状態遷移

```
[未作成] --create--> [有効] --delete--> [削除済] --restore--> [有効]
                        |                                          ^
                        |                                          |
                        +------------------------------------------+
                                    update (有効な場合のみ)
```

### 状態定義

1. **有効 (Active)**
   - is_deleted = False
   - deleted_at = None
   - 通常の取得APIで返される
   - 更新・削除・復元が可能

2. **削除済 (Deleted)**
   - is_deleted = True
   - deleted_at = 削除日時
   - include_deleted=True の場合のみ取得可能
   - 更新不可、復元のみ可能

### 許可される操作

| 現在の状態 | 操作 | 結果の状態 | HTTP メソッド |
|----------|-----|----------|--------------|
| 有効 | 削除 | 削除済 | DELETE |
| 有効 | 更新 | 有効 | PUT/PATCH |
| 有効 | 復元 | エラー（400） | POST |
| 削除済 | 削除 | 削除済（冪等） | DELETE |
| 削除済 | 更新 | エラー（400） | PUT/PATCH |
| 削除済 | 復元 | 有効 | POST |
| 削除済 | 取得（デフォルト） | エラー（404） | GET |
| 削除済 | 取得（include_deleted） | 削除済（成功） | GET |

## データ検証

### Pydantic スキーマ

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class CategoryMasterDocument(AbstractDocument):
    """商品カテゴリドキュメント"""

    tenant_id: str = Field(..., description="テナントID")
    category_code: str = Field(..., description="カテゴリコード")
    description: str = Field(..., description="カテゴリ説明")
    description_short: Optional[str] = Field(None, description="短縮説明")
    tax_code: Optional[str] = Field(None, description="税コード")
    is_deleted: bool = Field(False, description="論理削除フラグ")
    deleted_at: Optional[datetime] = Field(None, description="削除日時")

    @validator('deleted_at')
    def validate_deleted_at(cls, v, values):
        """deleted_at の検証"""
        is_deleted = values.get('is_deleted', False)
        if is_deleted and v is None:
            raise ValueError('is_deleted が True の場合、deleted_at は必須です')
        if not is_deleted and v is not None:
            raise ValueError('is_deleted が False の場合、deleted_at は None である必要があります')
        return v
```

## マイグレーション

### 既存データの更新

すべての既存 CategoryMasterDocument に対して:

```python
{
    "$set": {
        "is_deleted": False,
        "deleted_at": None
    }
}
```

### マイグレーションスクリプト

```python
# scripts/migrations/add_logical_delete_to_category_master.py

async def migrate_category_master():
    """カテゴリマスターに論理削除フィールドを追加"""

    # すべてのテナントのデータベースに対して実行
    for tenant_id in tenants:
        db = get_database(tenant_id)
        collection = db["category_master"]

        # 既存データを更新
        result = await collection.update_many(
            {"is_deleted": {"$exists": False}},
            {"$set": {"is_deleted": False, "deleted_at": None}}
        )

        # インデックス作成
        await collection.create_index("is_deleted")

        print(f"Tenant {tenant_id}: {result.modified_count} documents updated")
```

## クエリパターン

### 有効なカテゴリのみ取得

```python
query = {
    "tenant_id": tenant_id,
    "is_deleted": False
}
```

### 削除済みを含むすべてのカテゴリ取得

```python
query = {
    "tenant_id": tenant_id
}
# is_deleted フィールドでフィルタリングしない
```

### 特定カテゴリの取得（削除チェック付き）

```python
category = await collection.find_one({
    "tenant_id": tenant_id,
    "category_code": category_code,
    "is_deleted": False
})
if category is None:
    raise HTTPException(status_code=404, detail="Category not found")
```

### 論理削除の実行

```python
result = await collection.update_one(
    {
        "tenant_id": tenant_id,
        "category_code": category_code
    },
    {
        "$set": {
            "is_deleted": True,
            "deleted_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    }
)
```

### 復元の実行

```python
result = await collection.update_one(
    {
        "tenant_id": tenant_id,
        "category_code": category_code,
        "is_deleted": True
    },
    {
        "$set": {
            "is_deleted": False,
            "updated_at": datetime.utcnow()
        },
        "$unset": {
            "deleted_at": ""
        }
    }
)
```

## パフォーマンス考慮事項

1. **インデックス**:
   - is_deleted フィールドにインデックスを作成
   - デフォルトクエリ（is_deleted=False）のパフォーマンス向上

2. **クエリ最適化**:
   - 削除済みカテゴリは少数と想定
   - is_deleted=False のクエリが大多数

3. **データ量**:
   - 削除済みカテゴリも保持するため、データ量は増加
   - 定期的なアーカイブ機能は Out of Scope

## セキュリティ考慮事項

1. **認証・認可**:
   - 削除・復元は管理者権限が必要（既存の認証・認可メカニズムを使用）

2. **監査ログ**:
   - deleted_at フィールドで削除日時を記録
   - 誰が削除したかは既存のログ機構で記録（この機能の範囲外）

3. **データ整合性**:
   - 削除済みカテゴリも一意制約の対象
   - トランザクションデータからの参照は保持
