# Research: client-carried cart phase 2（stateless cart backend, #156）

spec「未解決事項」および Technical Context の不明点を確定する。phase 1（#148）の調査・実装で確立した事実は前提とし、本フェーズ固有の判断のみ記す。

---

## R-001: リクエストでのスナップショット搬送方法

**Decision**: 変更系リクエストのボディに**任意フィールド `signed_snapshot`**（phase 1 のエンベロープと同一形）を追加する。既存のリクエストボディを持つエンドポイント（lineItems / discounts 等）はそのボディに追加し、ボディを持たない操作（subtotal / cancel / resume-item-entry 等）には `signed_snapshot` のみを持つ任意ボディを受け付ける。ヘッダ搬送・専用ラッパは採らない。

**Rationale**:
- スナップショットは大きい（40 商品で ~2 KB gzip 前は数十 KB）。ヘッダはサイズ制約・圧縮非対応のため不適。ボディが自然。
- phase 1 のレスポンス側 `signed_snapshot` と**同名・同形**にすることで、クライアントは「受け取ったものをそのまま次のリクエストに詰める」だけでよい（往復の対称性）。
- 任意フィールドにすることで FR-008 のデュアルモード（あり/なし分岐）が素直に表現できる（フィールドの有無＝経路）。

**Alternatives considered**: (a) 共通リクエストラッパで全エンドポイントを包む → 既存 API 形状を破壊し後方互換を失う。(b) ヘッダ `X-Cart-Snapshot` → サイズ・圧縮で不利。(c) 専用の単一「操作 API」に集約 → 既存エンドポイント体系の作り直しで過大。

---

## R-002: あり/なし経路の分岐点（デュアルモード実装）

**Decision**: 分岐は **dependency 層（`get_cart_service_with_cart_id_async` 相当）**で行う。リクエストに `signed_snapshot` があれば、phase 1 の `snapshot_service.verify_envelope` で検証・再構成したカートを `CartService.current_cart` に注入して「あり経路（ステートレス）」のサービスを構築する。なければ従来どおりキャッシュから読む「なし経路」のサービスを構築する。`CartService` のビジネスロジック（状態機械・採番・確定）は経路によらず共通。

**Rationale**:
- 既存の DI（`app/dependencies/get_cart_service.py`）がカート取得の単一の入口であり、ここで「カートをどこから得るか（スナップショット vs キャッシュ）」だけを切り替えれば、下流のロジックを二重化せずに済む。
- phase 1 の `restore_cart_async` がすでに「スナップショットからの再構成（マスタ再ハイドレート + 状態設定）」を実装済み。あり経路はこの再構成を**毎リクエスト・キャッシュ書き込みなし**で行う形に一般化する。
- あり経路はキャッシュを読まない（FR-004）。書き込みは「best-effort の最適化」としてのみ許容（移行期間の GET 供給用、R-007）。

**Alternatives considered**: 各エンドポイント内で分岐 → 12+ 箇所に重複。ミドルウェアで分岐 → カート ID 解決・認証コンテキストが未確定の段階では早すぎる。

---

## R-003: 取引連番の持ち回り化（`(business_counter, seq)`）

**Decision**: `transaction_no` / `receipt_no` を **`(business_counter, seq)` の複合**に再定義する（spec FR-012）。
- `business_counter`: terminal service が open 時に払い出す既存の単調増加値（`terminal_service.py:429`、非リセット）。JWT クレーム / terminal_info 経由で持ち回る（既存 `tranlog.business_counter = terminal_info.business_counter`、`tran_service.py:165` をそのまま活用）。
- `seq`: 開設セッション内連番。**スナップショット（cart_document）に保持**し、端末がローカルに採番・前進。あり経路では確定時にこの持ち回り `seq` を tranlog に刻む。
- cart の `TerminalCounterRepository` による transaction/receipt 採番（`tran_service.py:159,173`、`numbering_count`）は**あり経路では使用しない**。なし経路（移行期間）では従来どおり `numbering_count` を使う（デュアルモードの一貫性）。移行完了後に `terminal_counter` の transaction/receipt 採番を撤去。

**seq の初期値源**: 開設セッションの最初の確定で `seq=1`。`seq` は cart_document に持つため、カート作成時のスナップショット（phase 1 で付与済み）に `seq=0`（未確定）を載せ、確定のたびに +1 する。端末はセッションをまたいで seq を持ち越さない（open ごとに business_counter が変わるためリセットされる）。

