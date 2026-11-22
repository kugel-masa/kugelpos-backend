# Research: 支払マスタのサブコード（派生）

**Feature**: [spec.md](spec.md) | **Date**: 2026-11-22

現行コードの調査結果と、設計の判断をまとめる。各項は Decision / Rationale / Alternatives considered の形で書く。

---

## R-1: サブコードの置き場所（支払マスタの文書に内包する）

**Decision**: `master_payment` コレクションの支払方法の文書に `variants: list[PaymentVariant]` を内包する。別コレクションは作らない。

**Rationale**:
- cart は支払方法を 1 件ずつ取得してキャッシュしている（`PaymentMasterWebRepository._fetch_one` → `GET /tenants/{tenant_id}/payments/{payment_code}`）。内包すれば、取得 1 回・キャッシュ 1 件のまま、サブコードの判定に必要な情報が揃う
- 支払方法の削除でサブコードも消える（FR-009）ことが、文書の削除だけで成り立つ
- サブコードは支払方法ごとに数十件程度（Assumptions）で、文書の大きさの問題にならない

**Alternatives considered**:
- 別コレクション `master_payment_variant`: cart の取得が 2 回になるか、master-data で結合が要る。削除の連動も別に書く必要がある
- 支払方法の文書を増やす（サブコードごとに支払コードを作る）: 支払プラグインの登録（`plugins.json`）が支払コードに束縛されているので、サブコードごとにプラグインの登録が要る。本フィーチャーが解く問題そのもの

---

## R-2: サブコードの一意性と更新の原子性

**Decision**: 一意性は「支払方法の中で一意」（FR-002）。索引ではなく、条件付きの原子更新で守る。
- 追加: フィルタ `{tenant_id, payment_code, "variants.variant_code": {"$ne": code}}` に `$push`。一致 0 件なら、支払方法の有無を引き直して「支払方法が無い」（404）か「重複」（409 相当の既存の例外）を返す
- 変更: フィルタ `{tenant_id, payment_code, "variants.variant_code": code}` に位置指定の `$set`（`variants.$.name`・`variants.$.is_active`・`variants.$.updated_at`）と文書の `updated_at`。時刻の項目名は、master-data のリポジトリが継承している共通ライブラリの `AbstractRepository` に合わせる（`created_at`・`updated_at`。master-data の `app/models/repositories/abstract_repository.py` は使われていない古い複製で、`updated_on` を書くが参照しない・#312）

**Rationale**:
- MongoDB の一意索引は、同じ文書の配列の中の重複を防がない。支払方法の中での一意性は索引では表せない
- テナント全体の一意性（`{tenant_id, variants.variant_code}`）は要らない。取引の支払行は支払コードとサブコードを両方持つので、支払方法をまたいで同じコードがあっても曖昧にならない（spec US1 シナリオ 3）
- 条件付きの `$push` は 1 文書への 1 操作なので、同時の 2 件の追加でも重複が入らない

**Alternatives considered**:
- 読んでから書く（取得 → 重複確認 → 文書の置換）: 同時の追加で重複や上書きが起きる
- `$addToSet`: 名前や有効フラグが違えば別の要素として入るので、コードの一意性を守れない

---

## R-3: 支払マスタの作成・更新の要求とサブコード

**Decision**: 既存の作成・更新の要求スキーマ（`BasePaymentCreateRequest`・`BasePaymentUpdateRequest`）は変えない（サブコードを受けない）。応答スキーマ（`BasePaymentResponse`）に `variants` を加える。

**Rationale**:
- 更新は `AbstractRepository.update_one_async` の `$set` で、要求に含まれる項目だけを書く。要求にサブコードが無ければ既存のサブコードは残る（FR-008）。追加の処理は要らない
- 作成時のサブコードは空。サブコードは専用の API で足す
- 応答に足すだけなので既存のクライアントは影響を受けない

**Alternatives considered**:
- 更新の要求でサブコードの一覧を丸ごと受ける: 一覧を送らないクライアントがサブコードを消してしまう、あるいは「送らない」と「空にする」の区別が要る。API が分かれている方が安全

---

## R-4: サブコードの API の形

**Decision**: v1 の支払マスタのリソースの下に置く。
- `POST /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants`（201）
- `GET /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants`
- `GET /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants/{variant_code}`
- `PUT /api/v1/tenants/{tenant_id}/payments/{payment_code}/variants/{variant_code}`

