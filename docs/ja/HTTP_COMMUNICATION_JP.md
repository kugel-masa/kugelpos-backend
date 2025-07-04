# HTTP通信パターン

このドキュメントでは、Kugelposマイクロサービスアーキテクチャ全体で使用される統一されたHTTP通信パターンについて説明します。

## 概要

KugelposのすべてのHTTP通信は、専用のヘルパークラスを使用した一貫したパターンに従います：
- **HttpClientHelper**: REST API用のリトライロジックとコネクションプーリングを提供
- **DaprClientHelper**: Daprサイドカー通信用のサーキットブレーカーパターンを提供

## 通信タイプ

### 1. サービス間REST通信

すべての直接的なサービス間REST API呼び出しは`HttpClientHelper`を使用します：

```python
from kugel_common.utils.http_client_helper import get_service_client

async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items", headers={"X-API-KEY": api_key})
```

**特徴:**
- 自動リトライ（デフォルト：3回）
- コネクションプーリング
- サービスディスカバリ
- 統一されたエラーハンドリング

**使用箇所:**
- `ItemMasterWebRepository` (Cart → Master Data)
- `PaymentMasterWebRepository` (Cart → Master Data) 
- `SettingsMasterWebRepository` (Cart → Master Data)
- `TranlogWebRepository` (Terminal → Cart)
- `TerminalInfoWebRepository` (Report → Terminal)
- `StoreInfoWebRepository` (Commons → Terminal)
- `StaffMasterWebRepository` (Commons → Master Data)

### 2. Dapr通信

すべてのDaprサイドカー通信は`DaprClientHelper`を使用します：

```python
from kugel_common.utils.dapr_client_helper import get_dapr_client

async with get_dapr_client() as client:
    # Pub/Sub
    await client.publish_event("pubsub", "topic", {"message": "data"})
    
    # State Store
    await client.save_state("statestore", "key", {"value": "data"})
    data = await client.get_state("statestore", "key")
```

**特徴:**
- サーキットブレーカーパターン
- HttpClientHelper経由の自動リトライ
- Dapr API用の適切なレスポンス解析
- ノンブロッキングエラーハンドリング

**使用箇所:**
- `PubsubManager` (Cart, Terminal)
- `StateStoreManager` (Report, Journal)

## サーキットブレーカーパターン

サーキットブレーカーパターンはDaprClientHelperでカスケード障害を防ぐために実装されています：

### 状態
1. **Closed**（正常動作）
   - すべてのリクエストが通過
   - 失敗がカウントされる

2. **Open**（障害状態）
   - すべてのリクエストが即座に失敗
   - 障害サービスへの負荷なし
   - 閾値失敗後にアクティブ化

3. **Half-Open**（回復テスト）
   - 限定的なリクエストを許可
   - 成功 → Closedに戻る
   - 失敗 → Openに戻る

### 設定
- **失敗閾値**: 3回連続失敗
- **リセットタイムアウト**: 60秒
- **インスタンスごとに設定可能**

## 認証パターン

### APIキー認証
```python
headers = {"X-API-KEY": api_key}
```

### JWT Bearerトークン
```python
headers = {"Authorization": f"Bearer {token}"}
```

### 混合認証（フォールバック付き）
```python
try:
    token = create_service_token(...)
    headers = {"Authorization": f"Bearer {token}"}
except Exception:
    headers = {"X-API-KEY": api_key}  # フォールバック
```

## エラーハンドリング

### HttpClientHelper例外
- `HttpClientError`: ステータスコードとレスポンスを含む基本例外
- 一時的なエラーでの自動リトライ（サーキットブレーカーなし）

### DaprClientHelperの戻り値
- Pub/Sub: `bool`（成功/失敗）
- State Get: `Optional[Any]`（データまたはNone）
- State Save: `bool`（成功/失敗）

## ベストプラクティス

1. **常にコンテキストマネージャーを使用**
   ```python
   async with get_service_client("service") as client:
       # クライアントを使用
   ```

2. **ステート操作でのNoneレスポンスを処理**
   ```python
   data = await client.get_state("store", "key")
   if data is None:
       # キーが存在しない
   ```

3. **適切なログ記録**
   - 成功: DEBUGレベル
   - 警告: サーキットブレーカー状態変更
   - エラー: 失敗した操作とコンテキスト

4. **適切なタイムアウト設定**
   - デフォルト: 30秒
   - 操作タイプに基づいて調整

## 移行ガイド

### 直接httpxからHttpClientHelperへ
```python
# 変更前
async with httpx.AsyncClient() as client:
    response = await client.get(url, headers=headers)
    
# 変更後
async with get_service_client("service-name") as client:
    response = await client.get(endpoint, headers=headers)
```

### aiohttpからDaprClientHelperへ
```python
# 変更前 (Pub/Sub)
async with aiohttp.ClientSession() as session:
    await session.post(dapr_url, json=message)
    
# 変更後
async with get_dapr_client() as client:
    await client.publish_event(pubsub_name, topic, message)
```

## パフォーマンスの考慮事項

1. **コネクションプーリング**: 可能な限り接続を再利用
2. **サーキットブレーカー**: カスケード障害を防止（DaprClientHelperのみ）
3. **リトライロジック**: 一時的な障害を自動的に処理
4. **非同期操作**: すべての操作はノンブロッキング

## モニタリング

以下のメトリクスを監視：
- サーキットブレーカー状態変更
- リトライ回数
- レスポンスタイム
- サービス別エラー率

## 今後の拡張

1. リクエストトレーシングの実装
2. メトリクス収集の追加
3. バルク操作のサポート
4. リアルタイム通信用のWebSocketサポート