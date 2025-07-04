# Daprコンポーネント ドキュメント

このドキュメントでは、Kugelposマイクロサービスアーキテクチャで使用されているDaprコンポーネントと、各サービスがどのコンポーネントを実際に利用しているかを説明します。

## 概要

KugelposはDapr（Distributed Application Runtime）を以下の用途で使用しています：
- **状態管理**: Redisベースのステートストアによるキャッシングと状態の永続化
- **Pub/Subメッセージング**: Redisベースのpub/subによるサービス間のイベント駆動通信
- **サービスメッシュ**: サービス間通信とサービスディスカバリー

## コンポーネントディレクトリ構造

```
/services/dapr/components/
├── cartstore.yaml              # カートサービス用ステートストア
├── pubsub_cashlog_report.yaml  # 入出金イベント用pub/sub
├── pubsub_opencloselog_report.yaml  # ターミナル開閉イベント用pub/sub
├── pubsub_tranlog_report.yaml  # トランザクションログ用pub/sub
├── statestore.yaml             # 汎用ステートストア（イベント重複排除用）
└── terminalstore.yaml          # ステートストア（未使用 - 設定されているがどのサービスでも使用されていない）
```

## アクティブなステートストアコンポーネント

### 1. 汎用ステートストア (`statestore.yaml`)
- **タイプ**: `state.redis`
- **Redis DBインデックス**: 1
- **TTL**: 1時間（3600秒）
- **使用サービス**: `report`、`journal`、および`stock`サービス
- **用途**: 
  - 冪等なメッセージ処理 - 処理済みイベントIDの追跡
  - pub/subメッセージの重複処理防止
  - イベント重複排除のためのシンプルなキーバリューストレージ

```yaml
metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "3600"
  - name: databaseIndex
    value: "1"
```

### 2. カートストア (`cartstore.yaml`)
- **タイプ**: `state.redis`
- **Redis DBインデックス**: 2
- **TTL**: 10時間（36000秒）
- **使用サービス**: `cart`サービス
- **用途**: 
  - トランザクション中のカートドキュメントのキャッシング
  - MongoDBフォールバック付きサーキットブレーカーパターンの実装
  - トランザクションライフサイクル中のカート状態の保存

```yaml
metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "36000"
  - name: databaseIndex
    value: "2"
```

## Pub/Subコンポーネント

### 1. トランザクションログPub/Sub (`pubsub_tranlog_report.yaml`)
- **タイプ**: `pubsub.redis`
- **ストリーム名**: `topic-tranlog`
- **処理タイムアウト**: 180秒
- **パブリッシャー**: `cart`サービス
- **サブスクライバー**: 
  - `report`サービス（ルート: `/api/v1/tranlog`）
  - `journal`サービス（ルート: `/api/v1/tranlog`）
  - `stock`サービス（ルート: `/api/v1/tranlog`）
- **用途**: カートサービスからレポート、ジャーナル、および在庫サービスへのトランザクションログの配信

### 2. 入出金ログPub/Sub (`pubsub_cashlog_report.yaml`)
- **タイプ**: `pubsub.redis`
- **ストリーム名**: `topic-cashlog`
- **処理タイムアウト**: 180秒
- **パブリッシャー**: `terminal`サービス
- **サブスクライバー**:
  - `report`サービス（ルート: `/api/v1/cashlog`）
  - `journal`サービス（ルート: `/api/v1/cashlog`）
- **用途**: ターミナルサービスからレポートおよびジャーナルサービスへの入出金イベントの配信

### 3. 開閉ログPub/Sub (`pubsub_opencloselog_report.yaml`)
- **タイプ**: `pubsub.redis`
- **ストリーム名**: `topic-opencloselog`
- **処理タイムアウト**: 180秒
- **パブリッシャー**: `terminal`サービス
- **サブスクライバー**:
  - `report`サービス（ルート: `/api/v1/opencloselog`）
  - `journal`サービス（ルート: `/api/v1/opencloselog`）
- **用途**: ターミナルサービスからレポートおよびジャーナルサービスへのターミナル開閉イベントの配信

## サービスコンポーネント使用状況マトリクス

| サービス | ステートストア | Pub/Sub（パブリッシャー） | Pub/Sub（サブスクライバー） |
|---------|--------------|---------------------|---------------------|
| **terminal** | - | pubsub-cashlog-report<br>pubsub-opencloselog-report | - |
| **cart** | cartstore | pubsub-tranlog-report | - |
| **report** | statestore | - | pubsub-tranlog-report<br>pubsub-cashlog-report<br>pubsub-opencloselog-report |
| **journal** | statestore | - | pubsub-tranlog-report<br>pubsub-cashlog-report<br>pubsub-opencloselog-report |
| **stock** | statestore | - | pubsub-tranlog-report |

## サービス別コンポーネント使用詳細

### ターミナルサービス
- **役割**: イベントパブリッシャー
- **Pub/Subパブリッシャー**:
  - `pubsub-cashlog-report`: 入出金イベントを発行
  - `pubsub-opencloselog-report`: ターミナル開閉イベントを発行
- **プライマリストレージ**: ターミナルデータ用MongoDB

### カートサービス
- **役割**: 状態管理とイベント発行
- **ステートストア**:
  - `cartstore`: サーキットブレーカーパターンによるカートドキュメントのキャッシング
- **Pub/Subパブリッシャー**:
  - `pubsub-tranlog-report`: 完了したトランザクションログを発行
- **プライマリストレージ**: 永続化用MongoDB、キャッシング用Redis

