# Data Model: client-carried cart phase 2（#156）

phase 1 で確立したエンベロープ・監査レコードを再利用し、本フェーズの差分のみ記す。

---

## 1. スナップショットエンベロープ（phase 1 から不変）

phase 1 の `SnapshotEnvelope`（`schema_version` / `issued_at` / `kid` / `tenant_id` / `store_code` / `terminal_no` / `cart_document` / `signature`）をそのまま使用する。phase 2 では「レスポンスで受領 → 次のリクエストで返送」の往復単位になる。

- **エンベロープ形は変更しない**（`schema_version` 据え置き）。phase 2 で必要な `seq` は `cart_document` 内に含まれるため、エンベロープ自体のスキーマ拡張は不要（R-003）。
- 署名は phase 1 と同一（canonical JSON over HMAC-SHA256、snake_case 表現）。phase 1 発行のスナップショットが phase 2 バックエンドでもそのまま検証・受領できること（FR-011）。

### リクエスト側の搬送（新規）

変更系リクエストボディに任意フィールド `signed_snapshot`（型は `SnapshotEnvelope`、`Optional`）を追加（R-001）。有無で経路が決まる（FR-008）:
- あり → ステートレス経路（検証・再構成・操作適用）
- なし → キャッシュ権威経路（phase 1 挙動、移行期間のみ）

---

## 2. `CartDocument` の拡張

| フィールド | 型 | 説明 | 備考 |
|---|---|---|---|
| `seq` | `int` | 開設セッション内の取引連番（持ち回り）。カート作成時 0、確定のたびに +1 | 新規。`business_counter` と組で取引連番を構成（FR-012） |
| `transaction_datetime` | `str`（仮） | 取引時刻（持ち回り）。確定の決定論化のため、サーバ時刻スタンプではなく carried 値を使う | 新規。`generate_date_time` の供給源（FR-012）。スタンプ点は plan で確定 |

- `seq` / `transaction_datetime` は cart_document に含まれるため、スナップショット（=cart_document の dump）で自動的に持ち回られる。
- `business_counter` は既存（`terminal_info` 経由で取得済み）。cart_document に冗長保持はせず、確定時に `terminal_info.business_counter` から取得する（既存 `tran_service.py:165` を踏襲）。
- 確定時の tranlog 生成は carried snapshot の決定論的関数とする: `transaction_no`=`seq`、`receipt_no`、`generate_date_time` を carried 値から設定し、サーバ時刻スタンプ（現状 `tran_service.py:166`）・サーバカウンタ採番（`:159,173`）をあり経路では使わない。これによりリトライ先でも同一のレシート・台帳になり、先勝ちスキップと整合する。

---

## 3. `BaseTransaction`（tranlog）の拡張 — #152 連携

| フィールド | 型 | 説明 | 備考 |
|---|---|---|---|
| `cart_id` | `Optional[str]` | 取引同一性キー。確定時に `CartDocument.cart_id` を引き継ぐ | 新規（R-004）。下流の冪等収束・整合性検知の基盤 |

- `transaction_no` の**意味が変わる**: 単一端末通し番号 → 開設セッション内連番（`seq`）。値域・採番源が R-003 のとおり変わる。
- 取引の一意性キー: `(tenant_id, store_code, terminal_no, business_counter, transaction_no)`（= `(... , business_counter, seq)`）。ただし**下流の重複排除キーは `cart_id`**（R-005）。

---

## 4. 取引連番の状態遷移（あり経路）

```
カート作成        : seq = 0（未確定）、business_counter = open 時の値（terminal_info）
  ↓ 商品追加・割引等（seq は変化しない・スナップショット往復）
確定(bill) 1 回目  : seq = 1 を採番（端末ローカル、cart_document に反映）
                    tranlog に (business_counter, transaction_no=seq=1, cart_id) を刻む
  ↓ lost-ACK → 同じスナップショット（seq=1 確定前状態 or 確定後状態）を再送
確定(bill) 再送    : 同じ cart_id・同じ (business_counter, seq=1) → 下流 cart_id 冪等で1件に収束
```

- 端末交換（セッション途中）: 代替端末が open → 新 `business_counter` → seq は新エポックで 1 から。旧エポックの番号と衝突しない（FR-012、SC-005）。

---

## 5. 監査レコード（phase 1 を一般化）

phase 1 の `log_cart_restore`（`cart_restore_log_document.py`）を一般化（R-009）。記録は**異常系のみ**。

| フィールド | 説明 | phase 1 からの変更 |
|---|---|---|
| `result` | `rejected` / `existing_returned` / `restored` / `diverged` / `numbering_anomaly` 等 | 値を拡張 |
| `reject_reason` | エラーコード（4015xx 系） | 既存 |
| `api_path` | どの変更系エンドポイントで発生したか | 新規（毎リクエスト検証への一般化） |
| `cart_id` / `snapshot_issued_at` / `snapshot_terminal_no` / `snapshot_kid` / `snapshot_schema_version` | 監査メタ | 既存 |
| `diverged` | 乖離フラグ | 既存 |

- コレクション名は `log_cart_restore` 拡張 or `log_cart_snapshot_event` 改称（tasks で確定）。TTL なし、テナント別 DB。

---

## 6. 下流（report / journal / stock）のインデックス変更 — #152

| サービス | 現行 unique index | 変更後 |
|---|---|---|
| report (tranlog) | `(tenant, store, terminal, transaction_no)` | スキップ判定を `cart_id` 基準に（insert-if-absent）。`(tenant, store, cart_id)` unique を追加。参照用に `(tenant, store, terminal, business_counter, transaction_no)` |
| journal (tranlog) | `(tenant, store, terminal, transaction_no)` | 同上 |
| stock (stock_update) | `(tenant, store, terminal, transaction_no, item_code, update_type)` | 事前チェック（既存ありはバッチスキップ）を `cart_id` 基準に。unique も `transaction_no` を `cart_id` に置換: `(tenant, store, cart_id, item_code, update_type)`。`$inc` + ロールバック保護は温存 |

- 重複時の挙動は**スキップ（insert-if-absent / 先勝ち）**。確定取引ログは不変で重複は同一内容のため後勝ち upsert は不要。既存の下流消費者は既にスキップ型で実装されており、変更はキーの差し替えが主。
- 既存の `event_id` state-store dedup は第一線として維持（Dapr 再配信除け）。cart_id スキップが lost-ACK 再送の最終防壁。
- **注意**: `transaction_no` の seq 再定義（セッション間で非一意化）と下流キーの cart_id 差し替えは**同時適用が必須**。片方だけだと別セッションの同一 seq を誤スキップする。

---

## 7. 影響しないもの

- マスタ（`cart.masters`）の構造・同梱方針（#146 で確定、不変）。
- 署名アルゴリズム・鍵管理（phase 1 FR-011 を継続）。
- account / master-data のスキーマ。