`DELETE` は置かない（FR-006）。権限は既存の支払マスタの端点と同じ依存を使う（書き込みは `get_tenant_id_refusing_terminal`、読み取りは `get_tenant_id_with_security_by_query_optional`）（FR-010）。

**Rationale**:
- 既存の支払マスタの端点が v1 にあり、サブコードはその子リソースである。複数形（`/variants`）・パス引数の snake_case（`{variant_code}`）は API 命名規約（`.claude/rules/api-naming-convention.md`）に沿う
- 一覧はページングしない。1 つの支払方法のサブコードは数十件程度で、支払方法の取得の応答にも全件入る

**Alternatives considered**:
- 支払マスタの更新に含める: R-3 のとおり
- `DELETE` を置いて物理削除: 削除後に同じコードを別の意味で登録できてしまい、集計でコードの意味が時期によって変わる。停止で表す（spec FR-006）

---

## R-5: サブコードのコードと名前の検証

**Decision**: 要求スキーマで検証する。
- `variant_code`: 正規表現 `^[A-Za-z0-9_-]{1,20}$`（大文字・小文字を区別、正規化しない）
- `name`: 空でない文字列（前後の空白だけのものも空とみなす）

違反は既存の検証エラー（422）で答える。

**Rationale**: パス引数にも使う値なので、URL で扱いにくい文字を避ける。既存のマスタの検証と同じく、スキーマで弾けば業務の層は値が正しい前提で書ける。

---

## R-6: cart でのサブコードの決定の置き場所

**Decision**: サブコードの決定は純関数 `resolve_sale_variant(pay_doc, requested_code)`（新設 `app/services/logics/payment_variant_logic.py`）に置き、`CartService.add_payment_to_cart_async` が支払プラグインを呼ぶ前に呼ぶ。要求の配列のすべての要素について、どのプラグインも呼ぶ前に支払マスタを読んでサブコードを決め終える（1 つでも拒否なら、どのプラグインも呼ばずに失敗する）。決めたサブコードは `pay()` のキーワード引数 `variant_code` でプラグインへ渡し、組み込みのプラグイン（現金・キャッシュレス・その他）はそれを `settle_payment_async(..., variant_code=...)` へそのまま渡す。`settle_payment_async` → `_build_cart_payment` が支払行にサブコード・名前・支払方法の名前を書く。

プラグインを呼んだ後、`CartService` は今回追加された支払行がすべて決めたサブコードを持つことを確かめ、持たなければ `ServiceException` で失敗させる。

**要求の途中で拒否されたとき**: 現行の `add_payment_to_cart_async` は、読み込んだカートをメモリ上で要素ごとに変更し、最後に 1 回だけキャッシュへ保存する。途中で例外になれば保存されないので、保存されたカート（スナップショットの経路ではクライアントの持つスナップショット）は要求の前のまま。サブコードの拒否は上のとおりプラグインを呼ぶ前に起きるので、プラグインの副作用も生じない。サブコード以外の拒否（403004・403017 等）が 2 件目で起きる場合の扱いは現行どおり。

**Rationale**:
- 決定はプラグインによらない業務ルール（spec FR-013・FR-014）なので、プラグインの外で 1 回だけ行う。外部のプラグインが規則を写し間違える余地を作らない
- #308 で `pay()` の契約は「呼び出し側は追加のキーワード引数を渡してよい。実装は受け取らねばならず、扱えない値を黙って捨ててはならない」と定めた。`variant_code` はこの契約にそのまま乗る
- 事後の確認は、`variant_code` を受け取って捨てるプラグイン（#308 の契約違反）がサブコードの無い支払行を作る事故を、黙って記録せずに止める（spec FR-012 の「黙って無視しない」）
- 支払マスタは `settle_payment_async` の中でも読むが、cart のマスタのキャッシュ（`AbstractMasterDataRepository`）に乗るので、2 回目の読み取りは同じキャッシュの項目を返す

**決定の規則**（spec FR-012・FR-013）:

| 有効なサブコード | 指定あり | 指定なし |
|---|---|---|
| 0 件 | 存在しなければ 403018、停止中なら 403019 | サブコードなし |
| 1 件 | その支払方法の有効なサブコードなら採用。存在しない 403018・停止中 403019 | その 1 件 |
| 2 件以上 | 同上 | 403020（指定が要る） |

