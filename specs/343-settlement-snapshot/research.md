# Research: 精算を report が確定するスナップショットにする

**Feature**: 343-settlement-snapshot | **Date**: 2026-11-24（レビューの反映: 2026-11-24）

調べた事実は main（e9405001）のコードを読んだもの。Fable と codex のレビュー（2026-11-24）で見つかった問題を、R-12 以降と各節に反映した。

---

## R-1: 営業の単位

**Decision**: 精算実績は `(tenant_id, store_code, terminal_no, business_counter)` に1件。精算実績は、その営業の `business_date` と `open_counter` も持ち、日報の要求（`business_date`・任意の `open_counter`・任意の `business_counter`）から引けるようにする。

**Rationale**:
- `business_counter` は開設のたびに増え、二度と使われない。取引ログ・入出金ログ・開閉ログはどれも持っている
- `open_counter` は端末を登録し直すと 1 に戻る（`report/app/models/repositories/open_close_log_repository.py:59-62` のコメント）。`(business_date, open_counter)` では、登録し直した端末の同じ日の営業が重なる。精算の計算と確定集計は、必ず `business_counter` で絞る（R-4）

---

## R-2: 精算実績の計算

**Decision**: report は、精算の要求を受けた時点で、その営業（`business_counter`）について次を数える。読み取りはすべて同じ締めの時刻（R-12）で絞る。

| 項目 | 数え方 |
|---|---|
| 届いた件数 `included_count` | `cart_id` を持つ取引は `cart_id` の種類の数、`cart_id` の無い取引は1件ずつ |
| 番号の系列 | `receipt_counter` を持つ取引（カートが運ぶ番号、営業の中で 1 から）と、持たない取引（サーバー側の番号、端末全体で増える）に分ける（R-13） |
| 届いた番号の範囲 `included_ranges` | 運ぶ番号の系列について、連続した範囲 `[{first, last}]` |
| 未着 `missing_ranges` / `missing_count` | 運ぶ番号の系列について、名乗った番号 `seq` があれば 1〜`seq`、無ければ届いた最小〜最大のあいだで届いていない番号 |
| 重複 `duplicate_numbers` | 運ぶ番号の系列で、同じ番号を違う `cart_id` が持つもの |
| サーバー側の番号の件数 `server_numbered_count` | 範囲の分析をせず、件数だけ |
| 入出金の件数 `cash_log_count` | その営業の入出金ログの件数 |
| 入出金の未着 `missing_cash_log_count` | 端末が名乗った入出金の件数（要求の `cashLogCount`）から、届いた件数を引いたもの（負なら 0） |
| 理論在高 `expected_cash` | R-3 |
| 数えた現金・過不足 | 要求の値。過不足は `physical_amount − expected_cash.total`、数えていなければ `None` |
| 確定集計 | R-4 |

取消された取引（`sales.is_cancelled`）も番号を持つので、件数と番号には含める。売上の集計からは、今の日報と同じく除かれる（集計の条件 `sales.is_cancelled: False`）。番号が 1 未満・無い取引は、件数と番号から除くが、確定集計には今の日報どおり含まれる。

---

## R-3: 理論在高の式を1か所に置く

**Decision**: 今の売上レポートの現金の欄の式を、report の中のモジュール `app/services/expected_cash.py` に移す。売上レポートのプラグインと精算実績の両方がそれを呼ぶ。

```
total = 現金の支払（支払コード "01"）+ 入金（正の入出金の合計）+ 出金（負の入出金の合計）
```

内訳は `cash_sales`・`cash_in {amount, count}`・`cash_out {amount, count}`・`total`。釣銭準備金は開設時の入金ログとして `cash_in` に入っている。

**Rationale**: この式を使うのは report だけ（terminal は理論在高を計算しない）。report の中の1か所に置けば、精算実績と売上レポートが食い違わない（FR-007・SC-005）。

---

## R-4: 確定集計の作り方

