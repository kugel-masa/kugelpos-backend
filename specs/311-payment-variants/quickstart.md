# Quickstart: 支払マスタのサブコード

全サービスを起動した状態（`./scripts/start.sh`）で、テナント `A1234`・店舗 `5678`・端末 `1` が開設済みとする。`$TOKEN` はテナントのトークン、`$API_KEY` は端末の API キー。

## 1. サブコードを登録する

> サブコードの登録は、commons・cart・report を本フィーチャーの版へ配備し終えてから行う（古い cart はサブコードを無視して記帳する・research R-14）。

```bash
MD=http://localhost:8002/api/v1/tenants/A1234

curl -s -X POST "$MD/payments/11/variants" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"variantCode":"VISA","name":"VISA"}'
curl -s -X POST "$MD/payments/11/variants" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"variantCode":"PAYPAY","name":"PayPay"}'

# 重複は拒否される
curl -s -X POST "$MD/payments/11/variants" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"variantCode":"VISA","name":"VISA"}'

# 支払方法の取得にサブコードが入る
curl -s "$MD/payments/11" -H "Authorization: Bearer $TOKEN" | jq '.data.variants'
```

## 2. サブコードで支払う

cart の支払マスタのキャッシュの有効期限（`PAYMENT_MASTER_CACHE_TTL_SECONDS`、既定 600 秒）が過ぎてから行う。すぐに試すときは、特権の利用者のトークンで cart のキャッシュを無効化する:

```bash
curl -s -X DELETE "http://localhost:8003/api/v1/cache/master-data?namespace=payment_master" -H "Authorization: Bearer $TOKEN"
```


```bash
CART=http://localhost:8003/api/v1
# （カートを作り、商品を足し、小計まで進める。スナップショットの持ち回りは既存の手順どおり）

# サブコードの指定なし → 有効なサブコードが 2 件なので 403020
curl -s -X POST "$CART/carts/$CART_ID/payments?terminal_id=A1234-5678-1" -H "X-API-KEY: $API_KEY" \
  -H 'Content-Type: application/json' -d '[{"paymentCode":"11","amount":1000}]' | jq '.userError'

# PAYPAY で支払う → 支払行の paymentName は "PayPay"、builtinPaymentName は支払方法の名前
curl -s -X POST "$CART/carts/$CART_ID/payments?terminal_id=A1234-5678-1" -H "X-API-KEY: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '[{"paymentCode":"11","amount":1000,"variantCode":"PAYPAY"}]' | jq '.data.payments'
```

## 3. 停止と取消・返品

```bash
# PAYPAY を停止
curl -s -X PUT "$MD/payments/11/variants/PAYPAY" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"PayPay","isActive":false}'

# 停止前に PAYPAY で支払った取引は、売上時の支払種別（11/PAYPAY）で取消・返品できる
#   取消: [{"paymentCode":"11","variantCode":"PAYPAY","amount":1000}]
#   返品: 売上時の支払種別（売上時の金額まで）か現金 01。それ以外は 403021、超過は 403022
```

## 4. 集計

```bash
RP=http://localhost:8004/api/v1/tenants/A1234/stores/5678
curl -s "$RP/reports?report_scope=flash&report_type=sales&business_date=$BIZ_DATE" \
  -H "Authorization: Bearer $TOKEN" | jq '.data.payments'
# → {"paymentCode":"11","paymentName":"<支払方法の名前>","variants":[{"variantCode":"PAYPAY",...}, ...]}
```

## 5. テスト

```bash
cd services/master-data && pipenv run pytest tests/unit -k variant
cd services/cart && pipenv run pytest tests/unit -k variant
cd services/report && pipenv run pytest tests/unit -k variant
./scripts/run_integration_tests.sh
./scripts/run_e2e_tests.sh
```
