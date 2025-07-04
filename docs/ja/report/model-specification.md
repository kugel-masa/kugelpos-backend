# レポートサービス モデル仕様

## 概要

レポートサービスは、包括的なビジネスレポートの生成と、トランザクション、現金操作、ターミナル活動からのイベントログの管理を担当します。拡張可能なレポート生成のためのプラグインアーキテクチャを実装し、複雑なデータ処理にMongoDBアグリゲーションパイプラインを使用し、日次レポート生成前の完全性を保証するデータ検証メカニズムを含みます。このサービスは、マルチテナント分離を備えた堅牢なビジネスインテリジェンス機能を提供します。

## データベースドキュメントモデル

すべてのドキュメントモデルは、監査、キャッシュ、シャーディング用の共通フィールドを提供する`AbstractDocument`を継承しています。

### AbstractDocument（基底クラス）

すべてのドキュメントに共通機能を提供する基底クラス。

**基底フィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| shard_key | string | - | 水平スケーリング用のデータベースシャーディングキー |
| created_at | datetime | - | ドキュメント作成タイムスタンプ |
| updated_at | datetime | - | 最終更新タイムスタンプ |
| cached_on | datetime | - | キャッシュ無効化用のキャッシュタイムスタンプ |
| etag | string | - | 楽観的並行性制御用のエンティティタグ |

### 1. SalesReportDocument（一時的レポートデータ）

APIレスポンス用の一時的ドキュメント構造（データベースに保存されない）。

**目的:** セールスレポートAPIレスポンス用のオンデマンド生成

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| store_name | string | - | 店舗表示名 |
| terminal_no | integer | - | ターミナル番号（店舗レベルレポートの場合null） |
| business_counter | integer | - | ビジネスカウンタ |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| open_counter | integer | - | ターミナルセッションカウンタ |
| report_scope | string | - | レポートスコープ（'flash'または'daily'） |
| report_type | string | - | レポートタイプ（'sales'） |
| sales_gross | SalesReportTemplate | - | 総売上メトリクス |
| sales_net | SalesReportTemplate | - | 純売上メトリクス |
| discount_for_lineitems | SalesReportTemplate | - | アイテムレベル割引メトリクス |
| discount_for_subtotal | SalesReportTemplate | - | トランザクションレベル割引メトリクス |
| returns | SalesReportTemplate | - | 返品トランザクションメトリクス |
| taxes | array[TaxReportTemplate] | - | 税コード別の税金内訳 |
| payments | array[PaymentReportTemplate] | - | 決済方法別内訳 |
| cash | CashReportTemplate | - | 現金引き出し照合 |
| receipt_text | string | - | フォーマットされたレシートテキスト |
| journal_text | string | - | フォーマットされたジャーナルテキスト |
| generate_date_time | string | - | レポート生成タイムスタンプ |
| staff | StaffMasterDocument | - | 利用可能な場合のスタッフ情報 |

### 2. CashInOutLog（現金操作記録）

現金の入出金操作ログを格納するドキュメント。

**コレクション名:** `log_cash_in_out`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| store_name | string | - | 店舗表示名 |
| terminal_no | integer | - | ターミナル番号 |
| staff_id | string | - | 操作を実行したスタッフ識別子 |
| staff_name | string | - | スタッフ表示名 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| open_counter | integer | - | ターミナルセッションカウンタ |
| business_counter | integer | - | ビジネス操作カウンタ |
| generate_date_time | string | - | イベントタイムスタンプ |
| amount | float | - | 操作金額（現金入金は正、現金出金は負） |
| description | string | - | 操作説明 |
| receipt_text | string | - | フォーマットされたレシートテキスト |
| journal_text | string | - | フォーマットされたジャーナルテキスト |

**インデックス:**
- 複合インデックス: (tenant_id, store_code, terminal_no, business_date)
- インデックス: amount

### 3. OpenCloseLog（ターミナルセッション記録）

ターミナル開店/閉店操作ログを格納するドキュメント。

