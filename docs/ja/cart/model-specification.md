# カートサービス モデル仕様

## 概要

カートサービスは、Kugelpos POSシステムのショッピングカート管理とトランザクション処理を担当します。ステートマシンパターンによるカートライフサイクル管理、デュアルストレージ戦略（Dapr State Store + MongoDB）、プラグインアーキテクチャ（決済・プロモーション）、イベント駆動通信を実装しています。phase 2（issue #156）以降はクライアントが署名付きスナップショットとしてカートを保持し、サーバ側ストレージは「正」ではなくなった（[クライアント持ち回りカート](./client-carried-cart.md)）。

## データベースドキュメントモデル

### 1. CartDocument（アクティブショッピングカート）

ステートマシン管理されたアクティブショッピングカートを格納するドキュメント。

**コレクション名:** `cache_cart`

**継承:** `BaseTransaction` → `AbstractDocument` → `BaseDocumentModel`

**注:** 多くのフィールドは `BaseTransaction` から継承されています（tenant_id, store_code, transaction_no, payments, taxes 等）。

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| cart_id | string | ✓ | 一意のUUIDカート識別子 |
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | ターミナル番号 |
| receipt_no | integer | - | レシート番号 |
| transaction_no | integer | - | トランザクション番号 |
| transaction_type | integer | - | トランザクションタイプ |
| user | UserInfoDocument | - | ユーザー情報 |
| staff | StaffDocument | - | スタッフ情報 |
| sales | SalesDocument | - | 売上サマリー情報 |
| status | string | - | カート状態（Initial/Idle/EnteringItem/Paying/Completed/Cancelled） |
| generate_date_time | datetime | - | カート生成日時 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| subtotal_amount | float | - | 税金と割引前の合計 |
| total_amount | float | - | 税込み合計金額 |
| total_quantity | integer | - | 合計数量 |
| total_discount_amount | float | - | 合計割引金額 |
| deposit_amount | float | - | 預かり金額 |
| change_amount | float | - | おつり金額 |
| balance_amount | float | - | 残高金額 |
| line_items | array[LineItemDocument] | - | カート内商品明細 |
| payments | array[PaymentDocument] | - | 決済情報 |
| taxes | array[TaxDocument] | - | 税金計算情報 |
| subtotal_discounts | array[DiscountInfoDocument] | - | 小計レベル割引 |
| is_voided | boolean | - | 取消フラグ |
| is_refunded | boolean | - | 返品フラグ |
| masters | ReferenceMasters | - | マスターデータキャッシュ |
| receipt_text | string | - | レシートテキスト |
| journal_text | string | - | ジャーナルテキスト |
| seq | integer | - | オープンセッション内の取引連番。最初の finalize まで 0（#156） |
| revision | integer | - | 単調増加のカートリビジョン。スナップショット発行のたびに進む（#165） |
| carry_snapshot | boolean | - | 作成時にクライアントが宣言した経路（#192）。下記参照 |
| receipt_counter | integer | - | 端末の通算レシートカウンタ。印字番号の導出元（#166） |
| transaction_datetime | string | - | クライアントが bill 時に押印した取引時刻。tranlog の generate_date_time の源 |

**持ち回りカートが運ぶ値（issue #156 以降）:**

上表の下 5 フィールドは、いずれも**署名付きスナップショットの一部としてクライアントが保持する**値である。
署名がこれらを覆うため、サーバはキャッシュを読まずに「この端末がどの世代のカートを、どちらの経路で
開いたか」を判定できる。

- `seq` / `receipt_counter` / `transaction_datetime` は**採番と時刻の決定性**のためにある。
  再送がどのバックエンドに届いても同じ値が記録される（FR-012）。
  印字レシート番号は端末から受け取らず、`receipt_counter` と設定レンジからサーバが導出する（#208）。
- `revision` は**巻き戻しの事後検出**用。古いエンベロープはリビジョンが低い。ステートレスな
  バックエンドは高水位をリクエストごとの書き込みなしには知り得ないため、同期的な拒否ではなく
  検出に留める（#165）。
