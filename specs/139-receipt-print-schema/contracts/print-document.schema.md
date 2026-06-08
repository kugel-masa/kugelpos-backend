# 印字データ JSON スキーマ定義（`print_document`）

- **ステータス**: ドラフト（#139）
- **対象**: backend（kugel_common 経由で cart/terminal/report）が生成し、消費者（frontend/device）が描画/転送する印字データ
- **関連**: [spec.md](../spec.md)（#139）、流用元 stpos-backend #316 contracts
- **出力形式**: camelCase JSON（消費者向け契約）。pydantic は `model_dump(by_alias=True, exclude_none=True)` で出力

> **前提**:
> - 複数カラム行は `columns` 要素で表し、**各カラムが独立した `value`・`style`・位置**を持つ（カラム単位の倍角/強調が可能）。
> - カラム位置は backend が **`metadata.charsPerLine`（設計基準桁数）** を基準に設計する。`mid` は左からの固定オフセット `startCol`、`right` は右端終端。
> - **桁揃え（空白計算・配置）と実機描画は消費者の責務**。backend は意味カラムを出力し空白を焼き込まない。
> - `style`（倍角・強調等）は **`text` は行単位 / `columns` はカラム単位**で適用。
> - R/J/RJ チャネル（ステーション）は backend の**内部ルーティング属性**であり、各要素を `print_document`（R/RJ）と `journal_text`（J/RJ）へ振り分ける。**この属性は本スキーマ（JSON 出力）には現れない** — `print_document` は R/RJ のレシートビューのみを表す（下記「ルーティングチャネル」参照）。

---

## ドキュメント構造

```jsonc
{
  "schemaVersion": "1.0",
  "metadata": { /* 下記 */ },
  "elements": [ /* 順序付き印字要素列 */ ]
}
```

### metadata

> **凡例（必須）**: ○＝常に出力（既定値あり）。△＝任意（値が無ければ `exclude_none` で出力から省略）。消費者は△フィールドの欠落を許容すること。

| フィールド | 型 | 必須 | 既定 | 説明 |
|---|---|---|---|---|
| `documentType` | string | ○ | `"receipt"` | `"receipt"`（帳票は `"report"` を想定） |
| `tenantId` | string | △ | — | テナント識別子（None 時は省略） |
| `storeCode` | string | △ | — | 店舗コード（None 時は省略） |
| `terminalNo` | int | △ | — | 端末番号（None 時は省略） |
| `transactionNo` | int | △ | — | 取引番号 |
| `receiptNo` | int | △ | — | レシート番号 |
| `businessDate` | string(`YYYY-MM-DD`) | △ | — | 営業日 |
| `generatedAt` | string(ISO8601) | △ | — | 生成時刻（タイムゾーン付き、None 時は省略） |
| `locale` | string | ○ | `"ja-JP"` | 例 `"ja-JP"` |
| `charsPerLine` | int | ○ | `32` | **設計基準桁数（半角換算）**。`columns` の `startCol`・右端終端・`text` 整列はこの桁数を基準に設計する。消費者はこの値を基準に実機幅へ適合させる |

---

## elements（`type` で判別する要素ユニオン）

### `text` — 単一内容のテキスト1行
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"text"` | — | |
| `value` | string | — | 印字文字列（1行） |
| `align` | `left`\|`center`\|`right` | `left` | 行全体の寄せ（`charsPerLine` 基準） |
| `style` | Style | （なし） | **行単位**の文字修飾 |

### `columns` — 複数カラム行
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"columns"` | — | |
| `columns` | Column[] | — | カラムの配列。任意組み合わせ（`left`+`right` だけ／`left`+`mid`+`right` 等） |

#### Column
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `slot` | `left`\|`mid`\|`right` | — | `left`=左端起点 / `mid`=`startCol` 起点 / `right`=右端終端 |
| `value` | string | — | カラムの文字列 |
| `startCol` | int | — | **`mid` のみ必須**。左からの固定オフセット（半角換算・0始まり、`charsPerLine` 基準） |
| `align` | `left`\|`center`\|`right` | `left`（`right` slot は `right`） | カラム内の寄せ |
| `style` | Style | （なし） | **カラム単位**の文字修飾 |

**レイアウト規則（消費者が実施）**
- `left` は col 0 から、`mid` は `startCol` から右へ、`right` は右端へ寄せる。
- 桁衝突時は `mid` の開始位置で `left` を切詰める（同様に `right` の開始位置で `mid` を切詰める）。
- 倍角カラムは 2 セル換算で配置する。
- `charsPerLine`（設計基準）と実機幅が異なる場合、消費者が `charsPerLine` を基準に実幅へ適合させる。

