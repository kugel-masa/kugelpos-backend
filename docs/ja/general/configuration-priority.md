# Kugelpos 設定優先順位仕様

## 概要

Kugelposシステムでは、柔軟な設定管理を実現するため、複数の設定ソースから値を読み込み、明確な優先順位に基づいて最終的な設定値を決定します。

## 設定読み込み優先順位（高→低）

### 1. 環境変数（最高優先度）

**Docker Compose override設定:**
```yaml
# docker-compose.override.yaml
services:
  cart:
    environment:
      - MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
      - DB_NAME_PREFIX=db_cart_dev
```

**システム環境変数:**
```bash
export MONGODB_URI="mongodb://production:27017/?replicaSet=rs0"
export JWT_SECRET_KEY="production-secret-key"
```

### 2. .envファイル（中優先度）

**サービス固有設定:**
```bash
# /services/cart/.env
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart
DAPR_HTTP_PORT=3500
JWT_SECRET_KEY=your-secret-key
```

### 3. 設定クラスのデフォルト値（低優先度）

**実装例:**
```python
# /services/cart/app/config/settings.py
class Settings(AppSettings, DBSettings):
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")
    DAPR_HTTP_PORT: int = Field(default=3500)
```

### 4. 共通設定（最低優先度）

**kugel_common基底設定:**
```python
# /services/commons/src/kugel_common/config/base_settings.py
class BaseSettings:
    LOG_LEVEL: str = Field(default="INFO")
    HTTP_TIMEOUT: int = Field(default=30)
```

## v0.0.206以降の重要変更

### .envファイルのオプション化

**変更前:** .envファイルが必須
**変更後:** .envファイルなしでもサービス起動可能

**フォールバック順序:**
1. 環境変数（docker-compose.override.yaml）
2. 環境変数（docker-compose.yaml）
3. .envファイル（存在する場合）
4. 設定クラスのデフォルト値

## サービス別設定例

### Cart Service設定

```python
class CartSettings(AppSettings, DBSettings):
    # MongoDB設定
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")
    
    # Dapr設定
    DAPR_HTTP_PORT: int = Field(default=3500)
    
    # サービス固有設定
    CART_TTL_SECONDS: int = Field(default=36000)  # 10時間
    MAX_ITEMS_PER_CART: int = Field(default=100)
```

**優先度適用例:**
```bash
# 環境変数で上書き
export DB_NAME_PREFIX="db_cart_test"
export CART_TTL_SECONDS="7200"  # 2時間に変更

# 結果: test環境用の設定値が適用される
```

### Terminal Service設定

```python
class TerminalSettings(AppSettings, DBSettings):
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_terminal")
    
    # APIキー設定
    API_KEY_LENGTH: int = Field(default=32)
    API_KEY_EXPIRY_DAYS: int = Field(default=365)
```

## 設定検証とエラーハンドリング

### Pydantic設定検証

```python
class Settings(BaseSettings):
    @validator('MONGODB_URI')
    def validate_mongodb_uri(cls, v):
        if not v.startswith('mongodb://'):
            raise ValueError('MONGODB_URI must start with mongodb://')
        return v
    
    @validator('JWT_SECRET_KEY')
    def validate_jwt_secret(cls, v):
        if len(v) < 32:
            raise ValueError('JWT_SECRET_KEY must be at least 32 characters')
        return v
```

### 設定読み込みエラー

```python
try:
    settings = Settings()
except ValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
    raise ConfigurationException("Invalid configuration")
```

## 開発・テスト・本番環境対応

### 開発環境

```yaml
# docker-compose.override.yaml
services:
  cart:
    environment:
      - LOG_LEVEL=DEBUG
      - DB_NAME_PREFIX=db_cart_dev
      - ENABLE_CORS=true
```

### テスト環境

```bash
# .env.test
MONGODB_URI=mongodb://test-mongo:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart_test
LOG_LEVEL=WARNING
```

### 本番環境

```bash
# 環境変数で機密情報を設定
export MONGODB_URI="${MONGODB_CONNECTION_STRING}"
export JWT_SECRET_KEY="${JWT_SECRET_FROM_VAULT}"
export LOG_LEVEL="ERROR"
```

## 設定管理のベストプラクティス

### 1. 機密情報の管理

```python
# 機密情報は環境変数のみ
JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
DATABASE_PASSWORD: str = Field(..., env="DB_PASSWORD")

# .envファイルには含めない
# docker-compose.override.yamlでも避ける
```

### 2. 環境別設定の分離

```python
class EnvironmentSettings:
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
```

### 3. 設定値の検証

```python
@validator('DAPR_HTTP_PORT')
def validate_port(cls, v):
    if not 1024 <= v <= 65535:
        raise ValueError('Port must be between 1024 and 65535')
    return v
```

## トラブルシューティング

### よくある設定問題

| 問題 | 原因 | 対処 |
|------|------|------|
| Service startup fails | 必須設定の欠如 | 環境変数を確認 |
| Wrong database connection | 設定優先度の誤解 | 優先順位を再確認 |
| CORS errors | 開発環境設定の不備 | ENABLE_CORS=true設定 |

### 設定デバッグ

```python
# 現在の設定値を表示
settings = Settings()
logger.info(f"Current settings: {settings.dict()}")

# 設定ソースの確認
logger.info(f"MongoDB URI source: {settings.__fields__['MONGODB_URI'].field_info}")
```

## 設定例テンプレート

### 最小限の.env設定

```bash
# 基本的なサービス設定
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_service_name
LOG_LEVEL=INFO
```

### 完全な開発環境設定

```bash
# 開発環境用詳細設定
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart_dev
DAPR_HTTP_PORT=3500
LOG_LEVEL=DEBUG
ENABLE_CORS=true
JWT_SECRET_KEY=development-secret-key-32chars
HTTP_TIMEOUT=30
CIRCUIT_BREAKER_THRESHOLD=3
```

この設定優先順位システムにより、Kugelposは開発・テスト・本番環境での柔軟な設定管理を実現しています。