**コレクション名:** `log_open_close`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| store_name | string | - | 店舗表示名 |
| terminal_no | integer | - | ターミナル番号 |
| staff_id | string | - | 操作を実行したスタッフ識別子 |
| staff_name | string | - | スタッフ表示名 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| open_counter | integer | - | ターミナルセッションカウンタ |
| business_counter | integer | - | ビジネス操作カウンタ |
| operation | string | - | 操作タイプ（'open'または'close'） |
| generate_date_time | string | - | イベントタイムスタンプ |
| terminal_info | TerminalInfoDocument | - | ターミナル状態情報 |
| cart_transaction_count | integer | - | 閉店時のトランザクション数 |
| cart_transaction_last_no | integer | - | 最後のトランザクション番号 |
| cash_in_out_count | integer | - | 現金操作数 |
| cash_in_out_last_datetime | string | - | 最後の現金操作タイムスタンプ |
| receipt_text | string | - | フォーマットされたレシートテキスト |
| journal_text | string | - | フォーマットされたジャーナルテキスト |

**インデックス:**
- 複合インデックス: (tenant_id, store_code, terminal_no, business_date, open_counter)
- インデックス: operation

### 4. DailyInfoDocument（日次レポート状況）

日次レポート生成状況とデータ検証を追跡するドキュメント。

**コレクション名:** `info_daily`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| terminal_no | integer | - | ターミナル番号 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| open_counter | integer | - | ターミナルセッションカウンタ |
| verified | boolean | - | データ検証状況 |
| verified_update_time | string | - | 最終検証タイムスタンプ |
| verified_message | string | - | 検証状況メッセージ |

**目的:** 日次レポート生成適格性の検証状況を追跡

**インデックス:**
- ユニーク複合インデックス: (tenant_id, store_code, terminal_no, business_date)
- インデックス: verified

### 5. トランザクションログ（kugel_commonから）

トランザクションデータはkugel_commonライブラリの`BaseTransaction`を使用。

**コレクション名:** `log_tran`

**使用される主要フィールド:**
- 明細項目、支払い、税金を含む完全なトランザクション記録
- 適切な集計のためのトランザクションタイプコード
- ビジネス日付とカウンタ情報
- レポート用の金額計算

## 埋め込みドキュメントモデル

### SalesReportTemplate

売上メトリクスのテンプレート構造。

**フィールド定義:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| amount | float | 合計金額 |
| quantity | integer | 合計アイテム数量 |
| count | integer | トランザクション数 |

### TaxReportTemplate

税金内訳構造。

**フィールド定義:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| tax_name | string | 税金表示名 |
| tax_amount | float | 徴収した税金合計 |
| target_amount | float | 課税対象金額ベース |
| target_quantity | integer | 課税対象アイテム数量 |

### PaymentReportTemplate

決済方法サマリー構造。

**フィールド定義:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| payment_name | string | 決済方法表示名 |
| amount | float | 合計決済金額 |
| count | integer | 決済トランザクション数 |

### CashInOutReportTemplate

現金操作サマリー構造。

**フィールド定義:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| amount | float | 合計現金操作金額 |
| count | integer | 現金操作数 |

### CashReportTemplate

現金引き出し照合構造。

**フィールド定義:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| logical_amount | float | 計算された予想現金金額 |
| physical_amount | float | 実際に数えた現金金額 |
| difference_amount | float | 差異（実際 - 論理） |
| cash_in | CashInOutReportTemplate | 現金入金操作サマリー |
| cash_out | CashInOutReportTemplate | 現金出金操作サマリー |

## APIリクエスト/レスポンススキーマ

すべてのスキーマは、JSON直列化の際にsnake_caseからcamelCaseへの自動変換を提供する`BaseSchemaModel`を継承しています。

### リクエストスキーマ

#### レポート生成リクエスト（クエリパラメータ）
レポート生成のリクエストパラメータ。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| reportScope | string | ✓ | レポートスコープ（'flash'または'daily'） |
| reportType | string | ✓ | レポートタイプ（'sales'） |
| businessDate | string | ✓ | ビジネス日付（YYYYMMDD） |
| openCounter | integer | - | ターミナルセッションカウンタ |
| businessCounter | integer | - | ビジネスカウンタ |
| limit | integer | - | ページネーション制限（デフォルト: 100） |
| page | integer | - | ページ番号（デフォルト: 1） |
| sort | string | - | ソート条件（形式: "field1:1,field2:-1"） |

