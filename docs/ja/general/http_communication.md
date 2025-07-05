# Kugelpos HTTP通信仕様

## 概要

Kugelposシステムでは、統一されたHTTP通信パターンを採用し、高い信頼性とパフォーマンスを実現しています。サーキットブレーカーパターンと自動リトライメカニズムにより、堅牢なサービス間通信を提供します。

## 統一HTTP通信アーキテクチャ

### HttpClientHelper

**実装場所:** `/services/commons/src/kugel_common/utils/http_client_helper.py`

**主要機能:**
- 自動リトライメカニズム（3回、指数バックオフ）
- サーキットブレーカーパターン（3回失敗で60秒ブロック）
- コネクションプーリング（最大100接続、Keep-Alive 20接続）
- サービスディスカバリサポート
- 統一エラーハンドリング

**設定:**
```python
httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
)
```

### 使用例

```python
# サービス間通信
async with get_service_client("master-data") as client:
    response = await client.get("/api/v1/items", headers={"X-API-KEY": api_key})

# マニュアル設定
client = HttpClientHelper("master-data")
response = await client.get("/api/v1/products/123")
await client.close()
```

## サービス間通信パターン

### 認証メカニズム

#### 1. JWT Bearer Token認証
```python
headers = {"Authorization": f"Bearer {jwt_token}"}
```

#### 2. API Key認証
```python
headers = {"X-API-Key": terminal_api_key}
```

### サービスディスカバリ

**環境変数ベース:**
```python
MASTER_DATA_SERVICE_URL=http://master-data:8002
CART_SERVICE_URL=http://cart:8003
```

**Docker Compose環境:**
- サービス名による自動解決
- 内部ネットワークでの通信

## エラーハンドリング

### 統一例外体系

**HttpClientError:**
```python
class HttpClientError(Exception):
    def __init__(self, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
```

### リトライ対象エラー

- **5xx Server Errors**: すべてリトライ対象
- **タイムアウト**: 接続・読み取りタイムアウト
- **接続エラー**: ネットワーク障害

### 非リトライ対象エラー

- **4xx Client Errors**: 即座に失敗
- **認証エラー**: 401, 403
- **リソース不存在**: 404

## サーキットブレーカー実装

### 状態管理

```python
class CircuitState(Enum):
    CLOSED = "closed"      # 正常状態
    OPEN = "open"          # 遮断状態
    HALF_OPEN = "half_open" # 回復試行状態
```

### 動作フロー

1. **CLOSED → OPEN**: 3回連続失敗で遮断
2. **OPEN → HALF_OPEN**: 60秒後に回復試行
3. **HALF_OPEN → CLOSED**: 成功で正常復旧
4. **HALF_OPEN → OPEN**: 失敗で再度遮断

## パフォーマンス最適化

### 接続プーリング

- **最大接続数**: 100
- **Keep-Alive接続**: 20
- **接続再利用**: 自動管理

### タイムアウト設定

- **接続タイムアウト**: 30秒
- **読み取りタイムアウト**: 30秒
- **書き込みタイムアウト**: 30秒

### 非同期処理

- **asyncio基盤**: 全ての通信が非同期
- **並列リクエスト**: 複数サービス同時呼び出し
- **ノンブロッキングI/O**: 高いスループット

## 監視・ログ

### メトリクス

- **リクエスト数**: サービス別・エンドポイント別
- **レスポンス時間**: 平均・95パーセンタイル
- **エラー率**: 4xx/5xx別
- **サーキットブレーカー状態**: OPEN/CLOSED

### ログ出力

```python
logger.info(f"HTTP {method} {url} - {status_code} ({duration}ms)")
logger.warning(f"Circuit breaker opened for {service_name}")
logger.error(f"HTTP request failed: {error}")
```

## 設定管理

### 環境変数

```bash
# サービスURL
MASTER_DATA_SERVICE_URL=http://master-data:8002
CART_SERVICE_URL=http://cart:8003

# タイムアウト設定
HTTP_TIMEOUT=30
CIRCUIT_BREAKER_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT=60
```

### デフォルト設定

```python
class HttpClientSettings:
    timeout: int = 30
    max_connections: int = 100
    max_keepalive: int = 20
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout: int = 60
    retry_attempts: int = 3
```

## セキュリティ考慮事項

### HTTPS通信

- **本番環境**: 必須
- **開発環境**: HTTP許可
- **証明書検証**: 本番環境で有効

### ヘッダーセキュリティ

```python
default_headers = {
    "User-Agent": "kugelpos-client/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json"
}
```

### 機密情報保護

- **APIキー**: ヘッダーでの送信
- **JWTトークン**: Bearer形式
- **ログマスキング**: 機密情報の自動マスク

## トラブルシューティング

### よくあるエラー

| エラー | 原因 | 対処 |
|--------|------|------|
| Connection refused | サービス停止 | サービス起動確認 |
| Circuit breaker open | 連続失敗 | サービス正常化待ち |
| Timeout | レスポンス遅延 | タイムアウト値調整 |
| 401 Unauthorized | 認証失敗 | トークン・APIキー確認 |

### デバッグ方法

```python
# ログレベル設定
logging.getLogger("httpx").setLevel(logging.DEBUG)

# リクエスト詳細表示
client = HttpClientHelper("service", debug=True)
```

## 今後の拡張予定

### 負荷分散

- **ラウンドロビン**: 複数インスタンス対応
- **ヘルスチェック**: 不健全インスタンス除外

### キャッシング

- **レスポンスキャッシュ**: GET リクエスト
- **ETags**: 条件付きリクエスト

### 圧縮

- **gzip**: レスポンス圧縮
- **brotli**: 高効率圧縮

この統一HTTP通信アーキテクチャにより、Kugelposは高い信頼性とパフォーマンスを持つサービス間通信を実現しています。