**確定の決定論化（取引時刻のクライアント打刻）**: 連番に加え、確定時にサーバ時刻でスタンプされる **`generate_date_time`（`tran_service.py:166` の `get_app_time_str()`）をクライアント打刻に変更**する（spec Clarifications 2026-06-13 で確定）。理由: レシート（`receipt_text` / `journal_text`、`tran_service.py:262-267`）はこの tranlog から生成され、レスポンス受領後に発行される。lost-ACK でリトライ先が確定し直すとサーバ時刻が変わり、先勝ちで保全される1件目の台帳時刻と、客が受け取る（リトライ応答からの）レシート時刻が食い違う。

**決定**: 取引時刻は**端末が確定（bill）時に打刻し bill リクエストで供給**する。バックエンドは `generate_date_time` にこのクライアント値を用いる（`get_app_time_str()` をあり経路で使わない）。lost-ACK でも端末は自分の打刻値を保持しており同値でリトライ可能なため、どのバックエンドでも同一時刻になり決定論が成立。確定レスポンスが返す completed スナップショットの `cart_document.transaction_datetime` にこの値を含め署名する。`business_date`（`cart.business_date` 由来、`tran_service.py:163`）は既に carried。

**Alternatives considered**: (a) paying 遷移時にサーバが署名済みスナップショットへ記録 → 「支払い開始時刻」になり現行の「確定時刻」意味からずれる。(b) サーバ確定時刻＋下流 last-wins（最大時刻採用）→ ledger=receipt は成立しうるが、バックエンド間クロックずれで「最大時刻 ≠ 客が受け取った試行」になり破綻、かつ不変台帳の上書きを要する。クライアント打刻が「確定時刻の意味維持・lost-ACK 耐性・クロックずれ非依存・先勝ち維持」を同時に満たす。

**Rationale**: spec Clarifications（2026-06-13）で確定済み。交換・オフライン確定・ステートレスを同時に満たす唯一の構成。`business_counter` が非リセットのため `(business_counter, seq)` が単独で一意になり、交換時の seq 復元が不要。取引時刻の持ち回りにより確定が決定論的になり、先勝ちスキップ（R-005）と台帳=レシートの一致が両立する。

**Alternatives considered**: 単一通し整数（中央採番）→ ステートレス・オフライン確定と両立せず、spec で Out of Scope。open_counter エポック → 日内リセットで `(business_date, open_counter, seq)` の3要素が必要、business_counter の方が単純（spec Clarifications 参照）。

---

## R-004: tranlog への `cart_id` 追加（#152 連携）

**Decision**: `BaseTransaction`（`commons/.../base_tranlog.py`）に **`cart_id: Optional[str]`** を追加し、確定時に `CartDocument.cart_id` を引き継ぐ（`tran_service.py` の CartDocument→BaseTransaction 変換で受け渡し）。これは #152 の中核であり、phase 2 の採番変更と同じ確定パスを触るため**本フィーチャーの実装に含める**（#152 を phase 2 が駆動する）。

**Rationale**: 下流調査により、現状 tranlog は cart_id を持たず（`BaseTransaction` に欠落）、cart_id キーの収束（FR-006）が物理的に不可能と判明。cart_id を載せることが全ての前提。採番変更（R-003）と cart_id 付与は同一の確定パス・同一の tranlog スキーマ変更なので分離不能。

**Alternatives considered**: #152 を先行・独立 issue として完了させてから phase 2 → 採番変更（transaction_no 再定義）と cart_id 付与が同じスキーマ・同じ確定コードを触るため、分けると二重改修になる。phase 2 で一体実装が合理的。

---

## R-005: 下流の冪等化方針と unique index 変更

**Decision**: 下流（report / journal / stock）の取引重複排除を **`cart_id` 基準のスキップ（insert-if-absent / 先勝ち）**に統一する（spec FR-006）。確定取引ログは不変で、A-1/A-3 下で重複は同一内容のため、後勝ち upsert ではなく「既処理ならスキップ」が正しく、かつ既存実装と一致する。
- tranlog の一意性インデックスを `(tenant_id, store_code, cart_id)` の unique に変更（または追加）。現行の `(tenant_id, store_code, terminal_no, transaction_no)` インデックスは、`transaction_no` が seq に再定義され単独では一意でなくなる（セッション間で重複）ため、`business_counter` を含めた `(tenant_id, store_code, terminal_no, business_counter, transaction_no)` へ是正する（監査・参照用）。
- report: `create_tranlog_async` の存在チェック（現状 `(tenant,store,terminal,transaction_no)` で存在すれば warning して何もせず返す = insert-if-absent）のキーを cart_id に差し替え。
- journal: 同様。tranlog 取り込みの存在チェックキーを cart_id に。
- stock: `process_transaction_async` の取引レベル事前チェック（現状 `(tenant,store,terminal,transaction_no)` で既存 stock_update を検査し、あればバッチ全体をスキップ、`stock_service.py:175-188`）を **cart_id 基準**に差し替え。`$inc` + DuplicateKey ロールバックの保護機構（`stock_service.py:107-120`）はそのまま活かし、unique index に cart_id を組み込む。
- 既存の `event_id` state-store dedup は第一線（安価な Dapr 再配信除け）として維持。ただし **lost-ACK 再送は新しい event_id を生む**ため、cart_id スキップが最終防壁。