**Decision**:
- 5つのプラグインの集計（パイプライン、入出金と開閉ログの取得）に、任意の `business_counter` の絞り込みを足す。渡されたときは `business_counter` で絞る。日報の照会（その場で集計する速報・既存の呼び出し）は今までどおり
- 精算の確定のとき、5つのプラグインを `report_scope="daily"`、`business_counter`・`business_date`・`open_counter`・端末を指定し、**件数の区切りなし**で呼ぶ。区切りなしは、パイプラインの `$skip`/`$limit` と、入出金・開閉ログの取得の `limit` を外すことを意味する（今は呼び出し元の `limit` で切られる）
- 1つでも失敗したら、精算の確定そのものを失敗にする（R-15）
- 売上レポートの現金の欄（`cash`）は、精算実績の値で上書きする: `logical_amount`=`expected_cash.total`、`physical_amount`、`difference_amount`、`cash_in`・`cash_out`。上書きのあとにレシートとジャーナルの本文を作り直す（`SalesReportReceiptData`）。精算の確定の時点では閉設ログがまだ無いため、上書きしないと「数えていない」になる
- 確定集計は精算実績の文書に埋め込まず、別のコレクション `settlement_daily_report` に `(settlement_id, report_type)` ごとに1件で保存する（R-17）

---

## R-5: 日報を確定集計から返す

**Decision**:
- 対象の営業: 端末の日報は `(terminal_no, business_date[, open_counter][, business_counter])`、店舗の日報は `(store_code, business_date[, open_counter])`、期間の日報は `business_date_from`〜`business_date_to`
- 対象の範囲で、開設ログ・取引ログ・入出金ログのいずれかがある営業 `(terminal_no, business_counter)` を集める。そのうち**確定した**精算実績（R-14）が無いものがあれば、`412101` で断り、未精算の営業の一覧を応答に載せる（R-16）
- 対象の営業が1つも無ければ、空の日報を 200 で返す（今と同じ。既存の e2e が依存している）
- 確定集計を合算する。各プラグインに `merge(reports)` を実装する（入口は `report_plugin_interface.py:58-89` にある）。1件だけなら `from_saved(report)` で文書に戻す
- 合算の規則:
  - 金額・件数・数量は足す
  - 売上: 税の行は `tax_name` を鍵に寄せる（`TaxReportTemplate` に `tax_code` は無い）。支払の行は `payment_code` を鍵に寄せ、内訳（`variants`）は `variant_code` で寄せる。名前は、最も新しい精算（`settled_at`）のものを使う。現金の欄は各項目を足し、`physical_amount` と `difference_amount` は、1つでも数えていない営業があれば `None`
  - 支払レポート: `payment_code` で寄せ、`ratio` を合算のあとに計算し直す
  - 部門・商品・プロモーション: それぞれのコードで寄せて足す。合計の項目は行から計算し直す
  - 合算のあとにレシートとジャーナルの本文を作り直す（プロモーションはレシートを持たない）
- 応答に `missing_count` と `missing_ranges`（営業ごと）を足す
- 速報は今までどおりその場で集計する
- 日報（daily）は確定集計を丸ごと返し、`limit`・`page` は使わない。後方互換性の節に、意図した変更として書く
- 期間の日報は、今は現金の欄が空（入出金を数えない）だが、確定集計の合算で現金の欄が入る。意図した変更として書く

---

## R-6: 保存の規則（仮と確定）

**Decision**: 精算実績は「仮」（`provisional`）と「確定」（`final`）の2つの状態を持つ。

| 状況 | 動き |
|---|---|
| 精算実績が無い | 計算して「仮」として保存し、返す |
| 「仮」がある（前の精算の閉設が失敗した、または閉設ログがまだ届いていない） | 計算し直して置き換え、返す（`settlement_id` は新しくする） |
| 「確定」がある | 計算せず、保存されている値を返す（`created: false`） |
| report に、`settlement_id` を持つ閉設ログが届いた | 同じ営業の「仮」で `settlement_id` が一致すれば「確定」にする。一致しない・精算実績が無いときは、閉設ログの `settlement_id` で計算し直して確定する（下の「同時に2つの精算」）。確定できなければ例外にして、閉設ログの配信をやり直させる |

書き込みは `(tenant, store, terminal_no, business_counter)` を鍵にした upsert で、条件 `state != final` を付ける。確定したものは二度と書き換わらない。利用者が選んだ（2026-11-24）。