### レポートサービス
- **役割**: 冪等処理を伴うイベントコンシューマー
- **ステートストア**:
  - `statestore`: 処理済みイベントIDの追跡（冪等性）
  - pub/subメッセージの重複処理防止
  - レジリエンスのためのサーキットブレーカーパターン
- **Pub/Subサブスクライバー**:
  - `pubsub-tranlog-report`: トランザクションログを受信
  - `pubsub-cashlog-report`: 入出金ログを受信
  - `pubsub-opencloselog-report`: ターミナル開閉ログを受信
- **プライマリストレージ**: 集計レポート用MongoDB

### ジャーナルサービス
- **役割**: 冪等処理を伴うイベントコンシューマー
- **ステートストア**:
  - `statestore`: 処理済みイベントIDの追跡（冪等性）
  - pub/subメッセージの重複処理防止
  - レジリエンスのためのサーキットブレーカーパターン
- **Pub/Subサブスクライバー**:
  - `pubsub-tranlog-report`: トランザクションログを受信
  - `pubsub-cashlog-report`: 入出金ログを受信
  - `pubsub-opencloselog-report`: ターミナル開閉ログを受信
- **プライマリストレージ**: 電子ジャーナルエントリー用MongoDB

## アーキテクチャパターン

### 1. イベント駆動アーキテクチャ
- **プロデューサー**: `cart`と`terminal`サービスがビジネスイベントを生成
- **コンシューマー**: `report`、`journal`、および`stock`サービスが非同期でイベントを処理
- **メリット**: 疎結合、スケーラビリティ、耐障害性

### 2. サーキットブレーカーパターン
- **実装**: 
  - カートサービス：`cartstore`でキャッシング用
  - レポート/ジャーナル/在庫サービス：`statestore`で冪等性用
- **動作**: ステートストアが利用不可の場合、自動的にフォールバックまたは処理を継続
- **メリット**: レジリエンス、グレースフルデグラデーション

### 3. ファンアウトメッセージング
- **パターン**: 1つのパブリッシャー、複数のサブスクライバー
- **例**: トランザクションログを一度発行し、レポートとジャーナルの両方が消費
- **メリット**: 効率的なイベント配信、独立したスケーリング

### 4. ステートストアの分離
- **設計**: 各サービスが独自のRedisデータベースインデックスを持つ
- **メリット**: データ分離、独立したTTL管理、キーの競合なし

### 5. 冪等なメッセージ処理
- **実装**: レポート、ジャーナル、および在庫サービスが処理済みイベントIDを追跡
- **メカニズム**: 処理前にステートストアをチェック、成功後にイベントIDを保存
- **メリット**: 正確に一度だけの処理セマンティクス、リトライへの耐性

## 設定に関する注意事項

1. **Redis接続**: すべてのコンポーネントが`redis:6379`を使用（Docker Composeサービス名）
2. **処理タイムアウト**: すべてのpub/subコンポーネントが180秒のタイムアウトを使用
3. **TTL設定**: 
   - 汎用ステートストア: 1時間（イベント重複排除用）
   - カートストア: 10時間（アクティブセッション用の長期保存）
4. **アクターサポート**: すべてのステートストアで`actorStateStore: false`（Daprアクターは未使用）

## イベントフロー図

```
┌─────────────┐                     ┌─────────────┐
│  Terminal   │                     │    Cart     │
│  サービス    │                     │  サービス    │
└─────┬───────┘                     └─────┬───────┘
      │                                   │
      │ 発行                              │ 発行
      ├─► pubsub-cashlog-report          │
      │                                   │
      └─► pubsub-opencloselog-report     └─► pubsub-tranlog-report
           │                                   │
           │                                   │
           ├──────────────┬────────────────────┤
           │              │                    │
           ▼              ▼                    ▼
    ┌─────────────┐ ┌─────────────┐    ┌─────────────┐
    │   Report    │ │   Report    │    │   Report    │
    │  サービス    │ │  サービス    │    │  サービス    │
    └─────────────┘ └─────────────┘    └─────────────┘
           │              │                    │
           ▼              ▼                    ▼
    ┌─────────────┐ ┌─────────────┐    ┌─────────────┐
    │  Journal    │ │  Journal    │    │  Journal    │
    │  サービス    │ │  サービス    │    │  サービス    │
    └─────────────┘ └─────────────┘    └─────────────┘
```

### 在庫サービス
- **役割**: 冪等処理を伴うイベントコンシューマー
- **ステートストア**:
  - `statestore`: 処理済みイベントIDの追跡（冪等性）
  - pub/subメッセージの重複処理防止
  - レジリエンスのためのサーキットブレーカーパターン
- **Pub/Subサブスクライバー**:
  - `pubsub-tranlog-report`: 在庫更新用のトランザクションログを受信
- **プライマリストレージ**: 在庫データ用MongoDB
- **WebSocket機能**: 在庫アラートと再注文ポイント通知はDaprとは独立して動作

## 実装に関する注意事項

1. **未使用コンポーネント**: `terminalstore.yaml`は設定されているがどのサービスでも使用されていない
2. **カートサービスパターン**: `DaprClientHelper`ではなく、レガシーなDapr state APIへの直接HTTP呼び出しを使用
3. **在庫WebSocket機能**: リアルタイム在庫アラートは追加のDaprコンポーネントなしで独立して動作
4. **データベースインデックス**: 分離のためにcartstore(2)、statestore(1)、terminalstore(3)を使用