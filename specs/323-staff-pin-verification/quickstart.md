# Quickstart: 端末サインインでの従業員 PIN の照合

**Feature**: 323-staff-pin-verification

起動したスタック（`./scripts/start.sh`）で確かめる手順。`$TENANT`・`$STORE`・`$TERMINAL_ID`・端末の資格情報（`X-API-KEY` または端末の JWT）は既存の e2e と同じ準備で用意する。

## 1. 従業員を 2 人登録する

```bash
# PIN を登録した従業員
curl -s -X POST "$MASTER/api/v1/tenants/$TENANT/staff" -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"id":"S1","name":"With PIN","pin":"1234","roles":["cashier"]}'

# PIN を登録していない従業員
curl -s -X POST "$MASTER/api/v1/tenants/$TENANT/staff" -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"id":"S2","name":"No PIN","roles":["cashier"]}'   # PIN を省略できる
```

## 2. PIN を登録した従業員

```bash
# 正しい PIN → 200
curl -s -X POST "$TERMINAL/api/v1/terminals/$TERMINAL_ID/sign-in?terminal_id=$TERMINAL_ID" \
  -H "X-API-KEY: $API_KEY" -H 'Content-Type: application/json' -d '{"staffId":"S1","pin":"1234"}'

# サインアウトしてから、誤った PIN / PIN なし → どちらも 401、userError.code=406004
curl -s -X POST ".../sign-in?..." -d '{"staffId":"S1","pin":"9999"}'
curl -s -X POST ".../sign-in?..." -d '{"staffId":"S1"}'
```

## 3. PIN を登録していない従業員

```bash
# PIN なし → 200（今と同じ）
curl -s -X POST ".../sign-in?..." -d '{"staffId":"S2"}'
# サインアウトしてから、任意の PIN → 200（無視される）
curl -s -X POST ".../sign-in?..." -d '{"staffId":"S2","pin":"0000"}'
```

## 4. 存在しない従業員

```bash
# → 401、userError.code=406004、メッセージは 2 の失敗と同じ
curl -s -X POST ".../sign-in?..." -d '{"staffId":"NOPE","pin":"1234"}'
```

## 5. 照合を直接は呼べない

```bash
# 端末の API キー → 401、端末の JWT → 403
curl -s -X POST "$MASTER/api/v1/internal/tenants/$TENANT/staff/S1/verify" \
  -H "X-API-KEY: $API_KEY" -H 'Content-Type: application/json' -d '{"pin":"1234"}'
```

## 6. ログに PIN が無い

手作業の grep は、他の数値に一致したり、誤った PIN の漏れを見落としたりする。自動テストで確かめる（DEBUG を有効にし、正しい PIN・誤った PIN・任意の PIN にそれぞれ一意で長い値を使って、すべてのログに現れないことを検査する）。手で確かめるなら、一意で長い PIN（例 `pin-sentinel-7c1e9a`）を使い、DEBUG を有効にしたうえで:

```bash
docker compose logs master-data terminal | grep -c pin-sentinel-7c1e9a   # 0
```

## 7. master-data が止まっているとき

```bash
docker compose stop master-data
# → 502、userError.code=407201（401 ではない）
curl -s -X POST ".../sign-in?..." -d '{"staffId":"S1","pin":"1234"}'
docker compose start master-data
```
