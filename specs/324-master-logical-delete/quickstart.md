# Quickstart: すべてのマスタの論理削除（is_deleted）

**Feature**: 324-master-logical-delete

起動したスタック（`./scripts/start.sh`）で、管理者のトークン `$ADMIN` を使って確かめる。`$MD=http://localhost:8002/api/v1/tenants/$TENANT`。

## 1. 論理削除と取得（例: 分類）

```bash
curl -s -X POST "$MD/categories" -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"categoryCode":"C9","description":"Old","descriptionShort":"Old","taxCode":"01"}'
curl -s -X DELETE "$MD/categories/C9" -H "Authorization: Bearer $ADMIN"               # 200（論理削除）
curl -s "$MD/categories/C9" -H "Authorization: Bearer $ADMIN"                         # 404
curl -s "$MD/categories/C9?include_deleted=true" -H "Authorization: Bearer $ADMIN"    # 200, isDeleted: true
curl -s "$MD/categories" -H "Authorization: Bearer $ADMIN"                            # C9 は含まれない
curl -s "$MD/categories?include_deleted=true" -H "Authorization: Bearer $ADMIN"       # C9 が含まれる
curl -s -X DELETE "$MD/categories/C9" -H "Authorization: Bearer $ADMIN"               # 404（論理削除済み）
```

## 2. 復元

```bash
curl -s -X POST "$MD/categories" -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"categoryCode":"C9","description":"New","descriptionShort":"New","taxCode":"01"}'   # 201
curl -s "$MD/categories/C9" -H "Authorization: Bearer $ADMIN"                         # description: New, isDeleted: false
```

## 3. 物理削除

```bash
curl -s -X DELETE "$MD/categories/C9?is_logical=false" -H "Authorization: Bearer $ADMIN"   # 200
curl -s "$MD/categories/C9?include_deleted=true" -H "Authorization: Bearer $ADMIN"        # 404
```

## 4. 他のマスタ

1〜3 を、商品 `/items/{item_code}`、店舗別商品 `/stores/{store}/items/{item_code}`、支払 `/payments/{code}`、プロモーション `/promotions/{code}`、設定 `/settings/{name}`、従業員 `/staff/{id}` で同じように確かめる。

商品ブック `/item_books/{id}` は復元の対象外なので、手順 2 の代わりに次を確かめる:

```bash
ID=$(curl -s -X POST "$MD/item_books" -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"title":"Book","categories":[]}' | jq -r .data.itemBookId)
curl -s -X DELETE "$MD/item_books/$ID" -H "Authorization: Bearer $ADMIN"                       # 200（論理削除）
curl -s "$MD/item_books/$ID?include_deleted=true" -H "Authorization: Bearer $ADMIN"            # 200, isDeleted: true
curl -s -X POST "$MD/item_books" -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' \
  -d '{"title":"Book","categories":[]}' | jq -r .data.itemBookId                               # $ID とは別の ID
```

## 5. cart・terminal・report

- 商品を論理削除し、cart のキャッシュを無効にしてから（`DELETE http://localhost:8003/api/v1/cache/master-data`）、その商品を販売すると「存在しない商品」になる
- 従業員を論理削除し、その従業員でサインインすると 401 / `406004`（存在しない従業員と同じ）
- プロモーションを論理削除してキャッシュを無効にすると、その割引が付かない。設定を論理削除すると、cart は既定値を使う
- report は変えない。削除したマスタはレポートでコードで出る（名前の解決は #326）
