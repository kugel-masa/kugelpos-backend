# Data Model: 署名付きカートスナップショット + restore API（#148）

**Date**: 2026-06-11 | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

## 1. スナップショットエンベロープ（SnapshotEnvelope — 転送専用、永続化しない）

クライアントに渡り、restore の入力となる構造。cart 内の Pydantic モデルとして定義する（レスポンス埋め込みとリクエストボディの両方で使用）。

| フィールド | 型 | 必須 | 説明 / 検証ルール |
|---|---|---|---|
| `schema_version` | int | ✅ | エンベロープのスキーマバージョン。初期値 `1`。受信時にサポート範囲外なら `401504` で拒否（FR-008） |
| `issued_at` | str (ISO8601 UTC) | ✅ | 発行時刻。監査・差分判断の参考情報（認可判定には使わない） |
| `kid` | str | ✅ | 署名鍵 ID。未知の kid は `401503` で拒否（FR-011） |
| `tenant_id` | str | ✅ | 帰属テナント。認証コンテキストと不一致なら `401505` で拒否（FR-005） |
| `store_code` | str | ✅ | 帰属店舗。不一致なら `401505` で拒否（FR-012） |
| `terminal_no` | int | ✅ | 発行端末。一致は要求しない（FR-012）が監査に記録 |
| `cart_document` | object | ✅ | `CartDocument.model_dump(mode="json")` の全体（`masters` 含む）。復元時は `CartDocument(**cart_document)` で再構築（R-002） |
| `signature` | str (hex) | ✅ | `signature` を除くエンベロープ全体の canonical JSON への HMAC-SHA256（R-003）。不一致は `401501`、欠落/形式不正は `401502` |

**正規化規則（R-003）**: `json.dumps(envelope_without_signature, sort_keys=True, separators=(",", ":"), ensure_ascii=True)` の UTF-8 バイト列に署名する。検証側は受信 dict から `signature` を除いて同一手順で再直列化し、`hmac.compare_digest` で比較する。

**整合性ルール**: `cart_document` 内の `tenant_id` / `store_code` / `terminal_no` とエンベロープの帰属情報は生成時に一致させる。検証時は**エンベロープ側**（署名で保護された値）を認可判定に使う。

## 2. レスポンススキーマの追加フィールド（BaseCart 拡張）

既存フィールドは不変（FR-001 後方互換）。すべて Optional で、未対応クライアントは無視できる。

| フィールド | 型 | 返却条件 | 説明 |
|---|---|---|---|
| `signed_snapshot` | SnapshotEnvelope \| null | カート変更系 + restore のレスポンス | 変更適用後の最新スナップショット。生成失敗時は null（縮退、R-006）。GET には含めない（R-005） |
| `restored` | bool \| null | restore レスポンスのみ | `true` = スナップショットから新規再構築 / `false` = 既存カートを返却（FR-006） |
| `diverged` | bool \| null | restore レスポンスのみ | `true` = 提示スナップショットと既存カートの内容が不一致（差分通知、FR-006） |

**差分判定**: 提示エンベロープの `cart_document` と既存カートの `model_dump(mode="json")` の canonical JSON 同士を比較（バイト列等価）。等価なら `diverged=false`。

## 3. 監査レコード（CartRestoreLogDocument — コレクション `log_cart_restore`）

テナント別 DB `db_cart_{tenant_id}` に新設（R-007）。`BaseDocumentModel` 継承、既存 repository パターンで書き込む。

| フィールド | 型 | 説明 |
|---|---|---|
| `tenant_id` / `store_code` / `terminal_no` | str / str / int | restore を**要求した**端末の帰属（認証コンテキスト由来） |
| `cart_id` | str | 対象カート（スナップショット由来） |
| `result` | str (enum) | `restored` / `existing_returned` / `rejected` |
| `reject_reason` | str \| null | 拒否時のエラーコード（`401501` 等）。成功時 null |
| `diverged` | bool | 差分通知の有無（FR-006/FR-007） |
| `snapshot_issued_at` | str | スナップショット発行時刻（エンベロープ由来） |
| `snapshot_terminal_no` | int | スナップショット発行端末（エンベロープ由来 — 要求端末と異なり得る、FR-012） |
| `snapshot_kid` | str | 検証に使った（または提示された）鍵 ID |
| `snapshot_schema_version` | int | エンベロープのバージョン |
| `event_datetime` | datetime | 記録時刻 |

**インデックス**: `cart_id`、`event_datetime`（FR-007 の cart_id 追跡と時系列監査）。TTL なし（運用判断で後付け可能）。

**記録タイミング**: restore の成功・既存返却・拒否のすべてで 1 レコード。署名検証失敗（`401501`/`401502`/`401503`）も `rejected` として記録し、アプリログ（warning、英語）にも出す（NFR-003）。

## 4. 設定の追加（CartSettings）

| 設定 | env 変数 | 既定値 | 説明 |
|---|---|---|---|
| `SNAPSHOT_HMAC_KEYS` | 同名 | `""`（未設定） | `"<kid>:<base64鍵>[,<kid>:<base64鍵>]"`。先頭 = 現行鍵（署名用）、以降 = 検証のみ受け入れる前世代鍵（R-004）。未設定時はスナップショット機能を縮退し起動時 warning |
| `SNAPSHOT_SIZE_WARN_BYTES` | 同名 | `262144` (256KB raw) | スナップショット raw サイズの warning 閾値（R-008） |

JWT の `SECRET_KEY` は使用しない（FR-011 鍵分離）。前世代鍵の保持は 24 時間以上の運用ルール（ローテーション手順として運用文書に記載）であり、アプリは設定された鍵をすべて検証に受け入れる。

## 5. エラーコード追加（cart_error_codes.py — サブカテゴリ 4015xx、R-010）

| コード | 名前 | 条件 |
|---|---|---|
| `401501` | SNAPSHOT_SIGNATURE_MISMATCH | 署名不一致（改ざん） |
| `401502` | SNAPSHOT_INVALID | 署名欠落・エンベロープ形式不正・パース不能 |
| `401503` | SNAPSHOT_UNKNOWN_KID | 未知の kid / 受け入れ期間外の鍵 |
| `401504` | SNAPSHOT_VERSION_UNSUPPORTED | schema_version 非対応 |
| `401505` | SNAPSHOT_SCOPE_VIOLATION | テナント / 店舗スコープ違反 |
| `401506` | SNAPSHOT_TERMINAL_STATE | 終端状態（completed/cancelled）スナップショットの復元要求 |
| `401507` | SNAPSHOT_GENERATION_FAILED | スナップショット生成の内部失敗（縮退ログ用、API エラーとしては通常返さない） |

各コードは `ErrorMessage` に ja/en 両方のメッセージを追加する。

## 6. 状態遷移と restore の関係

カートの状態機械（initial → idle → entering_item → paying → completed/cancelled）は変更しない。

- **復元可能な状態**: `idle` / `entering_item` / `paying`（スナップショットの `cart_document.status` をそのまま復元し、対応する state クラスで再開）
- **終端状態**（`completed` / `cancelled`）のスナップショット: 復元せず `401506`（冪等応答、FR-007 / Edge Case）。確定処理の冪等性は既存の `cart_id` ベースの取引同一性に依存し、本フィーチャーでは取引ログの二重発行をしないことをテストで保証する
- **restore 成功後**: 通常のカートと完全に同等（Redis キャッシュに書き込み、以降の操作は既存フロー — FR-004/FR-010）