### `ruledLine` — 区切り罫線
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"ruledLine"` | — | |
| `char` | string | `"-"` | 罫線文字。幅いっぱいに敷く |

### `feed` — 行送り
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"feed"` | — | |
| `lines` | int | — | 送る行数（1–255） |

### `cut` — レシートカット
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"cut"` | — | |
| `mode` | `full`\|`partial` | `full` | 全カット / 部分カット |

### `barcode` — バーコード
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"barcode"` | — | |
| `symbology` | string | — | `jan13`/`ean13`/`jan8`/`code39`/`code93`/`code128`/`itf`/`codabar`/`gs1-128` 等（論理名） |
| `data` | string | — | バーコードデータ |
| `height` | int | 機種既定 | バーコード高さ（dot） |
| `moduleWidth` | int | 機種既定 | モジュール幅 |
| `hri` | `none`\|`above`\|`below` | `none` | 人間可読文字（HRI）の位置 |
| `align` | `left`\|`center`\|`right` | `center` | 配置 |

### `qrcode` — QRコード
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"qrcode"` | — | |
| `data` | string | — | QRデータ |
| `errorCorrection` | `L`\|`M`\|`Q`\|`H` | `M` | 誤り訂正レベル |
| `moduleSize` | int | 機種既定 | モジュールサイズ |
| `align` | `left`\|`center`\|`right` | `center` | 配置 |

### `image` — 画像
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"image"` | — | |
| `source` | `{ kind: "base64"\|"url", data: string, format?: string }` | — | 画像ソース（base64 埋め込み or URL） |
| `align` | `left`\|`center`\|`right` | `center` | 配置 |
| `width` | int \| `"auto"` | `"auto"` | 幅（dot）。`auto`=原寸 |

### `logo` — 事前登録ロゴ
| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `type` | `"logo"` | — | |
| `logoId` | string | — | 消費者/プリンタに事前登録したロゴ識別子 |
| `align` | `left`\|`center`\|`right` | `center` | 配置 |

---

## Style（文字修飾。`text`=行単位 / `columns` のカラム=カラム単位）

| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `bold` | bool | `false` | 強調 |
| `underline` | int (0/1/2) | `0` | 下線（0=なし、1/2=ドット） |
| `reverse` | bool | `false` | 白黒反転 |
| `scaleWidth` | int (1–8) | `1` | 横倍角 |
| `scaleHeight` | int (1–8) | `1` | 縦倍角 |
| `font` | `A`\|`B` | `A` | フォント |

> 能力依存: 非対応の修飾は消費者側で無視/縮退してよい（本リポジトリは指定を保持するのみ）。

---

## ルーティングチャネル（R/J/RJ・内部属性）

各印字要素は backend の内部に R/J/RJ チャネル（ステーション）を持つ。これは出力の振り分けにのみ使い、**JSON スキーマには出力しない**。

| チャネル | 意味 | `print_document`（本 JSON） | `journal_text`（プレーンテキスト） |
|---|---|---|---|
| `R` | レシートのみ | 含む | 含まない |
| `J` | 電子ジャーナルのみ | 含まない | 含む |
| `RJ`（既定） | 両方 | 含む | 含む |

- backend（`AbstractReceiptData`）が要素を R/RJ → `print_document`、J/RJ → `journal_text` に振り分ける。
- 戦略は `line_split`/`line_left`/… の `channel` 引数で指定する（既定 `RJ`）。例: JAN コード行を `channel="J"` にすると電子ジャーナルにのみ残る。
- **本 JSON（`print_document`）は R/RJ のレシートビューのみ**であり、`channel` 属性は含まれない。

---

## 設計上のポイント

- **桁揃えは消費者**。backend は `charsPerLine` を基準に意味カラム（left/mid/right）と位置を出力し、空白を焼き込まない。
- **カラム単位の修飾が可能**（金額カラムだけ倍角 等）。カラム内スパン粒度は対象外。
- 文字コードは UTF-8。対象デバイス文字セットへの変換は消費者が担う。

---

## 例

- [examples/normal-sale.json](../examples/normal-sale.json) — 通常販売レシート（ロゴ・倍角タイトル・複数カラム明細・カラム単位修飾・バーコード・QR・カット）
- [examples/builder-example.py](../examples/builder-example.py) — 上記を生成するアプリ側コード例
