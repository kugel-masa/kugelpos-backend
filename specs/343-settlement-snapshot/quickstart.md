# Quickstart: 精算実績の確かめ方

**Feature**: 343-settlement-snapshot

## 1. テスト

```bash
./scripts/run_unit_tests.sh
./scripts/build.sh && ./scripts/start.sh
./scripts/run_integration_tests.sh
./scripts/run_e2e_tests.sh            # cart は DUAL。REQUIRED も /test-guide の手順で
```

## 2. 手で通す流れ（e2e のスタック）

1. テナント・店舗・端末・担当者・商品・支払を用意し、端末をサインイン・開設（釣銭準備金 10,000）
2. 現金で 2 件販売する（番号 1、2）
3. 入金 500
3a. 販売と入金が report に届くのを待つ（e2e では `wait_for`）
4. 精算の前の確認: `GET /api/v1/terminals/{id}/close-preview?seq=3` → 何も保存されず、理論在高と未着 1 件
4a. 精算: `POST /api/v1/terminals/{id}/close` に `{"physicalAmount": <理論在高>, "seq": 3}`
   - 応答の `expectedCashTotal` = 10,000 + 現金の売上 + 500、`difference` = 0、`missingCount` = 1（番号 3 が届いていない）
   - レシートに `未着の取引 1件`
5. 精算実績: `GET /api/v1/tenants/{t}/stores/{s}/settlements?terminal_no=1` に 1 件。閉設ログが report に届くと `state` が `final`。`missingRanges` = `[{first:3,last:3}]`
6. 端末の日報: `GET …/terminals/1/reports?report_scope=daily&report_type=sales&business_date=…` が精算実績の確定集計と同じ。売上レポートの現金の欄の `logicalAmount` = 精算実績の `expectedCash.total`
7. 遅れた取引: 同じ営業の番号 3 の取引ログを report に直接届ける（pub/sub の口）→ 端末の日報は変わらない
8. 同じ営業の確定の口をもう一度（内部の口を直接）→ 確定済みなので `created: false`、同じ `settlementId`
8a. 閉設済みの端末にもう一度精算 → `406003`（端末の状態のエラー。既存の挙動）
9. report を止めて別の端末を精算 → 503 `406016`、端末は開設のまま、閉設ログが無い

## 3. 店舗の日報の未精算

端末 A を精算、端末 B は開設して販売したまま → 店舗の日報（daily）が 403 `412101`、`unsettledSessions` に端末 B。

## 4. 既存のテナント

配備前からあるテナントで、report を起動し直したあと `settlement_record` と索引ができていること（`db.settlement_record.getIndexes()`）。

## 5. 仮の精算実績の作り直し

terminal のトランザクションを失敗させる（テストで差し替える）か、report の応答を遅らせてタイムアウトさせる → 端末は開設のまま、精算実績は `provisional`。そのあと 1 件販売してもう一度精算 → 精算実績は作り直され、その販売を含む。閉設ログが届いて `final`。
