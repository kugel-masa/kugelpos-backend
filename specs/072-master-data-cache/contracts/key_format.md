# Contract: キャッシュキー仕様

このファイルはキャッシュキー文字列の構造を公式に定める。実装はこの仕様にビット精度で従う必要がある。

## 通常エントリ

```
mdcache:{tenant_id}:{store_code or '_'}:{namespace}:gen{N}:s{shape}:{entry_kind}:{logical_key}
```

### セグメント定義

| # | セグメント | 文字種制約 | 必須 | 説明 |
|---|---|---|---|---|
| 1 | `mdcache` | 固定リテラル | yes | 本キャッシュ系統の prefix |
| 2 | `tenant_id` | `[A-Za-z0-9_-]+` | yes | テナント識別子。`:` 禁止 |
| 3 | `store_code or '_'` | `[A-Za-z0-9_-]+` または `_` | yes | 店舗識別子。テナントスコープのとき `_` 固定 |
| 4 | `namespace` | `[a-z_]+` | yes | `cache_namespace` クラス属性 |
| 5 | `gen{N}` | `gen` + 0 以上の整数 | yes | 世代カウンタ。`gen0`, `gen1`, ... |
| 6 | `s{shape}` | `s` + 16 進 12 桁 | yes | 文書モデルの形の指紋（`model_json_schema()` の SHA-256 先頭 12 桁）。モデルに欄を足したり型を変えたりした cart は別のキーを使うので、古い形のエントリを読まない（既定値で読む・検証で落ちるを防ぐ）。古いエントリは TTL で消える |
| 7 | `entry_kind` | `one` または `list` | yes | エントリ種別 |
| 8 | `logical_key` | 任意（ただし `:` 禁止） | yes | サブクラスが渡す論理キー |

### 制約

- セグメント区切りは `:` 固定。値中に `:` を含めてはならない（必要なら呼び出し側で `_` 等にサニタイズ）
- 各セグメントは空文字列禁止
- 全体長は Redis のキー上限（512 MB）に余裕で収まること。実用上は 256 バイト以下を目安

### 例

| シナリオ | キー |
|---|---|
| 商品マスタ単一参照（テナント T001、店舗 S001、商品 ITEM_A） | `mdcache:T001:S001:item_master:gen0:s{shape}:one:ITEM_A` |
| 支払マスタ単一参照（テナント T001、テナントスコープ、CASH） | `mdcache:T001:_:payment_master:gen0:s{shape}:one:CASH` |
| 販促マスタリスト参照（テナント T001、店舗 S002、active） | `mdcache:T001:S002:promotion_master:gen0:s{shape}:list:active` |
| 税マスタ単一参照（テナント T001、テナントスコープ、TAX10） | `mdcache:T001:_:tax_master:gen0:s{shape}:one:TAX10` |
| 設定マスタ全件（テナント T001、店舗 S001） | `mdcache:T001:S001:settings_master:gen0:s{shape}:list:__all__` |
| 設定マスタテナント設定全件（テナント T001、テナントスコープ） | `mdcache:T001:_:settings_master:gen0:s{shape}:list:__all__` |

## 世代カウンタキー

```
mdcache:{tenant_id}:{store_code or '_'}:{namespace}:generation
```

- 値: 整数（文字列表現）
- TTL: なし（コンポーネント既定の `ttlInSeconds: 300` を上書きするため `metadata={"ttlInSeconds": "0"}` を save 時に明示するか、save_state で TTL 指定なしにすることが必要 — 実装で確認）
- 更新: ETag による CAS。最大 3 回まで衝突リトライ