- `carry_snapshot` は**作成時の申告**である。サーバ側からは推測できない（作成時点では運ぶものが
  まだ無い）ため明示的に受け取る。
  - `True` — 持ち回り。**キャッシュには一切書かない**ので、スナップショット非同梱のリクエストは
    カートを見つけられず、それだけで拒否される
  - `False` — 非持ち回り。これをスナップショットとして提示すると拒否される。残ったキャッシュ写しから
    後続のスナップショット非同梱リクエストが黙って継続してしまうため
  - `None` — このフィールド以前に作られたカート。どちらも拒否しない

**LineItemDocumentサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| line_no | integer | ✓ | 明細行番号 |
| item_code | string | ✓ | 商品コード |
| item_name | string | - | 商品名 |
| unit_price | float | ✓ | 単価 |
| unit_price_original | float | - | 元の単価 |
| is_unit_price_changed | boolean | - | 単価変更フラグ |
| quantity | integer | ✓ | 数量（デフォルト: 0） |
| amount | float | - | 金額 |
| discount_amount | float | - | 割引金額 |
| tax_amount | float | - | 税額 |
| discounts | array[DiscountInfoDocument] | - | 明細レベル割引 |
| item_details | dict | - | 追加商品情報 |
| image_urls | array[string] | - | 商品画像URL |
| is_discount_restricted | boolean | - | 割引制限フラグ |
| is_cancelled | boolean | - | キャンセルフラグ |

**PaymentDocumentサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| payment_no | integer | ✓ | 決済番号 |
| payment_code | string | ✓ | 決済方法コード |
| payment_name | string | - | 決済方法名 |
| payment_amount | float | ✓ | 決済金額 |
| payment_detail | string | - | 決済詳細 |

**TaxDocumentサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tax_no | integer | ✓ | 税番号 |
| tax_code | string | - | 税コード |
| tax_type | string | ✓ | 税タイプ |
| tax_name | string | - | 税名称 |
| tax_amount | float | ✓ | 税額 |
| target_amount | float | - | 課税対象金額 |
| target_quantity | integer | - | 課税対象数量 |

**インデックス:**
- cart_id (unique)
- created_at (TTL、`CACHE_CART_TTL_SECONDS` 秒で失効)

TTL は Redis の `cartstore` 側 TTL と揃えてあり、孤立した MongoDB フォールバック写しを掃除する。
`updated_at` ではなく `created_at` に張るのは、初回 insert で `updated_at` が None になり得るため。

### 2. TranlogDocument（トランザクション履歴）

完了したトランザクション記録を格納するドキュメント。

**コレクション名:** `log_tran`

**継承:** `BaseTransaction` → `AbstractDocument` → `BaseDocumentModel`

**フィールド定義:**

CartDocumentと同じフィールド構造（BaseTransactionから継承）に加えて：

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| invoice_issue_no | string | - | 請求書発行番号 |

**インデックス:**
- ユニーク: (tenant_id, store_code, terminal_no, business_counter, transaction_no)
- ユニーク（partial、`cart_id` が文字列のときのみ）: (tenant_id, store_code, cart_id)
- 非ユニーク: (tenant_id, store_code, terminal_no, receipt_counter)

**取引の同一性は `cart_id` である（issue #156）。** `transaction_no` はオープンセッション内の
`seq` になったため単独では一意でなく（日次オープンで 1 に戻る）、採番タプルには `business_counter`
が入る。再送の重複排除は `cart_id` の partial unique インデックスが担う。

`receipt_counter` のインデックスは**意図的に非ユニーク**である。カウンタはクライアントが所有し
バックエンドは強制できず、端末交換やオフライン確定の未達で欠番が生じ得る。交換端末の再シードと
欠番調査のための高水位検索に使う。

### 3. TransactionStatusDocument（トランザクション状態追跡）

取消および返品操作を追跡するドキュメント。

