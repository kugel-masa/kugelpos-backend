# Research: 署名付きカートスナップショット + restore API（#148）

**Date**: 2026-06-11
**Input**: [spec.md](./spec.md) の「未解決事項（plan で確定）」+ Technical Context の未確定項目

spec の Clarifications で確定済みの 3 判断（衝突ルール = 既存サーバ優先 + 差分通知 / 鍵管理 = 共有シークレット + kid 世代管理・猶予 24h / 復元端末範囲 = 同一テナント + 店舗）は前提とし、ここでは plan に持ち越された設計判断を確定する。

---

## R-001: 署名・正規化ユーティリティの置き場所

**Decision**: 汎用の HMAC 署名/検証ユーティリティ（kid 世代管理・canonical JSON 生成を含む）は **kugel_common（`kugel_common/utils/hmac_signer.py` 新設）** に置く。スナップショットの組み立て・検証・restore のドメインロジックは **cart サービス内**（`app/services/snapshot_service.py` 等）に置く。

**Rationale**:
- リポジトリに既存の HMAC ヘルパーは無い（`security.py` は JWT のみ）。新規作成になる。
- #146 phase 2（毎リクエスト持ち回り）でも同じ署名機構を使うため、commons に置けば再利用できる。JWT（`kugel_common/security.py`）と同じ配置パターン。
- 一方「カート文書をどう正規化して何を署名するか」は cart のドメイン知識なので cart 側に閉じる。

**Alternatives considered**:
- 全部 cart 内に閉じる: phase 2 や他サービスでの流用時に commons へ引っ越しが必要になり、二度手間。汎用部分だけ commons に置くコストはほぼ同じ。
- 全部 commons に置く: スナップショットスキーマという cart 固有概念が commons に漏れる。却下。

## R-002: スナップショットのトランスポート表現

**Decision**: **専用トランスポートスキーマは作らず、「エンベロープ + CartDocument の JSON」方式**とする。

```
snapshot = {
  "schema_version": 1,
  "issued_at": "<ISO8601 UTC>",
  "kid": "<署名鍵ID>",
  "tenant_id": "...", "store_code": "...", "terminal_no": ...,   # 帰属（FR-005/FR-012 検証用）
  "cart_document": { ... CartDocument.model_dump(mode="json") ... },
  "signature": "<hex(HMAC-SHA256)>"
}
```

レスポンスへの載せ方: cart のレスポンススキーマ（`BaseCart`）に optional フィールド `signed_snapshot` を追加し、transformer（`SchemasTransformerV1.transform_cart`）で詰める。既存フィールドは不変（FR-001 の後方互換）。

**Rationale**:
- `CartDocument.model_dump(mode="json")` → `CartDocument(**data)` のラウンドトリップは Redis キャッシュの JSON 化（commit 7b591b... 7b65cf1, #141/#142）で既に実運用パターンになっており、restore の再構築も同じ経路を使える。
- 専用トランスポートスキーマを設けると CartDocument 変更のたびに二重メンテが必要になり、phase 1 の趣旨（実証済み設計の薄い移植）に反する。
- 前方互換はエンベロープの `schema_version`（初期値 1）で判定する（FR-008）。CartDocument 自体のフィールド追加は Pydantic の既定（不明フィールド無視/Optional 既定値）で吸収する。

**Alternatives considered**:
- 専用トランスポートスキーマ: 変換層の分だけ堅牢だが二重メンテ。phase 2 で必要になれば schema_version を上げて移行できる。
- Cart レスポンススキーマ（API 表現）をそのまま署名対象にする: API 表現はマスタ全量を含まず復元に不十分。却下。

## R-003: 正規化（canonical serialization）と署名方式

**Decision**:
- 署名対象 = エンベロープから `signature` を除いた全体を **`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)`** で直列化した UTF-8 バイト列。
- アルゴリズム = **HMAC-SHA256**（`hmac` + `hashlib` 標準ライブラリのみ、新規依存なし）。検証は `hmac.compare_digest` で定数時間比較。
- `kid`・`schema_version`・帰属情報はエンベロープ内にあるため**自動的に署名対象に含まれる**（FR-003 の鍵すり替え防止を満たす）。