**Alternatives considered**:
- プラグインの中で決める（`settle_payment_async` が `requested_variant_code` を受けて決める）: 決定がプラグインの協力に依存し、外部のプラグインが `settle_payment_async` を使わないと規則が効かない
- `CartService` がプラグインの後で支払行にサブコードを書き込む: プラグインが作った行を後から書き換えることになり、プラグインがどの行を足したかの推測が要る

---

## R-7: 取消（void）の支払行

**現状**: `TranService.void_async` は、要求の支払の一覧（`payment_code`・`amount`）を、元の取引の支払コードごとの合計と照らし、一致すれば要求の行から支払マスタを引き直して支払行を作る。

**Decision**（spec FR-016・FR-016a・利用者の決定 2026-11-22）: 照合の鍵を `payment_code` から `(payment_code, variant_code)` に細かくする。
- 要求の各支払の鍵（`variant_code` の省略は `None`）が売上時の支払行の鍵の集合に無ければ拒否（現行と同じ `BadRequestBodyException`）
- 金額は鍵ごとに売上時の合計と一致しなければ拒否（現行と同じ）
- 支払行は現行どおり要求の行から作り、`variant_code` は要求の値、`description`・`builtin_description` は売上時のその鍵の最初の行から写す

純関数 `match_void_payments(original_lines, requested)`（`payment_variant_logic.py`）に置く。

**Rationale**:
- 取消は売上の裏返しなので、売上時の支払種別以外を受け付けない（利用者の決定）
- 要求の形（支払コード・金額）は現行と同じで `variant_code` が加わるだけ。サブコードの無い取引は現行の要求のまま取消できる
- 省略を「サブコードなし」と厳密に読むことで、サーバが推測する余地を無くす（利用者の決定: サブコードまで指定必須）
- 販売後にサブコードが停止・改名されても、照合は売上時の行と行い、名前も売上時の行から写すので影響しない（FR-016d）

**Alternatives considered**:
- 元の行をサーバが写し、要求のサブコードを拒否する: クライアントは支払種別を指定しているのにサブコードだけ指定できず、規則が非対称になる（利用者の指摘で却下）
- 省略時に売上時の行のサブコードが 1 種類ならそれとみなす: 推測を残す。利用者の決定で指定必須とした

---

## R-8: 返品（return）の支払行

**現状**: `TranService.return_async` は、要求の支払の一覧で返金の支払方法を自由に選べる（元の取引の支払方法と一致しなくてよい）。支払行は要求から作り直す。確認は返金の合計が取引の合計と一致すること・返金可否と上限（#309）だけ。

**Decision**（spec FR-016b〜FR-016e・利用者の決定 2026-11-22）: 純関数 `match_return_payments(original_lines, requested, cash_code="01")` で各支払を分類する。

| 要求の支払 | 扱い |
|---|---|
| 鍵 `(payment_code, variant_code)` が売上時の行にある（現金を含む） | 受け付ける。名前は売上時の行から。現金以外は鍵ごとの返金額の合計が売上時の合計以下（超えれば 403022） |
| 売上時の行に無いが `payment_code == "01"` | 受け付ける。サブコードは販売の規則（R-6: 403018・403019・403020）、名前は現在のマスタ。上限なし |
| それ以外 | 403021 |

- `variant_code` の省略は `None`（取消と同じ）
- 売上時の行にあるサブコードは停止中でも受け付ける（マスタの有効フラグを見ない）
- 返金の合計が取引の合計と一致すること・返金可否と上限（403014・403015）の確認は現行どおり

**Rationale**:
- 返品は売上時の手段へ戻すのが原則で、現金でしか返金できない場合（カードの取消期限切れ等）のために現金を常に認める（利用者の決定）
- 売上時の手段に売上時より多く返すのは、お金の流れとして誤り（利用者の決定: エラー）。現金は他の手段の不足分を受けるので上限を設けない
- 現金の判定は支払コード `01`（利用者の決定。report の現金の判定と同じ）

**既存動作の変更**: 現行は任意の支払方法で返金できる。売上時と違う支払方法（現金以外）での返品は 403021 で拒否されるようになる。サブコードの有無に関わらない変更なので、リリースノートに書く。

