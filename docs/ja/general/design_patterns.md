# Kugelpos デザインパターン仕様

## 概要

Kugelposシステムでは、保守性、拡張性、テスタビリティを向上させるために、以下の主要デザインパターンを実装しています。各パターンは実際のビジネス要件に基づいて設計され、具体的な実装コードとして確認できます。

## 実装されたデザインパターン

### 1. ステートマシンパターン（Cart Service）

**実装場所:** `/services/cart/app/services/cart_state_manager.py`

**目的:** カートのライフサイクル管理と不正操作の防止

**状態遷移:**
```
initial → idle → entering_item → paying → completed
               ↘               ↗        ↘ cancelled
```

**主要クラス:**
- `CartStateManager`: 状態遷移の制御
- `AbstractState`: 全状態の基底クラス
- 具体状態: `InitialState`, `IdleState`, `EnteringItemState`, `PayingState`, `CompletedState`, `CancelledState`

**特徴:**
- 各状態で許可される操作を明確に定義
- 状態に応じたビジネスルールの適用
- 無効な状態遷移の防止

### 2. プラグインアーキテクチャ

**実装場所:**
- Cart Service: `/services/cart/app/services/strategies/`
- Report Service: `/services/report/app/services/plugins/`

**プラグイン設定:** `plugins.json`
```json
{
    "payment_strategies": [
        {
            "module": "app.services.strategies.payments.cash",
            "class": "PaymentByCash",
            "args": ["01"]
        }
    ]
}
```

**主要機能:**
- 動的プラグインロード（importlib使用）
- 支払い戦略の実行時切り替え
- 販売促進ルールのプラグイン化
- レポート生成器のカスタマイズ

**プラグインマネージャー:** `CartStrategyManager`
- JSON設定からプラグインを動的ロード
- 実行時戦略選択と実行

### 3. リポジトリパターン

**実装場所:** `/services/commons/src/kugel_common/models/repositories/abstract_repository.py`

**基底クラス:** `AbstractRepository[Tdocument]`
- ジェネリック型サポート
- CRUD操作の標準化
- 楽観的ロック with リトライ
- ページネーション対応
- トランザクション管理

**主要メソッド:**
```python
async def create_async(self, document: Tdocument) -> bool
async def get_one_async(self, filter: dict) -> Tdocument
async def update_one_async(self, filter: dict, new_values: dict) -> bool
async def find_with_pagination_async(...) -> Tuple[List[Tdocument], int]
```

**特徴:**
- データアクセス層の抽象化
- ビジネスロジックとDB操作の分離
- 統一されたエラーハンドリング

### 4. サーキットブレーカーパターン

**実装場所:**
- `HttpClientHelper`: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- `DaprClientHelper`: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`

**設定:**
- 失敗閾値: 3回連続失敗
- 回復タイムアウト: 60秒
- 状態: CLOSED → OPEN → HALF_OPEN

**対象操作:**
- 外部HTTPサービス呼び出し
- Dapr pub/sub操作
- Daprステートストア操作

**統一エラーハンドリング:**
- 自動リトライ（3回、指数バックオフ）
- カスケード障害の防止
- 高速フェイル機能

### 5. ストラテジーパターン

**実装場所:**
- 支払い戦略: `/services/cart/app/services/strategies/payments/`
- 税計算: `/services/cart/app/services/logics/calc_tax_logic.py`

**抽象戦略:** `AbstractPayment`
```python
async def pay(self, cart_doc, payment_code, amount, detail)
async def refund(self, cart_doc, payment_index)
async def cancel(self, cart_doc, payment_index)
```

**具体戦略:**
- `PaymentByCash`: 現金支払い（お釣り計算）
- `PaymentByCashless`: キャッシュレス支払い（過払いチェック）

**税計算戦略:**
- 外税計算: 税額を価格に加算
- 内税計算: 税額が価格に含まれる
- 非課税: 税額なし

### 6. ファクトリーパターン

**実装場所:** `CartStrategyManager`

**機能:**
- 支払いコードに基づく戦略インスタンス生成
- プロモーションタイプによるインスタンス作成
- 設定ファイル駆動の動的オブジェクト生成

### 7. テンプレートメソッドパターン

**実装場所:** `AbstractState`

**処理フロー:**
1. イベント許可チェック
2. 前処理
3. メイン処理（サブクラス実装）
4. 後処理

## 統一通信アーキテクチャ

### HttpClientHelper

**機能:**
- 自動リトライメカニズム
- コネクションプーリング
- サーキットブレーカー組み込み
- サービスディスカバリサポート

**使用例:**
```python
async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items")
```

### DaprClientHelper

**機能:**
- Dapr操作の統一インターフェース
- pub/subとステートストアの統合
- サーキットブレーカー保護
- ノンブロッキングエラーハンドリング

**使用例:**
```python
async with get_dapr_client() as client:
    await client.publish_event("pubsub", "topic", data)
```

## パターンの組み合わせ効果

### 相乗効果

1. **ステートマシン + ストラテジー**
   - 状態に応じた支払い戦略の選択
   - ビジネスルールの明確な分離

2. **リポジトリ + サーキットブレーカー**
   - データアクセスの高い信頼性
   - 障害時の適切なフェイルオーバー

3. **プラグイン + ファクトリー**
   - 実行時の動的機能拡張
   - 設定駆動のカスタマイズ

### 保守性向上

- **単一責任の原則**: 各パターンが明確な責務を持つ
- **開放閉鎖の原則**: 拡張に開放、修正に閉鎖
- **依存性の逆転**: 抽象に依存、具象に依存しない

### テスタビリティ

- **モック可能性**: 各インターフェースのモック実装
- **独立性**: パターンごとの分離されたテスト
- **ステートテスト**: 状態遷移の網羅的テスト

## 実装における重要な考慮事項

### パフォーマンス最適化

- **非同期処理**: 全パターンでasyncio活用
- **リソース管理**: 適切なリソースクリーンアップ
- **キャッシング**: 戦略インスタンスの再利用

### エラーハンドリング

- **統一例外体系**: カスタム例外クラスの活用
- **グレースフルデグラデーション**: 部分的障害時の継続動作
- **ログ統合**: 構造化ログによる追跡性

### 設定管理

- **外部設定**: JSON/YAML設定ファイル
- **環境変数**: 実行時パラメータ調整
- **デフォルト値**: 設定なしでの動作保証

このデザインパターンの組み合わせにより、Kugelposは複雑なPOSビジネス要件に対して、保守性と拡張性を兼ね備えたソリューションを提供しています。