**Rationale**: Python の `json.dumps` のキー順・区切り・ASCII エスケープを固定すれば、同一内容 → 同一バイト列が言語処理系のバージョンに依らず成立する。float の表現揺れが理論上の懸念だが、署名と検証はともに「受信した JSON テキストを再パースせず、エンベロープ dict から同一手順で再直列化する」ため、揺れは往復で一致する（検証側は受信 dict から signature を除いて再直列化して比較）。

**Alternatives considered**: JWS（python-jose 等）: 標準的だが依存追加と base64 膨張のわりに、バックエンド間でしか使わない本用途では利点が薄い。RFC 8785 (JCS): 厳密だが実装/依存コストが過剰。

## R-004: 署名鍵の設定表現

**Decision**: cart の設定（`settings_cart.py`、env 上書き可）に以下を追加する。

- `SNAPSHOT_HMAC_KEYS`: `"<kid>:<base64鍵>[,<kid>:<base64鍵>]"` 形式（先頭が現行鍵、2 つ目が前世代鍵）。例: `"v2:...,v1:..."`
- 既定値はリポジトリに置かない（未設定時はスナップショット機能を**縮退**（R-006）し、起動ログに warning。テスト/開発は `.env` で注入）。

**Rationale**: 既存の `SECRET_KEY` と同じ env 配布モデル（Azure Container Apps では secrets/Key Vault 参照で注入）。現行+前世代を 1 変数に並べる形式は「ローテーション = 値の差し替え 1 回」で済み、Dapr secret store 等の新規インフラが不要。JWT の `SECRET_KEY` とは別変数（FR-011 の鍵分離）。

**Alternatives considered**: 鍵を DB/Dapr state に置く: 配布・同期の設計問題が再帰する（spec Clarifications でテナント別鍵を却下したのと同じ理由）。

## R-005: GET（照会系）レスポンスへの付加有無

**Decision**: **付加しない**。スナップショットはカート変更系（POST/PATCH）レスポンスと restore API レスポンスのみに含める。

**Rationale**: スナップショットの保証は「最後に成功した変更操作の直後の状態」であり、変更系で漏れなく返せば成立する（User Story 2）。GET に載せても帯域増のわりに復元保証は強くならない。POS がスナップショットを失った場合（アプリ再起動等）も、phase 1 ではサーバ側が正なのでカートはサーバに残っており、次の変更操作で再入手できる。

**Alternatives considered**: GET にも付加: phase 2（毎リクエスト持ち回り）では前提が変わるため再検討するが、phase 1 では YAGNI。

## R-006: スナップショット生成失敗時の縮退方針（NFR-004）

**Decision**: **縮退許容**。スナップショットの組み立て・署名で例外が発生しても本来のカート操作は成功させ、`signed_snapshot` フィールドを欠落（null）とし、**warning ログ**で検知可能にする。ただし**鍵未設定・パース不能などの構成エラーは起動時に検出してログに明示**する（リクエスト時に初めて発覚させない）。restore API は縮退の対象外（署名検証できなければ常にエラー応答）。

**Rationale**: phase 1 のスナップショットは付加価値（復元コピー）であり、生成失敗で会計業務を止めるのは本末転倒。サーバ側が正なので、欠落しても従来運用と同等に劣化するだけ。spec NFR-004 の「縮退するならログで検知可能に」を満たす。

**Alternatives considered**: 操作ごと失敗: 署名処理のバグが全カート操作の全停止に直結する。リスクに見合わない。

## R-007: 監査証跡の保存先（FR-007）

**Decision**: テナント別 DB（`db_cart_{tenant_id}`）に**専用コレクション `log_cart_restore` を新設**し、既存の repository パターン（`AbstractRepository` 継承、`settings_database.py` にコレクション名定数追加）で書き込む。記録対象: restore の成功/拒否（拒否理由つき）/衝突差分の有無、スナップショットメタ（`cart_id`・発行時刻・発行端末・kid・schema_version）、要求側（端末・店舗）、イベント時刻。インデックス: `cart_id`、`event_datetime`。保持期間は既存の取引ログ類と同様に無期限（TTL なし）とし、運用で必要になれば TTL インデックス追加で対応。

**Rationale**: cart には audit 用の既存コレクションが無く、tranlog 等と同じ「ログ系コレクション + repository」パターンの新設が最小かつ一貫。署名検証失敗（セキュリティイベント、NFR-003）もアプリログ（logger）と本コレクションの両方に残る。