**Rationale**: report が精算実績を保存したあとに terminal の閉設が失敗する（応答のタイムアウト、terminal のトランザクションの失敗）と、端末は開設のまま販売を続けられる。精算実績が最初の1回で固まると、そのあいだの販売が日報から永久に抜ける（Fable C1・codex Critical）。閉設ログが report に届いた時点で確定させれば、「端末が閉じた営業の精算実績だけが不変」になる。

**同時に2つの精算**: terminal は、端末の更新に条件（状態がまだ `Opened`）を付け、同じ端末の同時の精算のうち1つだけが閉設ログを書く（R-7）。もう一方は `406003`（端末の状態のエラー。既存の挙動）。閉設ログが運ぶ `settlement_id` は、閉設を書いた側が受け取った精算実績のもの。もう一方の精算が report で後から「仮」を置き換えていた場合、`settlement_id` が一致せず確定しない。その場合に備え、閉設ログを受け取った report は、一致しない「仮」を、閉設ログの `settlement_id` の値で計算し直して確定する（同じ時点のログを読み直す。閉設の直後なので差はほぼ無い）。

---

## R-7: terminal の精算の流れ

**Decision**: `close_terminal_async` を次の順にする。

1. 端末の状態を確かめる（今と同じ。閉設済みは `406003`（端末の状態のエラー。既存の挙動））
2. report の確定の口を呼ぶ。トークンは `create_service_token(tenant_id, "terminal")`、接続先は `BASE_URL_REPORT`。タイムアウトは 30 秒、再試行なし（1回だけ試す。既定の 3 回は、集計が重いと 2 分を超える）
3. 結果の扱い:
   - 200: 続ける
   - 接続できない・タイムアウト・5xx・404（口が無い古い report）・401/403（設定の誤り）: `406016`（503）。何も書かない
   - 400/422: terminal の不具合として `406008`（HTTP 400、既存の閉設のエラー）
4. 返った精算実績で閉設ログを作る（`expected_cash`・`difference`・`settlement_id`・`missing_count`・`missing_cash_log_count`。`cart_transaction_count`・`cart_transaction_last_no` は `seq`、無ければ `None`）
5. 端末の `physical_amount` は精算実績の値にする
6. レシートに理論在高・過不足・未着の行を足す
7. 端末の更新（条件: 状態がまだ `Opened`）・閉設ログ・配信状態を1つのトランザクションで書き、発行する。条件に合わなければ（同時の精算が先に閉じた）`406003`（端末の状態のエラー。既存の挙動）

cart への取引の問い合わせ（`tran_log_repo.get_tran_log_list_async`）は外す。入出金の件数は今までどおり terminal の手元で数え、要求で report に渡す（`cashLogCount`）。

閉設済みの端末への再送は `406003`（端末の状態のエラー。既存の挙動） のまま（利用者が選んだ、2026-11-24）。精算の内容は、精算実績の一覧と閉設ログで確かめられる。

---

## R-8: サービス間の認証と、確認の口

**Decision**: report に `app/api/v1/settlement_internal.py`（`APIRouter(prefix="/internal")`）を置き、`Depends(get_service_account_info)` とパスのテナントの照合（master-data の `internal.py` と同じ形）。精算実績の一覧（利用者向け）は、利用者のトークンだけを受け付け、端末の API キー・端末のトークンは受け付けない（本部の照会）。

terminal に精算前の確認の口 `GET /api/v1/terminals/{terminal_id}/close-preview` を置き、そこから report の内部の確認の口を呼ぶ（端末は report の内部の口を直接呼べない・FR-022）。

---

## R-9: エラーコード

| コード | 意味 | HTTP |
|---|---|---|
| `412101` | 精算していない（意味を変える） | 403（今と同じ） |
| `413007` | 精算実績が見つからない（照会） | 404 |
| `413008` | 精算の確定の集計に失敗した（R-15・R-17） | 500 |
| `406016` | 精算のとき report で確定できない | 503 |

`412102`〜`412107` は日報の経路から投げなくなるが、番号は残す。`docs/{en,ja}/general/error_code_spec.md` を更新する。

---

## R-10: 既存のテナントと DailyInfo

