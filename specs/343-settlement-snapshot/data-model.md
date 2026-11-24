# Data Model: 精算を report が確定するスナップショットにする

**Feature**: 343-settlement-snapshot | **Date**: 2026-11-24（レビューの反映: 2026-11-24）

## 1. 精算実績 `settlement_record`（report、テナントごとのデータベース、新規）

1つの営業に1件。「仮」のあいだは作り直され、「確定」したら変わらない（R-6）。

| 項目 | 型 | 内容 |
|---|---|---|
| `tenant_id` | str | |
| `store_code` | str | |
| `terminal_no` | int | |
| `business_counter` | int | 営業の番号。鍵の一部 |
| `business_date` | str (YYYYMMDD) | 営業日 |
| `open_counter` | int | その営業日の何回目の開設か |
| `state` | str | `provisional`（仮）/ `final`（確定） |
| `settlement_id` | str (uuid) | 精算実績の識別子。作り直すたびに新しくなる |
| `settled_by` | str \| None | 精算した担当者（`staff:<id>`） |
| `settled_at` | str | 端末が精算した日時（要求の値） |
| `recorded_at` | str | report が保存した日時 |
| `cutoff` | datetime | 計算を始めた時刻（記録のため）。数字は、このとき1回だけ読んだログの集合から作る（R-12） |
| `finalized_at` | str \| None | 確定した日時（閉設ログを受け取った日時） |
| `declared_count` | int \| None | 名乗った番号（`seq`） |
| `declared_source` | str | `pos`（名乗りあり）/ `none`（名乗りなし） |
| `included_count` | int | 届いた件数（カート単位、R-2） |
| `included_ranges` | list[{first:int, last:int}] | 運ぶ番号の系列の、届いた範囲 |
| `missing_count` | int | 運ぶ番号の系列の、未着の件数 |
| `missing_ranges` | list[{first:int, last:int}] | 運ぶ番号の系列の、未着の範囲 |
| `duplicate_numbers` | list[int] | 違うカートが同じ番号を持つもの |
| `server_numbered_count` | int | サーバー側で振った番号の取引の件数（R-13） |
| `declared_cash_log_count` | int \| None | 端末が名乗った入出金の件数 |
| `cash_log_count` | int | 届いた入出金ログの件数 |
| `missing_cash_log_count` | int | 入出金の未着の件数（名乗りが無ければ 0） |
| `expected_cash` | object | 理論在高の内訳: `cash_sales`、`cash_in {amount, count}`、`cash_out {amount, count}`、`total` |
| `created_at`・`updated_at` | datetime | 初めて保存した時刻・最後に書いた時刻 |
| `physical_amount` | float \| None | 数えた現金 |
| `difference` | float \| None | `physical_amount − expected_cash.total`。数えていなければ `None` |

**索引**:
- 一意: `(tenant_id, store_code, terminal_no, business_counter)`
- 非一意: `(tenant_id, store_code, business_date)` — 店舗・期間の日報と照会
- 非一意: `(tenant_id, store_code, terminal_no, business_date, open_counter)` — 端末の日報

**状態の遷移**:

```
(無し) --精算の依頼--> provisional --精算の依頼--> provisional（作り直し、settlement_id が新しくなる）
provisional --同じ settlement_id の閉設ログ--> final
provisional --違う settlement_id の閉設ログ--> final（閉設ログの settlement_id で計算し直す・R-6）
final（以後変わらない。精算の依頼には保存済みの値を返す）
```

## 2. 確定集計 `settlement_daily_report`（report、新規）

精算実績1件につき、日報の種類ごとに1件（R-17）。精算実績と同じトランザクションで書く。

| 項目 | 型 | 内容 |
|---|---|---|
| `tenant_id` | str | |
| `settlement_id` | str | 精算実績の識別子 |
| `store_code`・`terminal_no`・`business_counter` | | 精算実績と同じ |
| `report_type` | str | `sales`・`category`・`item`・`payment`・`promotion` |
| `report` | object | その種類の日報の文書を `model_dump()` したもの |

**索引**: 一意 `(tenant_id, settlement_id, report_type)`。

## 3. 取引ログ・入出金ログ・開閉ログ（report、既存）

形は変えない。索引を足す:
- `log_tran`・`log_cash_in_out`・`log_open_close`: `(tenant_id, store_code, business_date, terminal_no, business_counter, open_counter)` — 未精算の判定（R-18）
- `log_cash_in_out`: `(tenant_id, store_code, terminal_no, business_counter)` — 精算実績の計算

## 4. 閉設ログ `log_open_close`（report・terminal・journal、既存）

閉設ログに項目を足す（すべて任意、既存の文書はそのまま読める）。

| 項目 | 型 | 内容 |
|---|---|---|
| `settlement_id` | str \| None | 精算実績の識別子。report はこれで精算実績を確定する |
| `expected_cash` | float \| None | 理論在高（`expected_cash.total`） |
| `difference` | float \| None | 過不足 |
| `missing_count` | int \| None | 取引の未着の件数 |
| `missing_cash_log_count` | int \| None | 入出金の未着の件数 |

意味が変わる項目:
- `cart_transaction_count`・`cart_transaction_last_no`: 端末の名乗り（`seq`）。無ければ `None`（今は cart に問い合わせた件数と最後の番号）

## 5. 端末 `info_terminal`（terminal、既存）

形は変えない。精算のとき `physical_amount` に精算実績の値を入れる。閉設の更新は、状態が `Opened` であることを条件にする（R-7）。

## 6. 日報の文書（report、既存のレスポンスの形）

5種類の日報の文書に、項目を足す（任意、daily のみ）。

| 項目 | 型 | 内容 |
|---|---|---|
| `missing_count` | int \| None | 対象の営業の未着の件数の合計 |
| `missing_ranges` | list[{terminalNo, businessDate, businessCounter, first, last}] \| None | 営業ごとの未着の範囲（店舗・期間の日報で端末が分かるように） |

## 7. DailyInfo `info_daily`（report、既存）

日報の経路から外す（読み書きしない）。コレクションとデータは残す。