**Alternatives considered**: journal サービスへ送る: pub/sub 配線・スキーマ追加が必要で重い。restore は cart 内で完結する操作なので cart の DB でよい。アプリログのみ: 構造化検索（cart_id での追跡、FR-007/SC-003）が成立しない。

## R-008: サイズ超過対策の判断基準（NFR-001）

**Decision**: phase 1 では**計測 + 閾値超過の warning ログ**までとし、構造的対策（同梱マスタの絞り込み・分割等）は実測が以下のいずれかを超えた場合に #146（phase 2 設計）で検討する:

1. 標準 40 商品カートのスナップショット込みレスポンスが **gzip 後 15 KB 超**（SC-005 の上限）
2. スナップショット生成+署名のオーバーヘッドが **p95 で +50ms 超**（SC-006 の上限）

計測は `/perf-test` の標準手順 + e2e で取得し、実測値を #148 issue にフィードバックする（ダウンストリーム実データと突き合わせ）。生成時にスナップショット raw サイズをログ（debug）に出し、warning 閾値（既定 256 KB raw、設定可能）を超えたら warning を出す。

**Rationale**: `cart.masters.items` は「このカートでスキャンされた商品だけ」のセッションスナップショット（#146 で確認済み）なので、サイズは明細数に対して有界。机上見積りでは超過しない見込みであり、対策を先回りで作り込むのは過剰。

## R-009: restore API のエンドポイント形状

**Decision**: **`POST /api/v1/carts/restore?terminal_id={terminal_id}`**（cart ルーター配下、リクエストボディ = スナップショットエンベロープ全体）。認証は既存の端末 API キー/JWT 依存（`get_terminal_info_with_jwt_or_apikey`）をそのまま使う。レスポンスは `ApiResponse[Cart]` に統一し、`data.signed_snapshot` に最新スナップショット、復元結果（新規復元 / 既存返却）と差分有無は `data` 内の専用フィールド（`restored: bool`, `diverged: bool`）で返す（FR-006 の差分通知）。

**Rationale**: `cart_id` はボディ（スナップショット内）にあるためパスパラメータにしない（カートが存在しない前提の操作）。既存エンドポイントの認証・レスポンス規約（`ApiResponse[Cart]`、`terminal_id` クエリ）に完全に揃え、クライアントの追加学習を最小化する。

**Alternatives considered**: `PUT /carts/{cart_id}` 形式: 「クライアントが状態を書き込む」セマンティクスに見え、phase 1 の「サーバが正・上書きしない」原則と誤解を生む。却下。

## R-010: エラーコードの割当て

**Decision**: cart 予約帯（業務エラー 40YYZZ の 401xxx–404xxx）のうち未使用の **`4015xx` をスナップショット/restore 用サブカテゴリ**として割り当てる（`cart_error_codes.py` に追加）:

- `401501` 署名不一致 / `401502` 検証不能（署名欠落・形式不正） / `401503` 未知の kid・鍵期限切れ / `401504` スキーマバージョン非対応 / `401505` テナント/店舗スコープ違反 / `401506` 終端状態スナップショットの復元要求（冪等応答用） / `401507` スナップショット生成失敗（内部）

**Note**: spec FR-009 は当初 CLAUDE.md の記述に従い「30YYZZ 体系」と書いたが、実装上の cart 業務エラーは `40YYZZ`（`services/cart/app/exceptions/cart_error_codes.py`、4010xx–4040xx 使用済み）である。**spec FR-009 の表記を実態（cart のエラーコード体系 = cart_error_codes.py の予約帯）に合わせて修正する**。

## Technical Context の確定

| 項目 | 値 |
|---|---|
| 言語 | Python 3.12+（既存どおり） |
| 主要依存 | FastAPI / Pydantic v2 / Motor。署名は標準ライブラリ `hmac`+`hashlib`+`json` のみ（**新規依存なし**） |
| ストレージ | MongoDB（テナント別 `db_cart_{tenant_id}`）に `log_cart_restore` 新設。Redis（Dapr cartstore）は既存どおり |
| テスト | pytest 3 層（unit: 署名/正規化/エンベロープ、integration: レスポンス付加 + restore + 衝突/拒否、e2e: 取引継続シナリオ） |
| 性能目標 | p95 +50ms 以内 / 40 商品カート gzip 後 15KB 以下（実測検証） |
| 前提 | #147（gzip）完了後に有効化判断。実装・テストは並行可 |