- `report` の `database_setup.execute()` に `settlement_record`・`settlement_daily_report` と、その索引、R-18 の索引を足す。起動時の索引の整備（`start_index_ensure_in_background`、既定で有効）が既存のテナントにも足す
- `DailyInfoDocument` と `info_daily` は日報の経路から外す。コレクションとデータは残す

---

## R-11: 配備の順序と移行

- report を先に配備する。terminal を先に入れると、確定の口が無く `406016` で精算が断られる
- 配備より前に精算を終えた営業と、report だけを先に配備したあいだに古い terminal で精算した営業は、精算実績が無く、それらを含む日報（期間の日報を含む）は `412101` になる。利用者が受け入れた（2026-11-24）
- `BASE_URL_REPORT` は docker-compose には設定済み。Azure Container Apps の terminal の環境変数にも要る（既定値は `localhost:8004`）。配備の手順書（`/deploy`）で確かめる

---

## R-12: 精算の計算を同じ時点のデータで行う

**Decision**（PR のレビューで改めた、2026-11-25）: 計算の最初に、その営業の取引ログと入出金ログを1回だけ読み、その `_id` の集合を決める。件数・番号・理論在高・5つの確定集計は、すべてその `_id` の集合だけから作る（プラグインには `extra_match: {_id: {$in: …}}` と、入出金には `cash_extra_match` を渡す）。時計を使わないので、書き込みの確定が遅れた文書も、report を複数台で動かしたときの時計のずれも、数字を食い違わせない。`cutoff` は記録のためにだけ残す。

**前の Decision**（実装の段、レビューで退けた）: 精算の確定と確認の計算を始めるときに、締めの時刻 `cutoff` を1つ決める。件数・番号・入出金・5つの確定集計のすべてのクエリに、「report に届いた時刻（`created_at`）が `cutoff` より後ではない」という条件を足す（`{"created_at": {"$not": {"$gt": cutoff}}}`。`created_at` の無い古い文書も含める）。精算実績に `cutoff` を記録する。

**前の方式の穴**（Fable のレビュー S1）: `created_at` は、書き込みが確定する前にアプリで付ける。締めの時刻より前の `created_at` を持つのに、件数を数えたあとで確定する取引があり、件数では「未着」なのに理論在高には入ったまま凍結された（再現した）。report が複数台なら、時計のずれでこの隙間が広がる。

**Rationale**（前の方式のもの）: 計算は複数のクエリに分かれる。そのあいだに取引が届くと、売上には入らず商品には入る、といった食い違いが永久に残る（codex Critical）。report は取引ログ・入出金ログ・開閉ログを `insert_if_absent` で保存し、そのときに `created_at`（届いた時刻）を必ず入れる（`app/models/repositories/insert_if_absent.py`）。締めの時刻で絞れば、どのクエリも同じ集合を見る。

**Alternatives considered**: MongoDB のトランザクションの中で読み取りの一貫性 `snapshot` で読む（計画の時点の案）: commons の `AbstractRepository` の読み取り（`find`・`count_documents`・`aggregate`）がセッションを渡さないため、commons を変えて全サービスの依存を上げることになる。トランザクションの寿命（60 秒）と、集計の途中の master-data への問い合わせとの兼ね合いも要る。不採用。

**名前の問い合わせ**: プラグインは集計の途中で master-data に名前を問い合わせる（部門・支払。既定はタイムアウト 30 秒・再試行 3 回）。締めの時刻の方式ではトランザクションの寿命の問題は無いが、精算の要求の処理時間に効く。精算の確定では、名前を先に1回だけ取り（短いタイムアウト 5 秒・再試行なし。届かなければ今と同じくコードを名前の代わりに使い、ログに残す）、5つのプラグインに渡す。プラグインに「名前を外から渡す」入口を足す（渡されなければ今どおり自分で問い合わせる）。

---

## R-13: 番号の系列が2つある

**Decision**: 未着と重複は、`receipt_counter` を持つ取引（カートが運ぶ番号、営業の中で 1 から振られる）だけで分析する。`receipt_counter` を持たない取引（サーバー側の番号、端末全体で増える）は件数だけ数える（`server_numbered_count`）。`seq` は運ぶ番号の系列の最後の番号を意味する。