**重要（seq 再定義による誤スキップの回避）**: `transaction_no` を `seq`（開設セッション内連番）に再定義すると、`(tenant, store, terminal, transaction_no)` がセッション間で一意でなくなる。現状の stock 事前チェック・report/journal の存在チェックをこのまま残すと、**別セッションの同一 seq の正当な別取引を「処理済み」と誤判定してスキップ**する（在庫の取りこぼし等）。よって下流のキー差し替え（→ cart_id）は seq 再定義と**同時に行う必須事項**であり、片方だけの適用は不可。

**Rationale**: 下流調査で「現状 dedup は transaction_no タプル + event_id、cart_id は不使用、いずれも insert-if-absent（スキップ）」と判明。取引同一性キー＝cart_id で統一するのが最も堅牢かつ #146 の設計意図に一致。スキップ型のため変更は既存ロジックのキー差し替えが主で、新たな upsert 機構は不要。

**Alternatives considered**: (a) 後勝ち upsert → 確定取引ログは不変・重複は同一内容なので上書きの必要がなく、既存レコードのタイムスタンプ/監査を保全する先勝ちが優る。(b) `(business_counter, seq)` タプルで dedup（cart_id を載せない）→ 採番が決定論的持ち回りなら機能するが、採番バグ時に別取引を誤マージする危険（FR-013 の整合性検知が cart_id を要する）、#146 が cart_id を取引同一性キーと明記、の2点で cart_id 基準が優る。両者併用（cart_id で dedup、`(business_counter, seq)` で整合性検知）が最終形。

---

## R-006: リクエスト展開ミドルウェア

**Decision**: `kugel_common` に**リクエストボディ展開 ASGI ミドルウェア**を新設（`http_compression.py` の docstring が予告した保留分）。`Content-Encoding: gzip` / `br` を展開し、**展開後サイズ上限ガード**（既定値は `SNAPSHOT_SIZE_WARN_BYTES` と整合する上限、例: 1 MB）を設け、超過はストリーミング展開の途中で打ち切って明確なエラー（413 相当）を返す。cart サービスに登録（他サービスは任意）。クライアント圧縮は任意（非圧縮も受領）。

**Rationale**: spec FR-009。`http_compression.py:19-22` が「client-carried cart のリクエストで必要になったら追加する」と明記しており、本フィーチャーがその契機。展開後サイズガードは zip-bomb 対策に必須。クライアントは .NET 8（`BrotliStream` / `GZipStream` 標準）。

**Alternatives considered**: リバースプロキシ（nginx 等）で展開 → 配備依存で移植性が低く、サイズガードの業務エラー化が難しい。展開なし（非圧縮のみ）→ 上り帯域が NFR-001 を脅かす。

---

## R-007: デュアルモード設定と移行運用

**Decision**: cart の設定（環境変数）に **`CART_REQUEST_SNAPSHOT_MODE`**（仮、値: `DUAL` / `REQUIRED`、既定 `DUAL`）を追加（spec FR-008、サービス全体粒度）。
- `DUAL`: あり経路（スナップショット）/ なし経路（キャッシュ権威）を毎リクエスト自動分岐。
- `REQUIRED`: なし経路を明確なエラー（専用エラーコード）で拒否。
- 移行完了判定用のなし経路発生件数は、**既存のリクエストログの集計で代替**する（専用メトリクス実装タスクは設けない — ユーザー判断 2026-06-13）。なし経路通過は通常のリクエストログに現れるため、運用側の集計で「なし経路ゼロ」を確認して `REQUIRED` へ切り替える。FR-007 の異常系監査とは別系統。
- 移行期間中はサーバ側キャッシュ・サーキットブレーカー・フォールバックを残置（FR-004）。撤去は移行完了後の後続作業（本スコープ外）。

**Rationale**: spec で確定。phase 1 の `SNAPSHOT_HMAC_KEYS` と同じ env レベルの設定方式に倣い一貫性を保つ。

**Alternatives considered**: テナント別/店舗別切替 → 設定面・テスト面のコスト増、spec で不採用。