**コレクション名:** `status_tran`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | ターミナル番号 |
| business_counter | integer | - | 営業回数。`transaction_no` と組で同一性を成す（#156） |
| transaction_no | integer | ✓ | トランザクション番号（持ち回り経路では per-open の seq） |
| is_voided | boolean | - | 取消状態フラグ（デフォルト: false） |
| is_refunded | boolean | - | 返品状態フラグ（デフォルト: false） |
| void_transaction_no | integer | - | 取消トランザクション番号 |
| void_date_time | string | - | 取消日時（ISO 8601文字列） |
| void_staff_id | string | - | 取消実行スタッフID |
| return_transaction_no | integer | - | 返品トランザクション番号 |
| return_date_time | string | - | 返品日時（ISO 8601文字列） |
| return_staff_id | string | - | 返品実行スタッフID |

**インデックス:**
- ユニーク: (tenant_id, store_code, terminal_no, business_counter, transaction_no)

`business_counter` が入るのは、`transaction_no` がオープンセッションごとに繰り返す `seq` に
なったためである（#156）。これが無いと、あるセッションの取消／返品ステータスが別セッションの
同番の取引と衝突する（日次オープンで seq が 1 に戻るので、2 日目の最初の売上が 1 日目の
ステータスを読んでしまう）。log_tran の採番タプルと同じ形である。

### 4. TerminalCounterDocument（ターミナルシーケンスカウンタ）

ターミナル固有のシーケンスカウンタを管理するドキュメント。

**コレクション名:** `info_terminal_counter`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| terminal_id | string | ✓ | ターミナル識別子 |
| count_dic | dict | ✓ | カウンタ辞書 |

**カウンタタイプ:**
- transaction_no: トランザクション番号カウンタ
- receipt_no: レシート番号カウンタ

**インデックス:**
- terminal_id (unique)

### 5. TranlogDeliveryStatus（メッセージ配信追跡）

pub/subメッセージ配信状況を追跡するドキュメント。

**コレクション名:** `status_tran_delivery`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| event_id | string | ✓ | イベント識別子（UUID） |
| published_at | datetime | ✓ | 発行日時 |
| status | string | ✓ | 全体配信状況（published/delivered/partially_delivered/failed） |
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | ターミナル番号 |
| transaction_no | integer | ✓ | トランザクション番号 |
| business_date | string | ✓ | 営業日（YYYYMMDD） |
| open_counter | integer | ✓ | 開設回数 |
| payload | dict | ✓ | メッセージペイロード |
| services | array[ServiceStatus] | - | サービス別配信状況 |
| last_updated_at | datetime | ✓ | 最終更新日時 |

**ServiceStatusサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| service_name | string | ✓ | サービス名 |
| status | string | - | 配信状況（pending/received/failed、デフォルト: pending） |
| received_at | datetime | - | 受信日時 |
| message | string | - | エラーメッセージなど |

**インデックス:**
- event_id (unique)
- status
- published_at

### 6. CartRestoreLogDocument（スナップショット監査証跡）

スナップショットの復元・拒否・finalize 乖離を 1 件 1 レコードで残す監査コレクション（issue #148、
#156 で per-request 経路にも拡張）。持ち回りカートでは、カートがサーバ側に存在しない時間帯がある。
**何が拒否され、どの世代のカートを持った端末が拒否されたのかは、ここにしか残らない。**

**コレクション名:** `log_cart_restore`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子（認証済みコンテキストから） |
| store_code | string | ✓ | 店舗コード（同上） |
| terminal_no | integer | ✓ | ターミナル番号（同上） |
| cart_id | string | - | 対象カート（提示されたスナップショットから） |
| result | string | ✓ | 結果。`restored` / `existing_returned` / `rejected` / `finalize_repeat_diverged` |
| api_path | string | - | 事象が起きた API パス。restore エンドポイントでは None、per-request 拒否では当該操作のパス |
| reject_reason | string | - | 拒否時のカートエラーコード（例 401501）。成功時は None |
| diverged | boolean | - | 提示されたスナップショットが既存カートと食い違う場合 true |
| snapshot_issued_at | string | - | エンベロープの発行時刻 |
| snapshot_terminal_no | integer | - | エンベロープが名乗るターミナル番号 |
| snapshot_kid | string | - | 署名鍵 ID。鍵ローテーション時の追跡に使う |
| snapshot_schema_version | integer | - | エンベロープのスキーマバージョン |
| snapshot_revision | integer | - | 提示されたカートリビジョン（#165）。拒否時、端末がどの世代を持っていたかを示す |
| event_datetime | string | ✓ | 記録時刻 |