**Rationale**: DUAL のモードでは、同じ営業の中に、運ぶ番号（1..N）とサーバー側の番号（端末全体の通し番号）が混ざる（`cart/app/services/tran_service.py:204-229`）。混ぜて分析すると、偽の未着と重複が出る（Fable S1）。サーバー側の番号の取引は `receipt_counter` を記録しない（`tran_service.py:223-224` のコメント）ので、それで分けられる。

---

## R-14: 日報は確定した精算実績だけを使う

**Decision**: 日報（daily）が使うのは「確定」の精算実績だけ。「仮」しか無い営業は「精算していない」と同じ扱い（`412101`）。精算実績の一覧は、状態（`provisional`/`final`）を返す。

**Rationale**: 「仮」は、閉設が終わっていないか、閉設ログがまだ届いていない営業。その日報を出すと、あとで値が変わりうる。閉設ログは terminal の未配信の再送で必ず届く。

---

## R-15: 確定集計の失敗

**Decision**: 5種類のどれかの集計が失敗したら、精算実績を保存せずに `413008`（500）を返す。terminal はそれを `406016`（503）として扱い、端末は開設のまま。もう一度精算すれば、5種類がそろった精算実績ができる。利用者が選んだ（2026-11-24）。

**Rationale**: 欠けた確定集計が永久に残り、その種類の日報が二度と出せなくなるのを避ける。

---

## R-16: 未精算の一覧の返し方

**Decision**: report に `SessionNotSettledException`（`412101`、403）を置き、未精算の営業の一覧を持たせる。report の `main.py` で、この例外の専用の処理を登録し、`ApiResponse` の `data` に `{"unsettledSessions": [{terminalNo, businessCounter, businessDate, openCounter}]}` を入れて返す。commons の共通の処理（`data` は常に `None`、`exception_handlers.py:188`）は変えない。日報の経路の `except Exception` で包み直されないよう、この例外は包まずに送り出す。

**Rationale**: commons を変えずに、report の中で完結させる（Fable C4）。Starlette は例外の型に合う処理を、より具体的な型から選ぶ。

---

## R-17: 確定集計の保存先

**Decision**: 確定集計は `settlement_daily_report`（`settlement_id`・`report_type`・`report`）に、種類ごとに1件で保存する。精算実績の文書には含めない。日報は必要な種類だけを読む。一覧は精算実績だけを読む。

**Rationale**: 商品の日報は、商品ごとの行に加えて、レシートとジャーナルの本文にも同じ商品が並ぶ。品数の多い店舗では1件の文書が大きくなる。種類ごとに分ければ、1件あたりは1種類分で、日報も必要な種類だけを読む。

**大きさの上限**: 1種類分が MongoDB の 1 文書の上限（16 MB）を超えると保存できない。保存の前に大きさを確かめ、超えるなら `413008` で断る（端末は開設のまま）。今の規模の見込みでは届かない（1種類で数 MB 未満）。

**保存の順番**: 「仮」の精算実績と確定集計は、同じトランザクションで書く（作り直しのときは古い確定集計を消して書く）。精算実績だけがあって確定集計が無い、という状態を作らない。

---

## R-18: 未精算の判定の索引

**Decision**: `log_tran`・`log_cash_in_out`・`log_open_close` に `(tenant_id, store_code, business_date, terminal_no, business_counter, open_counter)` の索引を足す。日報のたびに、対象の範囲の営業を集めるため。`open_counter` は集める処理の `$group` が読むので、索引に含めて本体を読まずに済ませる（レビューで足した）。`business_counter` の無いログは、精算できる営業が無いので、未精算の判定から外す。

---

## R-19: テストの計画（レビューで足したもの）

統合テスト（実際の MongoDB）:
- 計算の途中で取引が届いても、件数・確定集計・理論在高が同じ時点を表す（R-12）
- 端末を登録し直して、同じ営業日・同じ `open_counter` の営業が2つあっても、確定集計が混ざらない（R-1・R-4）
- 運ぶ番号とサーバー側の番号が混ざった営業で、偽の未着・重複が出ない（R-13）
- 「仮」の作り直し、閉設ログでの確定、確定のあとの不変、`settlement_id` が一致しない閉設ログ（R-6）
- 集計の失敗で何も保存されない（R-15）
- 確定集計が件数の区切りで切られない（大量の取引・部門・商品）
- 合算の規則（税・支払と内訳・部門・商品・プロモーション、数えていない営業を含む現金の欄）
- 未精算の判定、空の範囲の 200、`412101` の一覧