---

## R-008: 乖離検知の実装（あり経路）

**Decision**: あり経路では提示スナップショットを正とする（FR-005）。乖離検知は「移行期間中はサーバ側キャッシュが残っている」事実を活かし、**ベストエフォートで**行う: あり経路の処理時に同一 `cart_id` のキャッシュ残存があり内容が乖離していれば、監査に「乖離」を記録する（処理は提示スナップショットで続行）。キャッシュが無い/読めない場合は乖離検知をスキップ（処理は続行）。リビジョン等のスカラー比較は誤検知のため判定に用いない（FR-005）。

**Rationale**: 純ステートレスでは比較相手が無いが、デュアルモードでキャッシュが残る移行期間は乖離を観測できる。検知はあくまで監査用で、処理の正否には影響しない。移行完了後（キャッシュ撤去）は乖離検知が自然に無効化される（A-1 前提下で乖離は異常系のため許容）。

**Alternatives considered**: 最小マーカー（cart_id→ダイジェスト）を別途保持して比較 → 新たな共有状態を導入する割に得る検知価値が低い（A-1 で乖離は稀）。不採用。

---

## R-009: 監査証跡の保存先

**Decision**: phase 1 の `log_cart_restore` コレクション・リポジトリを**一般化**して再利用するが、記録対象が restore 以外（毎リクエスト検証の異常系・乖離・連番異常）に広がるため、**コレクションを `log_cart_snapshot_event` へ改称**する（ユーザー判断 2026-06-13）。`cart_restore_log_document` / `cart_restore_log_repository` も対応する命名（例 `cart_snapshot_event_log_*`）へリネーム。phase 1 で書かれた既存 `log_cart_restore` レコードがあれば新コレクションへ移行する（phase 1 は既定縮退で本番データはほぼ無い想定だが、マイグレーションを tasks に含める）。記録は**異常系のみ**（検証失敗・スコープ違反・終端拒否・乖離・連番異常）。正常系の毎リクエストは記録しない（FR-007、NFR-005）。

**Rationale**: phase 1 が `result` / `reject_reason` / `diverged` 等のフィールドを持つ汎用的な監査レコードをすでに実装済み。毎リクエスト検証への一般化は API 経路（どのエンドポイントか）の記録追加程度で済む。

**Alternatives considered**: 新規コレクション分離 → phase 1 と二系統になり監査クエリが分散。既存ログ基盤（app log のみ）→ 構造化クエリ不可。

---

## R-010: 連番整合性の監査検知（下流）

**Decision**: 下流（report / journal）で `(tenant, store, terminal, business_counter, seq)` の**重複・欠番を `cart_id` 基準で検知**する（FR-013）。重複: 同一 `(business_counter, seq)` に異なる `cart_id` が来たら整合性異常として監査記録（採番バグ・端末不正の兆候）。欠番: 営業日締め / レポート集計時に seq の連続性を検査し欠落を記録。会計合計は cart_id 後勝ちで1件に収束するため、検知は集計の正しさを損なわない。

**Rationale**: spec FR-013。seq の権威が端末でバックエンドが強制できないため、整合性は事後検知。既存のレポート集計・ジャーナル生成のタイミングに検査を差し込むのが自然。

**Alternatives considered**: バックエンドでリアルタイム強制 → ステートレスと両立せず（権威の再導入）。

---

## 確定サマリ（spec「未解決事項」との対応）

| spec 未解決事項 | 決定 |
|---|---|
| デュアルモードの設定キー・値・既定・移行判定 | `CART_REQUEST_SNAPSHOT_MODE`（DUAL/REQUIRED、既定 DUAL）+ なし経路メトリクス（R-007） |
| 照会系（GET）の応答ソース | 移行期間中は従来どおりキャッシュ供給。撤去後は後続フェーズ（R-007/FR-004） |
| seq 初期化のコンテキスト提供 | cart_document に seq を保持（カート作成スナップショットに seq=0）、確定時 +1（R-003） |
| 下流 cart_id 冪等化と transaction_no キー是正の範囲 | report/journal/stock を cart_id 基準 dedup へ、unique index 是正（R-004/R-005） |
| 展開アルゴリズムと上限値 | gzip + br、展開後上限（例 1 MB、tasks で確定）（R-006） |
| エンベロープのスキーマ変更要否 | seq は既存 cart_document に含まれるためエンベロープ形は不変（スキーマバージョン据え置き）（R-003） |
| 監査の保存先・保持期間 | phase 1 `log_cart_restore` を一般化（TTL なし、異常系のみ）（R-009） |