#### テナント作成リクエスト
テナントデータベースを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| tenantId | string | ✓ | テナント識別子 |

### レスポンススキーマ

#### BaseSalesReportResponse
売上レポートレスポンス構造。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| tenantId | string | テナント識別子 |
| storeCode | string | 店舗コード |
| terminalNo | integer | ターミナル番号（店舗レベルの場合null） |
| businessDate | string | ビジネス日付（YYYYMMDD） |
| openCounter | integer | ターミナルセッションカウンタ |
| businessCounter | integer | ビジネスカウンタ |
| salesGross | SalesReportTemplate | 総売上メトリクス |
| salesNet | SalesReportTemplate | 純売上メトリクス |
| discountForLineitems | SalesReportTemplate | アイテムレベル割引 |
| discountForSubtotal | SalesReportTemplate | トランザクションレベル割引 |
| returns | SalesReportTemplate | 返品メトリクス |
| taxes | array[TaxReportTemplate] | 税金内訳 |
| payments | array[PaymentReportTemplate] | 決済内訳 |
| cash | CashBalanceReportTemplate | 現金照合 |
| receiptText | string | フォーマットされたレシートテキスト |
| journalText | string | フォーマットされたジャーナルテキスト |

#### BaseTranResponse
トランザクションデータレスポンス構造。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| tenantId | string | テナント識別子 |
| storeCode | string | 店舗コード |
| terminalNo | integer | ターミナル番号 |
| transactionNo | integer | トランザクション番号 |

#### BaseTenantCreateResponse
テナント作成レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| tenantId | string | 作成されたテナント識別子 |

## プラグインアーキテクチャ

### プラグインインターフェース
```python
class IReportPlugin(ABC):
    @abstractmethod
    async def generate_report(
        self, store_code: str, terminal_no: int, business_counter: int,
        business_date: str, open_counter: int, report_scope: str,
        report_type: str, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> dict[str, any]:
        """指定されたパラメータに基づいてレポートを生成"""
        pass
```

### プラグイン設定
プラグインは`plugins.json`で設定されます：

```json
{
    "report_makers": {
        "sales": {
            "module": "app.services.plugins.sales_report_maker",
            "class": "SalesReportMaker",
            "args": ["<tran_repository>", "<cash_in_out_log_repository>", "<open_close_log_repository>"]
        }
    }
}
```

### 売上レポートプラグイン
`SalesReportMaker`プラグインは、以下を行うための洗練されたMongoDBアグリゲーションパイプラインを実装します：

1. **トランザクションデータの集計**: 適切な要因でタイプ別にトランザクションをグループ化
   - 通常売上（101）: 要因 +1
   - 返品売上（102）: 要因 -1
   - 取消売上（201）: 要因 -1
   - 取消返品（202）: 要因 +1

2. **売上メトリクスの計算**: 総売上/純売上、割引、税金、決済を処理

3. **現金操作の統合**: トランザクションデータと現金入出金操作を結合

4. **フォーマット済み出力の生成**: 適切なフォーマットでレシートとジャーナルテキストを作成

## データ検証システム

日次レポート生成前に、サービスは包括的な検証を実行します：

### ターミナル状況検証
- すべてのターミナルが適切に閉店されている必要
- ターミナル状況をDailyInfoDocumentで追跡
- 検証により不完全な日次レポートを防止

### トランザクション数検証
- 閉店ログのトランザクション数が実際にログされたトランザクションと一致する必要
- すべてのトランザクションが確実に考慮される
- レポートでのデータ損失を防止

### 現金操作検証
- 現金操作数が期待値と一致する必要
- 現金引き出し照合の精度を検証
- 財務整合性を保証

### イベント完全性検証
- 必要なすべてのイベントタイプが存在する必要
- pub/subメッセージ配信を検証
- レポート用の完全なデータを保証