terminal（unit・統合）:
- report の結果ごとの扱い（200・タイムアウト・5xx・404・401/403・4xx）
- 精算の処理中の同時の精算（R-7 の条件付きの更新）
- 閉設ログ・レシート・応答の項目、確認の口
- cart への問い合わせをしない

e2e:
- 販売・入出金が report に届くのを待ってから精算し（`wait_for`）、精算実績・端末と店舗の日報を確かめる
- report を止めて精算 → `406016`、端末は開設のまま
- 精算のあとに届いた取引で日報が変わらない
- 既存の e2e（report の e2e はログを直接入れて日報を読む）を、確定の口を通す形に直す

書き直す既存のテスト:
- report: `412102`〜`412107` と DailyInfo を前提にしたテスト、`ReportService(daily_info_repository=...)` を組み立てる統合テスト
- terminal: cart の取引の問い合わせを差し替えているテスト（`tran_log_repo`）、閉設の統合テスト（report の口を respx で差し替える）
- `tests/e2e/test_report_error_codes.py` の `412101` の期待


---

## R-20: PR のレビューで直したこと（2026-11-25）

Fable と codex のレビュー（PR #345）の指摘を、確かめた上で直した。

| 指摘 | 直したこと |
|---|---|
| 内部の精算の口が、呼び出し元が terminal かを確かめていない（codex P1） | サービスアカウントの `service` が `terminal` でなければ 403。サービスどうしは同じ鍵を共有しているので多層防御の意味だが、最小の権限にそろえる |
| 締めの時刻だけでは、全部のクエリが同じ集合を見ない（S1） | R-12 を改めた（`_id` の集合で固定する） |
| 閉設ログが届かない営業が、日報を永久に止める（S2） | 管理者の精算の口を足した（R-21） |
| 店舗・期間の日報の `missingRanges` で、どの端末の未着か分からない（S3） | 各範囲に `terminalNo` と `businessDate` を足した |
| 同時に2つ精算したとき、負けた側が 406003 にならない（S4） | terminal: 書き込みの衝突（WriteConflict、112）を「閉設済み」（406003）として扱う。report: 一時的なトランザクションの失敗（TransientTransactionError）は、間を置いて最大 8 回やり直す |
| 閉設ログの照合が食い違ったとき、2回目の確定の結果を見ていない（S5） | 確定できなければ例外にし、閉設ログの配信をやり直させる |
| report への依頼の「再試行 1 回」 | `HttpClientHelper` の `max_retries` は試す回数なので、実際は再試行なし。待ち時間を延ばさないよう、そのままにして説明を直した |
| 精算実績の `created_at`・`updated_at` が空 | 入れる |

## R-21: 管理者の精算

**Decision**: `POST /api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlements`（利用者またはサービスのトークン、テナントの一致を確かめる）。要求は `businessCounter`、`reason`（必須、500 字まで）、`physicalAmount`（任意）。届いているログからその営業の精算実績を作り、すぐに「確定」にする。精算実績に `settled_kind = "admin"`、`admin_reason`、`settled_by = "admin:<利用者>"` を記録し、警告のログを残す。営業の日付と開設の回数は、その営業のどれかのログから取る。ログが1件も無ければ 404 `413007`。すでに確定していれば、保存されている値を返す（`created: false`）。

**Rationale**: 精算実績を書くのは端末の閉設だけで、閉設済みの端末は 406003 で精算できない。開設中のまま端末を消した・オフラインの営業・配信が死んだ閉設ログの営業は、その営業を含む日報を永久に止める（Fable S2）。利用者が「管理者の精算の口を足す」を選んだ（2026-11-25）。

**注意**: まだ販売している端末の営業に使うと、そのあとの販売が日報から抜ける。API の説明に書いた。