**Alternatives considered**:
- 元の取引から推測してサブコードを引き継ぐ: 推測を残す。利用者の指摘で、クライアントが指定する形にした
- 現金の判定を `plugins.json` の現金のプラグイン（`PaymentByCash`）の支払コードで行う: より汎用だが、利用者の決定で report と同じ `01` とした

---

## R-9: 取引ログの支払行の項目

**Decision**: `kugel_common` の `BaseTransaction.Payment` に `variant_code: Optional[str] = None` と `builtin_description: Optional[str] = None` を足す。cart の `CartDocument` は `BaseTransaction` を継承しているので、カートの支払行にも同じ項目が入る。

cart の API の支払行の応答（`BaseTranPayment`）に `variant_code: Optional[str] = None`・`builtin_payment_name: Optional[str] = None`（camelCase で `variantCode`・`builtinPaymentName`）を足す。既存の `payment_name` は `description`（サブコードの名前）のまま。

**Rationale**:
- 追加のみで、既存の項目の意味は変えない（名前がサブコードの名前になる点を除く・利用者の決定）
- 集計で支払方法の名前を販売時点の値で出すには、支払行が自分で持っている必要がある（マスタは販売後に変わりうる）
- 応答の名前は既存の `payment_name` に合わせて `builtin_payment_name` とした

**カートのスナップショット**: 署名は持ち込まれたスナップショットの生の内容にかかり、新しい項目は既定値（`None`）を持つ任意の項目なので、項目の無い既存のスナップショット（schema_version 1・2）はそのまま検証・復元できる。`SNAPSHOT_SCHEMA_VERSION` は上げない（#165 で上げたのは `revision` が検証の意味を持つため。今回の項目は検証に関わらない）。

---

## R-10: cart の支払マスタのキャッシュ

**Decision**: 仕組みは変えない。cart の `PaymentMasterDocument` に `variants: list[PaymentVariant] = Field(default_factory=list)` を足す。

**Rationale**:
- キャッシュの鍵は文書の型の構造の指紋（`document_shape`）を含む。型に項目が増えると指紋が変わり、項目の無い古いキャッシュは読まれずに取得し直される。配備の直後に「サブコードがあるのに 0 件と読む」ことは起きない
- サブコードの変更が cart に効くのは TTL（`PAYMENT_MASTER_CACHE_TTL_SECONDS`）の経過後。支払方法の設定の変更（#309）と同じ扱い（spec Edge Cases）

---

## R-11: レポート

**売上レポート（`SalesReportMaker`）の現状**: 集計のパイプラインは支払を `(payment_code, description)` で分組し、Python の後段（取引種別の符号を掛けて合算する部分）で `payment_code` ごとにまとめている（名前は最初に出た `description`）。名前がサブコードの名前になると、行の名前が先に出たサブコードの名前になってしまう。

**Decision（売上レポート）**:
- パイプラインの支払の写しに `variant_code`・`builtin_description` を足し、分組の鍵を `(payment_code, variant_code)` にする。分組の前に販売日時（`generate_date_time`）の降順で並べ、名前は `variant_name: $first description`、`builtin_name: $first {$ifNull: [builtin_description, description]}` とする（期間内で最も新しい販売時点の名前。並べずに `$first` を取ると、期間中に改名があったとき実行ごとに名前が変わりうる）
- Python の後段で `payment_code` ごとの行と、その下の `variant_code` ごとの内訳を合算する
- 報告の支払の行に `payment_code`（現行の内部の値をそのまま出す）・`variants: list[{variant_code, variant_name, amount, count}]` を足す。行の名前は `builtin_name`（FR-020）

**支払レポート（`PaymentReportMaker`）の現状**: 支払を `(payment_code, transaction_type)` で分組し、件数は取引の一意な集合の大きさ。名前は master-data から取得した現在の支払マスタの名前。