**インデックス:**
- cart_id（非ユニーク）
- event_datetime（非ユニーク）

TTL は張らない。保持期間は他のログコレクションに合わせる。

## APIリクエスト/レスポンススキーマ

すべてのスキーマは`BaseSchemaModel`（一部実装では`BaseSchemmaModel`）を継承し、snake_caseからcamelCaseへの自動変換を提供します。

### 変更系リクエストのラッパ（issue #156）

持ち回り経路では、変更系リクエストの本体を**署名付きスナップショットで包む**。

```json
{
  "signedSnapshot": { "schemaVersion": 1, "issuedAt": "...", "kid": "...",
                      "tenantId": "...", "storeCode": "...", "terminalNo": 9,
                      "cartDocument": { ... }, "signature": "..." },
  "payload": <本来のリクエストボディ>
}
```

ASGI ミドルウェア（`middleware/snapshot_envelope.py`）が `signedSnapshot` を剥がしてリクエスト
スコープに載せ、`payload` を本体としてハンドラに渡す。**包まれていない本体（`signedSnapshot` を
持たない配列・オブジェクト・空）はそのまま素通りする**ため、phase 1 のクライアントは変更なしで
動く。素通りを許すかどうかは `CART_REQUEST_SNAPSHOT_MODE` が決める。

エンベロープの署名は、`signature` を除く全フィールドの正準 JSON を覆う。署名も検証も常に
snake_case の `model_dump(mode="json")` 表現に対して行うため、ワイヤ上の camelCase 別名は
検証に影響しない。

**SnapshotEnvelope:**

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| schemaVersion | integer | ✓ | エンベロープのスキーマバージョン |
| issuedAt | string | ✓ | 発行時刻 |
| kid | string | ✓ | 署名鍵 ID（ローテーション対応） |
| tenantId | string | ✓ | 発行時のテナント |
| storeCode | string | ✓ | 発行時の店舗 |
| terminalNo | integer | ✓ | 発行時のターミナル |
| cartDocument | dict | ✓ | カート文書全体（参照マスタ含む） |
| signature | string | ✓ | 上記すべてに対する HMAC 署名 |

### カート管理スキーマ

#### CartCreateRequest
新しいショッピングカートを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| transactionType | integer | - | トランザクションタイプ（デフォルト: 1 = 通常販売） |
| userId | string | - | ユーザー識別子 |
| userName | string | - | ユーザー名 |
| carrySnapshot | boolean | - | 以降のリクエストでスナップショットを必ず同梱するという申告（#192）。デフォルト false |

`carrySnapshot` が必要なのは、作成時点ではまだ運ぶものが無く、サーバが経路を推測できないためで
ある。推測に頼ると「クライアントが運ばないかもしれない」からとキャッシュに書くことになり、その
写しを後続のスナップショット非同梱リクエストが黙って継続してしまう（持ち回りリクエストが行った
変更をすべて取りこぼした状態で）。送らないクライアントは false を意味する。

#### CartCreateResponse
カート作成レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| cartId | string | 生成されたカートID |
| signedSnapshot | SnapshotEnvelope | 作成直後のカートの署名付きスナップショット（#148）。**`carrySnapshot=true` のときだけ入る**。既定（false）では null |

#### CartDeleteResponse
カート削除レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| message | string | 削除結果メッセージ |

### アイテム管理スキーマ

#### Item
カートに追加するアイテム情報。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | 商品コード |
| quantity | integer | ✓ | 数量 |
| unitPrice | float | - | 単価（オーバーライド用） |

#### ItemQuantityUpdateRequest
アイテム数量更新リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| quantity | integer | ✓ | 新しい数量 |

#### ItemUnitPriceUpdateRequest
アイテム単価更新リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| unitPrice | float | ✓ | 新しい単価 |

### 決済処理スキーマ

#### PaymentRequest
決済処理リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | 決済方法コード |
| amount | integer | ✓ | 決済金額（最小通貨単位） |
| detail | string | - | 決済詳細情報 |

### トランザクション表現スキーマ