## MongoDBアグリゲーションパイプライン

### 売上レポートアグリゲーションパイプライン

サービスは売上計算のために洗練されたアグリゲーションパイプラインを使用：

1. **$match**: テナント、店舗、ターミナル、日付でフィルタリングし、キャンセルされたトランザクションを除外
2. **$project**: 割引金額を計算し、配列からネストされたデータを抽出
3. **$unwind**: 適切なグループ化のために税金と決済配列を展開
4. **$group**: 複雑な数学演算でトランザクションタイプ別に集計
5. **$sort**: 結果を順序付けし、ページネーションをサポート
6. **$facet**: 複数の集計を並列処理

### トランザクションタイプ処理
適切な計算要因で異なるトランザクションタイプを処理：
- トランザクションタイプに基づいて正/負要因を適用
- 返品と取消シナリオを正しく処理
- すべての操作で財務精度を維持

## イベント処理

### Dapr Pub/Sub統合
Dapr pub/sub経由で他のサービスからイベントを受信：

#### トランザクションログイベント（`tranlog`）
- カートサービスからの完全なトランザクションデータ
- 明細項目、決済、税金、合計を含む
- レポート集計用に処理

#### 現金ログイベント（`cashlog`）
- ターミナルサービスからの現金入出金操作
- 現金引き出し照合に使用
- 日次レポートに統合

#### 開閉ログイベント（`opencloselog`）
- ターミナルサービスからのターミナルセッションイベント
- 検証用のターミナル状態を追跡
- 日次レポート生成に必要

### 冪等処理
- 重複検出にDapr state storeを使用
- `StateStoreManager`経由のサーキットブレーカーパターン
- 信頼性のあるイベント処理を保証

## ジャーナル統合

### 自動ジャーナル提出
APIキー認証でレポートが要求された場合：
- レポートが自動的にジャーナルサービスに送信される
- 適切なトランザクションタイピング（FlashReport/DailyReport）を使用
- 生成されたすべてのレポートの監査証跡を提供
- フォーマット済みレシートとジャーナルテキストを含む

## マルチテナンシーとセキュリティ

### データベース分離
- 各テナントは個別のデータベースを使用: `db_report_{tenant_id}`
- テナント間の完全なデータ分離
- すべての操作でテナント検証

### 認証方法
- **JWTトークン**: 管理アクセスとレポート管理用
- **APIキー**: ターミナル操作と自動ジャーナル提出用
- **サービス間**: ジャーナル統合用

### データ保護
- テナント間のデータアクセスなし
- 包括的な監査証跡
- セキュアなイベント処理

## パフォーマンス考慮事項

1. **インデックス戦略**: レポートクエリとイベント処理用の最適化された複合インデックス
2. **アグリゲーション最適化**: 効率のためのパイプライン段階順序付けとインデックス使用
3. **イベント処理**: 冪等性保証付きの非同期処理
4. **キャッシュ**: アグリゲーション結果とstate storeキャッシュの戦略的使用
5. **ページネーション**: 大規模レポートデータセット用の効率的ページネーションサポート

## 検証ルール

### レポート生成検証
- フラッシュレポート: ターミナル閉店要件なし
- 日次レポート: すべてのターミナルが閉店として検証されている必要
- ビジネス日付は有効形式（YYYYMMDD）である必要
- レポートタイプは対応する登録済みプラグインを持つ必要

### イベント処理検証
- 冪等性のためイベントIDは一意である必要
- すべての金額は非負である必要
- タイムスタンプは有効なISO形式である必要
- ターミナル参照は存在し有効である必要

### データ整合性検証
- トランザクション数は異なるログタイプ間で一致する必要
- 現金計算は均衡する必要（開始額 + 操作 = 期待値）
- 完全なレポートのためにすべての必要なイベントタイプが存在する必要

この包括的なモデル仕様により、レポートサービスは拡張可能なプラグインアーキテクチャと堅牢なデータ検証メカニズムを備えた正確で信頼性の高いビジネスインテリジェンスを提供できます。