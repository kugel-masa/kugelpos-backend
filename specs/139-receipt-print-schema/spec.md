# Feature Specification: device-agnostic な印字データスキーマ（XML 撤去・JSON 化・表現力拡張）

**Feature Branch**: `139-receipt-print-schema`
**Created**: 2026-06-07
**Status**: Draft
**SPEC_TYPE**: functional
**Issue**: [#139](https://github.com/kugel-masa/kugelpos-backend/issues/139)
**派生元**: stpos-backend `316-device-print-schema`（流用・kugelpos #139 向けに再スコープ）

---

## 概要

POS のレシート/ジャーナル印字において、現在 backend（kugel_common 経由で cart / terminal / report）が `receipt_text` に入れている **XML 形式の印字データの中身を、OPOS や特定プリンタ機種に依存しない device-agnostic な JSON（`print_document` スキーマ）へ全面移行**する。**フィールド名（`receipt_text`）・型（`str`）は据え置き、中身（テキスト）を XML→JSON へ変える**。あわせて表現力を拡張する（位置・倍角等の文字修飾・ロゴ・画像・バーコード・QR・行送り・レシートカット）。

本フィーチャーのスコープは **backend（本リポジトリ）が生成する印字データの「形式」と「生成ロジック」** に限定する。印字データを実機コマンドへ変換・描画する device-gateway 相当の処理は本リポジトリのスコープ外であり、最終描画は印字データの消費者（frontend / device）の責務とする（Issue #139）。

具体的には:

1. 印字データを **device-agnostic な意味表現** として再設計し表現力を拡張する。
2. 形式を **XML から JSON へハードカットオーバー**する（並行運用・XML フォールバックなし）。
3. backend は **意味カラム**（各カラムの値・位置・修飾）を出力し、桁揃え（空白計算・配置）と実機描画は **消費者の責務**とする。
4. `journal_text`（電子ジャーナル・プレーンテキスト）は **維持** する。

これにより backend は OPOS 仕様・プリンタ機種差から分離され、印字機能の拡張（ロゴ・画像・バーコード等）がデータ表現の追加だけで可能になる。

---

## Clarifications

### Session 2026-06-07

- Q: stpos #316 の DeviceGW API 契約（文書印字 API・冪等性・状態/能力照会・OPOS エラー正規化）と frontend パススルー契約は本フィーチャーに含めるか？ → A: **スコープ外に整理**。本フィーチャーの成果物は backend の印字データ JSON スキーマ（kugel_common）と生成ロジック（cart/terminal/report 戦略）まで。実機変換・描画・非同期印字ジョブ・冪等性・能力照会は消費者（frontend/device）の責務とし、Out of Scope に記載のうえ短く参照するに留める（Issue #139 の Out of scope に一致）。
- Q: terminal の開閉店/現金レシートの JSON 化を本フィーチャーに含めるか？ → A: **含める**。kugel_common の XML 生成廃止（ハードカットオーバー）に伴い必須。cart と同時に JSON 化する。
- Q: kugelpos に #73 相当の R/J/RJ チャネル振り分けは存在するか？ → A: **元の実装には存在しなかった**（`receipt_text`(XML) と `journal_text`(plain) は同一ツリーから別レンダリングするだけ）。**当初は導入しない方針だったが、後続の合意で R/J/RJ チャネルを導入**（下記 2026-06-07 追補・FR-007 改訂）。
- 追補（2026-06-07）: **R/J/RJ チャネル（ステーション）指定をサポートする**。各印字要素に `channel`（R=レシートのみ / J=電子ジャーナルのみ / RJ=両方・既定）を持たせ、backend が**内部で**振り分ける（R/RJ→レシート、J/RJ→`journal_text`）。チャネルは内部ルーティング属性で **JSON 出力には現れない**。既定 RJ のため既存戦略の内容は不変（機能追加のみ。production 戦略でのチャネル実利用は後続）。
- 確定（2026-06-07・最重要）: **フィールド名は `receipt_text`、型は `str` のまま据え置く**。新フィールド `print_document` は追加しない。**`receipt_text` の中身（テキスト）を XML 文字列 → JSON 文字列に変える**だけ（JSON は `print_document` スキーマ＝`schemaVersion`/`metadata`/`elements` を `json.dumps` した文字列）。`journal_text` も従来どおり。これにより `tranlog`／各ログ文書／API レスポンス／pub-sub の**フィールド名・型は一切変わらず**、cart/terminal/journal/report の document・schema・transformer は**無改変**。変更は kugel_common（生成ロジック）に閉じる。`print_document` という語は本仕様では**保存フィールド名ではなく JSON スキーマ（印字文書）の呼称**として用いる。
- Q: XML→JSON 移行の形は？ → A: **ハードカットオーバー（XML を残さず JSON のみ）**。並行運用・XML フォールバックは設けない。理由＝二重保持の容量回避（pub-sub / sync / 保存）。過去データ（XML を持つ tranlog / journal_document）はマイグレーションせず、読み出し側は XML・JSON 混在を許容する。
- Q: 文字コードは？ → A: パイプラインは **UTF-8** のまま通す。対象デバイスの文字セット（例 Shift-JIS）への変換とマップ不能文字の代替は消費者/device の責務（本リポジトリは UTF-8 維持）。

---

## 影響するサービス

> **重要**: 変更は **kugel_common（生成ロジック）に閉じる**。`receipt_text` のフィールド名・`str` 型・スキーマは全サービスで不変で、**中身が XML 文字列→JSON 文字列に変わるだけ**。よって cart/terminal/journal/report のコード（document・schema・transformer・戦略）は**無改変**。

| サービス名 | 変更の種類 | 変更の概要 |
|---|---|---|
| kugel_common（共通ライブラリ） | 変更 | 意味要素ベースの印字データモデル（`print_document` スキーマ）を追加。`AbstractReceiptData` の **XML 生成経路（`PrintData.to_xml`・`make_receipt_text`）を撤去**し、`receipt_text` に **JSON 文字列**を入れる（`json.dumps(print_document)`）。`journal_text` 生成は維持。`BaseTransaction.receipt_text` は **`Optional[str]` のまま**（型・名前不変） |
| cart | 影響なし（中身のみ変化） | 戦略（`ReceiptDataSample`）・`tranlog`・Cart API レスポンス・pub/sub ペイロードは**無改変**。`receipt_text` の中身が XML→JSON 文字列に変わる |
| terminal | 影響なし（中身のみ変化） | 開閉店/現金レシート戦略・`open_close_log`／`cash_in_out_log`・API は**無改変**。`receipt_text` の中身が JSON 文字列に |
| journal | 影響なし（中身のみ変化） | 監査保存・API 配信は**無改変**。保存する `receipt_text` の中身が JSON 文字列に |
| report | 影響なし（中身のみ変化） | 帳票生成器（sales/item/payment/category）・帳票ドキュメント・API は**無改変**。`receipt_text` の中身が JSON 文字列に |

**影響なしのサービス（確認済み）**: account, master-data, stock。

---

## 変更する Pub/Sub トピック

| トピック | 変更の種類 | 発行者 | 購読者 | 変更の概要 |
|---|---|---|---|---|
| `tranlog_report`（`topic-tranlog`/`-cloud`） | 中身のみ変化（スキーマ不変） | cart | report, journal, stock | `tranlog` ペイロードのフィールド（`receipt_text`/`journal_text`）は不変。`receipt_text` の中身が XML→JSON 文字列に変わるのみ（購読側のコード改修は不要） |

> トピックのパブリッシャー/サブスクライバー割り当て・ペイロードのフィールド構成は変更しない。変更するのは **`receipt_text` の中身**（XML→JSON 文字列）。Edge↔Cloud sync のペイロードも中身が変わる（XML 撤去により容量は削減方向）。

---

## 変更するインターフェース

| インターフェース | 変更の種類 | 影響するサービス | 後方互換性 |
|---|---|---|---|
| 印字データモデル（kugel_common 内部） | 置換（JSON 新設・XML 撤去） | kugel_common | **破壊的（commons 内部のみ）**。外部公開フィールドは不変 |
| Cart API レスポンス（`POST /carts/{cart_id}/bill` 等） | 中身のみ変化 | cart | フィールド不変。`receipt_text` の中身が XML→JSON 文字列。`journal_text` 維持 |
| Terminal API レスポンス（開閉店/現金入出金） | 中身のみ変化 | terminal | フィールド不変。`receipt_text` の中身が XML→JSON 文字列 |
| `tranlog` ドキュメント（共有・MongoDB/pub-sub/sync） | 中身のみ変化 | cart, report, journal | フィールド不変。`receipt_text` の中身が JSON 文字列に（pub-sub/sync も中身のみ・容量は削減方向） |
| `journal_document` / `open_close_log` / `cash_in_out_log` | 中身のみ変化 | journal, terminal, report | フィールド不変。保存する `receipt_text` の中身が XML→JSON へ |
| 帳票（report）API レスポンス | 中身のみ変化 | report | フィールド不変。`receipt_text`（`receiptText`）の中身が JSON へ |

---

## 後方互換性

**方針：ハードカットオーバー（XML を残さず JSON のみへ全面切替）。理由＝保持・配信・sync するデータ容量の削減。**

- **スキーマ**: フィールド名・型は不変。`receipt_text` の中身を XML→JSON 文字列へ変更。`journal_text` は維持。
- **API**: フィールドは不変。`receipt_text` の中身が JSON 文字列に変わる。消費者は中身を JSON として解釈する。
- **既存データ**: 過去の `tranlog`／`journal_document` 等は `receipt_text`(XML) のまま残す（マイグレーションしない）。読み出し側は **歴史データ=XML・新規=JSON の混在**を許容すること。
- **リスク**: 単一リリースでの全面切替のため、cart/terminal/journal/report の同時整合が必須。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 取引確定時に device-agnostic な JSON 印字データを生成 (Priority: P1)

会計係が取引を確定すると、backend（cart）は OPOS にもプリンタ機種にも依存しない、意味単位で構造化された JSON 印字データ（`print_document`）を生成して返す。消費者はその内容を解釈・加工せずに描画/転送できる。

**独立テスト可能性**: テスト用取引でレシートを生成し、返却 JSON が定義済みスキーマに適合し、移行前の `receipt_text`(XML) と論理的に等価な内容（同一の行・順序・文言）であることを検証する。

**Affected Services**: kugel_common, cart

#### Acceptance Criteria
1. **Given** 通常販売取引, **When** 取引を確定する, **Then** Cart レスポンスと `tranlog` の `receipt_text`（`str`・フィールド名不変）に新スキーマ準拠の JSON 文字列（`print_document` スキーマ）が入る
2. **Given** 同一取引, **When** JSON と移行前 XML を比較する, **Then** 両者が表現する印字行（文言・順序）が論理的に一致する
3. **Given** JSON 印字データ, **When** スキーマ検証を行う, **Then** `schemaVersion` を含むスキーマに完全適合する
4. **Given** 取引確定後の `tranlog` / Cart レスポンス, **When** `receipt_text` の中身を確認する, **Then** XML ではなく `print_document` スキーマ準拠の JSON 文字列であり（フィールド名・`str` 型は不変）、`journal_text` は従来どおり生成される

---

### User Story 2 - 印字の修飾・位置を表現できる (Priority: P1)

レシート設計者が、各印字要素に対し位置（左/中央/右）と文字修飾（倍角縦・倍角横・強調・下線・白黒反転・フォント切替）を指定でき、その指定が JSON に保持される。

**独立テスト可能性**: 各修飾・各位置を指定した要素を生成し、JSON 上で対応する属性が保持されることを検証する。

**Affected Services**: kugel_common, cart

#### Acceptance Criteria
1. **Given** 中央寄せ・倍角（縦横）・強調を指定したテキスト要素, **When** 生成する, **Then** 位置=中央・倍角縦横・強調の各属性が要素に保持される
2. **Given** 左/中央/右の各位置指定, **When** 生成する, **Then** それぞれが区別可能な値として保持される
3. **Given** 修飾を指定しない要素, **When** 生成する, **Then** 既定（位置=左・等倍・修飾なし）が適用される

---

### User Story 3 - ロゴ・画像・バーコード・QR・行送り・カットを表現できる (Priority: P1)

レシート設計者が、ロゴ・画像・バーコード・QR・行送り・レシートカットを印字データ上で指定でき、消費者がそれらを実機に出力できる形で保持される。

**独立テスト可能性**: 各要素を含む印字データを生成し、JSON 上で各要素タイプと必須パラメータが表現されることを検証する。

**Affected Services**: kugel_common, cart

#### Acceptance Criteria
1. **Given** バーコード要素（シンボロジー・データ・高さ・HRI 位置）, **When** 生成する, **Then** それらが保持される
2. **Given** QR 要素（データ・誤り訂正レベル・モジュールサイズ）, **When** 生成する, **Then** それらが保持される
3. **Given** 画像要素（base64 または URL 参照・位置）, **When** 生成する, **Then** ソース種別とデータが保持される
4. **Given** ロゴ要素（登録ロゴ識別子）, **When** 生成する, **Then** ロゴ識別子が保持される
5. **Given** 行送り（行数）／レシートカット（全/部分）要素, **When** 生成する, **Then** それぞれが区別可能な要素として保持される

---

### User Story 4 - 複数カラム行を意味情報として出力できる (Priority: P1)

レシート設計者が、1 行内に複数カラム（`left`/`mid`/`right`）を、空白を焼き込まない**意味情報**として出力できる。`mid` は左からの固定オフセット `startCol` で開始位置を指定する。各カラムは独立した値・位置・修飾を持てる（例：金額カラムのみ倍角）。桁揃え（空白計算・配置）は消費者の責務とする。

**独立テスト可能性**: `left`/`mid`/`right` の組み合わせを含む行を生成し、JSON 上でカラム値・`startCol`・カラム単位 `style` が保持され、整形済みテキスト（空白埋め込み）になっていないことを検証する。

**Affected Services**: kugel_common, cart

#### Acceptance Criteria
1. **Given** `left`+`right` のみ／`left`+`mid`+`right` の行, **When** 生成する, **Then** 各カラムが意味情報として保持される
2. **Given** `mid` カラム, **When** 生成する, **Then** `startCol`（半角換算・`charsPerLine` 基準）で開始位置が保持される
3. **Given** カラム単位 `style`（倍角等）, **When** 生成する, **Then** 各カラムに独立して保持される
4. **Given** いずれのカラムも, **When** 生成する, **Then** 整形済みテキスト（空白埋め込み済み）ではなく値そのものが保持される

---

### Edge Cases

- すべての行を含む取引で `journal_text`（プレーンテキスト）は従来どおり生成されるか？
- 取消取引（VoidSales/VoidReturn）の印字データはどう表現されるか？（現状は「取引中止」レシートを生成。挙動を回帰なく維持する）
- 倍角・カラム単位修飾を含む `print_document` がスキーマ検証に適合するか？
- 文字コード: UTF-8 のまま JSON へ載るか（Shift-JIS 変換は消費者責務で本リポジトリは変換しない）。
- 歴史データ（XML を持つ `tranlog`/`journal_document`）を読み出し側がエラーなく扱えるか。

---

## Functional Requirements *(mandatory)*

### FR-001: device-agnostic な印字データスキーマの定義
**Description**: OPOS・特定プリンタ機種に依存しない、意味単位で構造化された印字データスキーマ（`print_document`）を kugel_common に定義する。スキーマはバージョン識別子（`schemaVersion`）・文書メタデータ・順序付き印字要素列を持つ。
**Affected Services**: kugel_common
**Priority**: P1
**Acceptance Criteria**:
- スキーマがバージョン識別子（`schemaVersion`）を持つこと
- 印字要素が出現順序を保持する列として表現されること
- 文書メタデータ（文書種別・テナント/店舗/端末識別・取引/レシート番号・営業日・生成日時・ロケール・`charsPerLine`＝設計基準桁数）を表現できること

### FR-002: テキスト要素と位置・文字修飾
**Description**: テキスト要素に位置（左/中央/右）と文字修飾（倍角縦・倍角横・強調・下線・白黒反転・フォント選択）を指定できること。
**Affected Services**: kugel_common, cart
**Priority**: P1
**修飾の粒度（設計注記）**:
- 修飾の粒度は **`text` 要素＝行単位 / `columns` 要素＝カラム単位**。1 カラム内の一部だけの修飾（スパン粒度）は本フィーチャーのスコープ外。
- 位置（align）は行/要素レベル属性。倍角の倍率は 1〜8。
- 修飾はレシート（視覚）専用。`journal_text`（プレーンテキスト）には反映しない。
**Acceptance Criteria**:
- 位置（左/中央/右）を指定でき、未指定時は既定値が適用されること
- 倍角（縦・横を独立指定、1〜8）・強調・下線・白黒反転・フォント選択を指定できること
- 修飾を指定しない場合、等倍・修飾なしが既定となること

### FR-003: 複数カラム行（left/mid/right・意味情報）
**Description**: 1 行内に複数カラム（`left`=左端起点 / `mid`=`startCol` 起点 / `right`=右端終端）を表現する `columns` 要素を持つこと。各カラムは独立した値・位置・`style` を持つ。カラムは空白を詰めた整形済みテキストにせず**意味情報**として出力する。桁揃えは消費者の責務。
**Affected Services**: kugel_common, cart
**Priority**: P1
**Acceptance Criteria**:
- 1 行で `left`/`mid`/`right` の任意組み合わせを表現できること
- `mid` は左からの固定オフセット `startCol`（半角換算・`charsPerLine` 基準）で開始位置を指定できること
- 各カラムに独立して文字修飾を指定できること
- カラムが整形済みテキストではなく意味情報として出力されること

### FR-004: 罫線・行送り・レシートカット要素
**Affected Services**: kugel_common, cart
**Priority**: P1
**Acceptance Criteria**:
- 罫線要素（使用文字）を表現できること
- 行送り要素（行数）を表現できること
- レシートカット要素（全カット/部分カット）を表現できること

### FR-005: バーコード・QRコード要素
**Affected Services**: kugel_common, cart
**Priority**: P1
**Acceptance Criteria**:
- 代表的なシンボロジー（JAN/EAN・CODE128・CODE39・ITF 等）を指定できること
- バーコードの高さ・HRI 位置（なし/上/下）を指定できること
- QR の誤り訂正レベル・モジュールサイズを指定できること

### FR-006: 画像・ロゴ要素
**Affected Services**: kugel_common, cart
**Priority**: P1
**Acceptance Criteria**:
- 画像要素がソース種別（base64/URL）とデータ、位置を表現できること
- ロゴ要素が登録ロゴ識別子を表現できること

### FR-007: R/J/RJ チャネル（ステーション）による振り分け
**Description**: 各印字要素に R/J/RJ チャネルを指定でき、backend が**内部で**振り分ける。R/RJ → レシート内容（`print_document`）、J/RJ → 電子ジャーナル `journal_text`。未指定時は両方（RJ）。チャネルは backend のルーティング属性であり **`print_document`(JSON) には出力しない**（消費者はレシートビューのみを受領）。`journal_text` は従来どおり回帰なく維持する。
**Affected Services**: kugel_common, cart, terminal, report
**Priority**: P1
**Acceptance Criteria**:
- 各印字要素に R/J/RJ チャネルを指定でき、未指定時は両方（RJ）となること
- `print_document` が R/RJ 要素のみを含むこと（J 要素は含まない）
- `journal_text` が J/RJ 要素のみから生成されること（R 要素は含まない）
- チャネル属性が `print_document`(JSON) の出力に**現れないこと**（内部ルーティングのみ）
- 既定 RJ により、チャネル未使用の既存戦略のレシート/ジャーナル内容が回帰しないこと

### FR-008: JSON 形式での出力（XML 置換）
**Description**: `receipt_text`（フィールド名・`str` 型は維持）の**中身を XML 文字列から JSON 文字列へ**変更する。JSON は `print_document` スキーマを `json.dumps` した文字列。XML（`PrintData.to_xml`）生成経路は撤去する。`journal_text` は維持する。
**Affected Services**: kugel_common
**Priority**: P1
**Acceptance Criteria**:
- `receipt_text` が `print_document` スキーマ準拠の JSON 文字列を保持すること（フィールド名・`str` 型は不変）
- XML を生成・保存・配信する経路が製品コードに残っていないこと
- `journal_text` は従来どおり生成・維持されること

### FR-009: 全サービスの印字生成器の JSON 化（cart/terminal/report）
**Description**: `AbstractReceiptData` を継承する全 7 生成器（cart 取引×1、terminal 開閉店/現金×2、report 帳票 sales/item/payment/category×4）が `print_document` を出力すること。基底の XML 経路撤去に伴い全生成器が一貫して JSON を出力する。
**Affected Services**: kugel_common, cart, terminal, report
**Priority**: P1
**Acceptance Criteria**:
- 7 生成器すべてが `print_document` を出力すること
- 既存の `line_*` 系ヘルパ（line_split/center/left/right/boarder）が新スキーマ上で機能すること（後方互換シム）
- 各生成器の `journal_text` 出力が回帰しないこと

### FR-010: 協調リリースと歴史データの取り扱い
**Description**: 本フィーチャーは破壊的変更（XML 撤去）であり後方互換は維持しない。協調リリースの整合と歴史データの読み出し許容を要件とする。
**Affected Services**: kugel_common, cart, terminal, report, journal
**Priority**: P1
**Acceptance Criteria**:
- XML を生成・保存・配信する経路が製品コードに残っていないこと（kugel_common/cart/terminal/report）
- journal/report が `print_document`(JSON) を正しく保存・参照できること
- 過去に保存済みの `receipt_text`(XML) を持つ `tranlog`／ログ文書を、読み出し側がエラーなく扱えること（混在許容）

---

## Non-Functional Requirements

| 項目 | 要件 | 備考 |
|---|---|---|
| パフォーマンス | JSON 印字データ生成によるレシート生成時間の増加が ±10% 以内 | 行数に比例する線形処理 |
| 容量 | XML 撤去により `tranlog`／pub-sub／sync／ログ文書のレシート表現が JSON 単一となり二重保持が無いこと | 本切替の主目的 |
| 互換性 | 新規フィールドはすべてデフォルト値を持ち、既存データのデシリアライズを壊さないこと | 歴史データ読み出し許容 |

---

## Data Model Changes

- **新規（kugel_common）**: device-agnostic 印字データモデル `PrintDocument`（文書メタデータ＋順序付き印字要素列）。要素は種別（text/columns/ruledLine/feed/cut/barcode/qrcode/image/logo）で区別され、各種別が固有パラメータと共通の修飾・位置属性を持つ。出力は camelCase JSON（消費者向け契約）。
- **撤去（kugel_common）**: XML を生成する経路（`PrintData.to_xml`・`make_receipt_text`）を廃止。`journal_text` 生成（`to_text` 相当）は維持。
- **変更（kugel_common の生成ロジックのみ）**: `receipt_text`（`str`）の中身を XML→JSON 文字列に変更。`tranlog`／`journal_document`／`open_close_log`／`cash_in_out_log`／API レスポンスの**フィールド名（`receipt_text`）・型（`str`）は不変**。cart/terminal/journal/report の document・schema・transformer は無改変。`journal_text` 維持。
- **既存データ**: マイグレーションしない（歴史データは XML・新規は JSON の混在を許容）。

> 具体的な JSON フィールド名・要素タイプ名・pydantic 表現は [contracts/print-document.schema.md](./contracts/print-document.schema.md) で定義する。

---

## Dependencies & Prerequisites

| 依存先 | 種類 | 理由 |
|---|---|---|
| stpos-backend #316 spec | 流用元 | 本仕様の派生元。スキーマ契約・例を再利用 |
| Issue #139 | 要件 | スコープ（backend の形式と生成ロジックに限定）の確定根拠 |

---

## Success Criteria

- **SC-001**: 取引確定時、新スキーマ準拠の `print_document` が生成され、スキーマ検証に **100% 適合**する
- **SC-002**: 切替前後で同一取引のレシート内容（行・順序・文言）が**論理的に保たれる**（開発時は旧 XML 生成結果を基準に等価性を検証）
- **SC-003**: 要求された全表現（位置・倍角等修飾・ロゴ・画像・バーコード・QR・行送り・カット・複数カラム）が JSON で表現可能であることが各要素テストで確認される
- **SC-004**: 切替後、XML 生成・保存・配信経路が製品コードから**消えている**こと。journal/report が JSON を正しく扱い、歴史データ（XML）の読み出しがエラーにならないこと
- **SC-005**: `journal_text` が回帰しないこと（移行前後で同一取引のプレーンテキストが一致）
- **SC-006**: 既存の単体テスト・結合テストが**全件パス**する

---

## Out of Scope

- **印字データを実機コマンドへ変換・描画する device-gateway 相当の処理**（OPOS/ESC-POS 等への変換、桁揃えの最終計算、実機描画）— 消費者（frontend/device）の責務
- デバイス能力差の吸収（カッター有無・非対応シンボロジー・非対応修飾の degradation）
- 非同期印字ジョブ実行・印字ジョブ冪等性（jobId）・状態/能力照会 API
- 対象デバイスの文字セット（Shift-JIS 等）への変換・マップ不能文字の代替（UTF-8 のまま消費者へ渡す）
- 既存ドキュメントの `receipt_text`(XML) → JSON データマイグレーション
- カラム内スパン粒度の文字修飾（行＝text／カラム＝columns 単位までを対象）
- 管理画面からのレシートレイアウト編集 UI

---

## 未解決事項（plan で確定）

- 画像/ロゴ要素を実際の戦略で使うか（初期は cart sample で showcase。report/terminal は最小変更で JSON 化）。
- 代替文字や倍角桁数換算は消費者責務のため本リポジトリでは規定しない（メタの `charsPerLine` のみ提供）。
- 帳票（report）レシートの `print_document` 文書種別（`documentType`）の値（`receipt` か `report` か）。