#### Cart（レスポンス）
カート全体情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| cartId | string | カートID |
| cartStatus | string | カート状態 |
| subtotalAmount | float | 小計金額 |
| totalAmount | float | 合計金額 |
| balanceAmount | float | 残高金額 |
| lineItems | array[TranLineItem] | 明細項目 |
| payments | array[TranPayment] | 決済情報 |
| taxes | array[TranTax] | 税金情報 |

#### Tran（レスポンス）
トランザクション情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| transactionNo | integer | トランザクション番号 |
| businessDate | string | ビジネス日付 |
| totalAmount | float | 合計金額 |
| lineItems | array[TranLineItem] | 明細項目 |
| payments | array[TranPayment] | 決済情報 |
| taxes | array[TranTax] | 税金情報 |

### 配信状況管理スキーマ

#### DeliveryStatusUpdateRequest
配信状況更新リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| eventId | string | ✓ | イベントID |
| service | string | ✓ | サービス名 |
| status | string | ✓ | 配信状況 |
| message | string | - | メッセージ |

#### DeliveryStatusUpdateResponse
配信状況更新レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| eventId | string | イベントID |
| service | string | サービス名 |
| status | string | 配信状況 |
| success | boolean | 更新成功フラグ |

## ステートマシンパターン

### カート状態と遷移

**カート状態:**
1. **Initial** - 初期状態
2. **Idle** - アイドル状態（空のカート）
3. **EnteringItem** - アイテム入力中
4. **Paying** - 決済処理中
5. **Completed** - 完了（終了状態）
6. **Cancelled** - キャンセル（終了状態）

**有効な遷移:**
- Initial → Idle
- Idle → EnteringItem（アイテム追加時）
- Idle → Cancelled
- EnteringItem → Paying（決済開始時）
- EnteringItem → Cancelled
- Paying → EnteringItem（アイテム入力再開時）
- Paying → Completed（決済完了時）

## デュアルストレージ戦略

> **phase 2（issue #156）以降の位置づけ:** クライアントが署名付きスナップショットとしてカートを保持し、変更系リクエストのたびに同梱する方式になったため、**サーバ側ストレージはカートの「正」ではなくなった**。スナップショットを同梱したリクエストは State Store も MongoDB も読まずに処理される。以下のデュアルストレージは、スナップショットを同梱しない従来経路（DUAL モード）のためのものとして残っている。詳細は [クライアント持ち回りカート](./client-carried-cart.md) を参照。

### プライマリストレージ: Dapr State Store
- **用途:** アクティブカートの高速アクセス（スナップショット非同梱時）
- **実装:** Redis 経由のキー値ストア（コンポーネント名 `cartstore`）
- **TTL:** `CACHE_CART_TTL_SECONDS`（既定 36000 秒）

### セカンダリストレージ: MongoDB
- **用途:** 永続化とフォールバック（コレクション `cache_cart`）
- **実装:** 完全なドキュメントストレージ
- **同期:** State Storeとの結果的整合性
- **TTL:** `created_at` の TTL インデックスで State Store 側と揃える

### 持ち回りカートは、ここには書かれない（issue #192）

`carrySnapshot=true` で作られたカートは**キャッシュにも MongoDB にも一切書かない**。
1 つのカートが両方の経路を行き来すると内容が黙って失われるためである。作成時にキャッシュ写しを
残しておくと、後続のスナップショット非同梱リクエストがその古い写しから継続してしまい、持ち回り
リクエストが行った変更を取りこぼす。書かないことで、スナップショット非同梱のリクエストは
「カートが見つからない」だけで拒否される。

## プラグインアーキテクチャ

### 決済プラグイン（/services/strategies/payments/）
- 現金決済: おつり計算を含む処理
- キャッシュレス決済: カード・電子マネー処理
- カスタム決済: 拡張可能な決済方法

### プロモーションプラグイン
- JSONベースの設定
- 複数プロモーションの組み合わせ可能
- カスタム割引ロジックの実装可能

## イベント駆動通信

### 発行トピック

#### tranlog_report
トランザクション完了時に発行されるイベント。レポートサービスやジャーナルサービスが購読。