**Decision（支払レポート）**:
- 同じパイプラインに `variant_code` の分組を足した内訳のパイプライン（`(payment_code, variant_code, transaction_type)`）を加え、内訳の件数も取引の一意な集合で数える
- 名前は現行どおり現在のマスタ（`_fetch_payment_master` をサブコードの名前も返すように拡張）。マスタに無いサブコードは支払行の名前（売上レポートと同じく販売日時の降順に並べてからの `$first description`）
- `_fetch_payment_master` は現行 `limit=100, page=1` の 1 ページだけを読むので、支払方法が 100 件を超えると後ろの支払方法の名前を引けない（既存の制限）。サブコードの名前もここから引くので、全ページを読むように直す（応答の `metadata` の総件数まで `page` を進める）
- 内訳の件数の合計は行の件数を上回ることがある（spec FR-021）。構成比（`ratio`）は行にだけ付ける

**並び順**: 内訳は `variant_code` の昇順、サブコードなしは末尾（spec Assumptions）。

**Rationale**: 既存の集計の構造（パイプライン → Python の符号付き合算）をそのまま使い、分組の鍵を 1 つ足すだけにする。印字（レシートデータ）は変えない（spec Assumptions）。

**Alternatives considered**:
- 内訳を別の端点にする: 行と内訳が別々に集計され、時点の違いで合わないことがある

---

## R-12: エラーコード

**Decision**:

| コード | 名前 | HTTP | 使う場面 |
|---|---|---|---|
| 403018 | `PAYMENT_VARIANT_NOT_FOUND` | 400 | 指定したサブコードがその支払方法に無い（販売・売上時に無い現金での返品） |
| 403019 | `PAYMENT_VARIANT_INACTIVE` | 400 | 指定したサブコードが停止中（同上） |
| 403020 | `PAYMENT_VARIANT_REQUIRED` | 400 | サブコードの指定が要る（同上で有効なサブコードが 2 件以上） |
| 403021 | `RETURN_TENDER_NOT_ALLOWED` | 400 | 返品の支払種別が売上時の支払種別でも現金でもない |
| 403022 | `RETURN_AMOUNT_EXCEEDS_ORIGINAL` | 400 | 返品で売上時の支払種別に返す額が売上時の金額を超える |

取消の照合の不一致（売上時に無い支払種別・金額の不一致）は、現行の取消の照合と同じ `BadRequestBodyException` で答える（新しいコードを足さない）。

master-data は新しいコードを足さず、既存の `DocumentNotFoundException`（支払方法・サブコードが無い）と `DocumentAlreadyExistsException`（サブコードの重複）で答える（spec FR-018）。

**Rationale**: cart の支払の拒否（403004・403014・403015・403017）と同じ 4030xx の並びで、空いている番号を順に使う。HTTP は既存の支払の拒否（`PaymentLimitExceededException` は 400）に合わせる。

---

## R-14: 配備の順序

**Decision**: サブコードを登録するのは、commons・cart・report を本フィーチャーの版へ配備し終えた後に限る。master-data だけを先に配備してもよいが、その間はサブコードを登録しない。リリースノートと運用手順に書く。

**Rationale**: 古い cart の `PaymentMasterDocument` には `variants` が無く、知らない項目は黙って捨てられる（Pydantic の既定）。master-data でサブコードを登録しても古い cart はそれを知らず、サブコードの指定を無視してサブコードなしで記帳する（SC-002・SC-006 に反する）。本システムは全サービスを同じ版で配備する運用なので、新旧の cart が並ぶのは配備の間だけで、登録をその後に行えば防げる。

**Alternatives considered**:
- 機能フラグで cart の全台の更新後にサブコードを有効にする: 配備を全サービス同時に行う運用では、手順で足りる。仕組みを足すほどの利得が無い
- 古い cart がサブコード付きのマスタを拒否する互換の取り決め: 古い cart は変えられない（既に配備済みの版の挙動）

---

## R-13: 影響しないことの確認

- **journal**: 取引ログを `BaseTransaction` のまま保存する。項目の追加は保存・検索に影響しない（検索の語は支払行の名前に当たるので、サブコードの名前でも引ける）
- **terminal・stock・account**: 支払マスタも支払行も読まない
- **report の現金の判定**: `payment_code == "01"` のまま（FR-022）
- **cart の受領票（レシート）**: `receipt_data_sample` は支払行の `description` を印字する。サブコードの名前がそのまま出る（spec Assumptions）
- **cart の e2e**: 新しいテストはスナップショットを伴う形で書く（`dual_only` は付けない）。#309 の `tests/e2e/test_payment_master_settings.py` と同じ書き方（スナップショットを持ち回る）に倣う（spec FR-024）
