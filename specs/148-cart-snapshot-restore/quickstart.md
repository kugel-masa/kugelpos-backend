# Quickstart: 署名付きカートスナップショット + restore API（#148）

実装完了後に機能を確認する手順。前提: Docker Compose スタックが起動できること（`/service` コマンド参照）。

## 1. セットアップ

```bash
# 署名鍵を設定（開発用）。kid:base64鍵 形式、先頭が現行鍵
echo 'SNAPSHOT_HMAC_KEYS=v1:'"$(openssl rand -base64 32)" >> services/cart/.env

./scripts/build.sh
./scripts/start.sh
```

起動ログに鍵ロードの成功（または未設定 warning = 縮退モード）が出ることを確認。

## 2. スナップショットの取得（User Story 2）

既存の e2e と同じ流れでテナント/端末を準備し、カートを操作する:

```bash
# カート作成 → 商品追加（terminal_id・APIキーは環境に合わせる）
curl -s -X POST "http://localhost:8003/api/v1/carts?terminal_id=$TERMINAL_ID" \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{"transaction_type": 101, "user_id": "u1", "user_name": "user"}' | jq '.data.cartId'

curl -s -X POST "http://localhost:8003/api/v1/carts/$CART_ID/lineItems?terminal_id=$TERMINAL_ID" \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '[{"itemCode": "ITEM001", "quantity": 2}]' | jq '.data.signedSnapshot' > /tmp/snapshot.json
```

確認ポイント:
- 変更系レスポンスすべてに `data.signedSnapshot` が含まれる（`schemaVersion` / `kid` / `cartDocument` / `signature`）
- `cartDocument.masters.items` にスキャン済み商品のマスタが同梱されている
- GET（カート照会）には `signedSnapshot` が**含まれない**

## 3. restore の確認（User Story 1）

「カートを見たことのないバックエンド」を再現する最も簡単な方法は Redis のカートキーを消すこと:

```bash
# サーバ側キャッシュからカートを消す（Redis 直接 / cartstore は databaseIndex に注意）
docker exec -it kugelpos-redis redis-cli -n 0 --scan --pattern "*$CART_ID*" | xargs -r docker exec -i kugelpos-redis redis-cli -n 0 del

# 消えたことを確認（404 になる）
curl -s "http://localhost:8003/api/v1/carts/$CART_ID?terminal_id=$TERMINAL_ID" -H "X-API-KEY: $API_KEY" | jq '.code'

# スナップショットから復元
curl -s -X POST "http://localhost:8003/api/v1/carts/restore?terminal_id=$TERMINAL_ID" \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/snapshot.json | jq '{restored: .data.restored, diverged: .data.diverged}'
# → {"restored": true, "diverged": null}

# 復元後に通常操作が継続できる（商品追加 → 小計 → 支払い → 確定）
```

## 4. 拒否系の確認（User Story 3）

```bash
# 改ざん: cartDocument の金額を書き換えて提示 → 401501
jq '.cartDocument.balanceAmount = 1' /tmp/snapshot.json > /tmp/tampered.json
curl -s -X POST "http://localhost:8003/api/v1/carts/restore?terminal_id=$TERMINAL_ID" \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/tampered.json | jq '.userError.code'   # → "401501"

# 衝突: カートが存在する状態でそのまま restore → 既存返却
curl -s -X POST "http://localhost:8003/api/v1/carts/restore?terminal_id=$TERMINAL_ID" \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/snapshot.json | jq '{restored: .data.restored, diverged: .data.diverged}'
# → restored=false。古いスナップショットなら diverged=true（差分通知）
```

監査証跡: MongoDB の `db_cart_{tenant_id}.log_cart_restore` に上記すべての試行（成功/既存返却/拒否）が記録されていることを確認。

## 5. テストと計測

```bash
cd services/cart
pipenv run pytest -m unit          # 署名・正規化・エンベロープ
pipenv run pytest -m integration   # レスポンス付加 + restore 全パターン（要 MongoDB）
./scripts/run_e2e_tests.sh         # 取引継続シナリオ含む

# サイズ/レイテンシ計測（SC-005 / SC-006）: /perf-test の標準手順で
# 40 商品カートの gzip 後レスポンスサイズと p95 を取得し、issue #148 に記録
```