#### cashlog_report
現金入出金操作時に発行されるイベント。

#### opencloselog_report
ターミナル開店・閉店時に発行されるイベント。

## マルチテナント実装

1. **データベース分離:** `db_cart_{tenant_id}`形式でテナント別DB
2. **認証連携:** JWTトークンからtenant_id取得
3. **アクセス制御:** すべての操作でテナント検証実施

## 設定パラメータ

### CartSettings（settings_cart.py）

| パラメータ名 | 型 | デフォルト値 | 説明 |
|------------|------|------------|-------------|
| UNDELIVERED_CHECK_INTERVAL_IN_MINUTES | integer | 5 | 未配信チェック間隔（分） |
| UNDELIVERED_CHECK_PERIOD_IN_HOURS | integer | 24 | 未配信チェック期間（時間） |
| UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES | integer | 15 | 失敗判定期間（分） |
| DEBUG | string | "false" | デバッグモード |
| DEBUG_PORT | integer | 5678 | デバッグポート |

**署名付きスナップショット（issue #148 / #156）:**

| パラメータ名 | 型 | デフォルト値 | 説明 |
|------------|------|------------|-------------|
| SNAPSHOT_HMAC_KEYS | string | ""（**必須**） | `kid:base64鍵` の CSV。先頭が署名鍵、以降は検証のみ受け付ける旧世代（ローテーション猶予） |
| SNAPSHOT_ALLOW_INSECURE_KEY | boolean | false | 本リポジトリに公開されている鍵での起動を許す（ローカル開発専用） |
| CART_REQUEST_SNAPSHOT_MODE | string | "DUAL" | `DUAL` = スナップショット非同梱も受け付ける／`REQUIRED` = 変更系は同梱必須 |
| MAX_REQUEST_BODY_BYTES | integer | 4194304（4 MiB） | リクエストボディの上限。圧縮の有無を問わず全ボディに効く。持ち回りスナップショットが 413 になるときの調整先はここ |
| REQUEST_DECOMPRESS_MAX_BYTES | integer | None | **非推奨**。`MAX_REQUEST_BODY_BYTES` の旧名（#195）。旧名を設定した配備が黙殺されないよう残してある |

`SNAPSHOT_HMAC_KEYS` は必須で、使える鍵が無ければサービスは**起動を拒否する**（#192）。クライアントが
持ち回るカートは他のどこにも存在しないため、署名できないサービスはカートを返せない — 返さなければ
カートごと持ち去ることになる。degraded で走れたのは、サーバ側キャッシュが「正」だった頃までである。

**マスターデータキャッシュ（issue #072）:**

| パラメータ名 | 型 | デフォルト値 | 説明 |
|------------|------|------------|-------------|
| MASTER_DATA_CACHE_ENABLED | boolean | true | キャッシュ層の全体スイッチ。false で常に取得しに行く |
| MASTER_DATA_CACHE_STATE_STORE | string | "masterstore" | Dapr ステートストアのコンポーネント名 |
| MASTER_DATA_CACHE_TTL_SECONDS | integer | 300 | 名前空間別 TTL が無い場合のフォールバック |
| ITEM_MASTER_CACHE_TTL_SECONDS | integer | 300 | 商品マスタ TTL（秒） |
| PAYMENT_MASTER_CACHE_TTL_SECONDS | integer | 600 | 決済マスタ TTL（秒） |
| PROMOTION_MASTER_CACHE_TTL_SECONDS | integer | 60 | プロモーションマスタ TTL（秒） |
| SETTINGS_MASTER_CACHE_TTL_SECONDS | integer | 600 | 設定マスタ TTL（秒） |
| TAX_MASTER_CACHE_TTL_SECONDS | integer | 3600 | 税マスタ TTL（秒） |

**master-data との通信:**

| パラメータ名 | 型 | デフォルト値 | 説明 |
|------------|------|------------|-------------|
| USE_GRPC | boolean | false | 商品詳細取得に gRPC を使う |
| GRPC_TIMEOUT | float | 5.0 | gRPC タイムアウト（秒） |
| MASTER_DATA_GRPC_URL | string | "master-data:50051" | gRPC サーバの URL |