# 設定優先順位ガイド

このドキュメントでは、Kugelposにおける設定の優先順位、特にデータベース接続文字列やその他の環境変数の優先順位について説明します。

## 概要

Kugelposは階層的な設定システムを使用しており、設定を複数の場所で定義できます。同じ設定が複数の場所で定義されている場合、システムは特定の優先順位に従って使用する値を決定します。

## 設定の優先順位（高い順）

### 1. 環境変数（最高優先度）
実行時に設定された環境変数は常に最高の優先度を持ちます。これらは複数の方法で設定できます：

#### a. Docker Compose Override (docker-compose.override.yaml)
```yaml
services:
  cart:
    environment:
      - MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0
      - DB_NAME_PREFIX=db_cart
```

#### b. Docker Compose Base (docker-compose.yaml)
```yaml
services:
  cart:
    environment:
      - BASE_URL_MASTER_DATA=http://localhost:3500/v1.0/invoke/master-data/method/api/v1
```

#### c. システム環境変数
```bash
export MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
./start.sh
```

### 2. .envファイル（中優先度）
各サービスは独自の`.env`ファイルをディレクトリに持つことができます：
```bash
services/cart/.env
services/account/.env
services/terminal/.env
# など
```

`.env`ファイルの内容例：
```env
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0
DB_NAME_PREFIX=db_cart
TOKEN_URL=http://localhost:8000/api/v1/accounts/token
```

**注意**: バージョン0.0.206以降、`.env`ファイルは省略可能です。docker-compose.yamlの`env_file`設定には`required: false`が含まれています。

### 3. サービス固有の設定（低優先度）
各サービスは`app/config/settings.py`でデフォルト値を持つ独自の設定を定義します：

```python
class Settings(
    AppSettings,
    DBSettings, 
    DBCollectionCommonSettings,
    # ... その他の設定
):
    # 必須フィールドをデフォルト値でオーバーライド
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,  # .envファイルの空の値を無視
        extra="allow",
    )
```

### 4. 共通設定のデフォルト（最低優先度）
共有の`kugel_common`ライブラリが基本のデフォルト値を提供します：

```python
# kugel_common/config/settings_database.py
class DBSettings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017/?replicaSet=rs0"
    DB_NAME_PREFIX: str = "db_common"
    # ... その他のデフォルト
```

## 実用例

### 例1: MongoDB URI の解決
cartサービスの場合、`MONGODB_URI`は以下の場所で定義される可能性があります：

1. **docker-compose.override.yaml**: `mongodb://mongodb:27017/?replicaSet=rs0` ✅ (使用される)
2. **services/cart/.env**: `mongodb://localhost:27017/?replicaSet=rs0` (無視される)
3. **services/cart/app/config/settings.py**: `mongodb://localhost:27017/?replicaSet=rs0` (無視される)
4. **kugel_common/config/settings_database.py**: `mongodb://localhost:27017/?replicaSet=rs0` (無視される)

### 例2: カスタム設定
テスト用にカスタムMongoDB URIが必要な場合：

```bash
# 方法1: 環境変数（最高優先度）
MONGODB_URI=mongodb://test-server:27017/?replicaSet=rs0 docker-compose up cart

# 方法2: .envファイルを作成（中優先度）
echo "MONGODB_URI=mongodb://test-server:27017/?replicaSet=rs0" > services/cart/.env
docker-compose up cart
```

## 設定場所のまとめ

| 設定タイプ | 場所 | 優先度 | 必須 |
|-----------|------|--------|------|
| ランタイム環境 | OS環境変数 | 最高 | いいえ |
| Docker Override | docker-compose.override.yaml | 高 | いいえ |
| Docker Base | docker-compose.yaml | 高 | いいえ |
| サービス .env | services/{service}/.env | 中 | いいえ |
| サービスデフォルト | services/{service}/app/config/settings.py | 低 | はい |
| 共通デフォルト | kugel_common/config/settings_database.py | 最低 | はい |

## 主要な設定

### データベース設定
- `MONGODB_URI`: MongoDB接続文字列
- `DB_NAME_PREFIX`: データベース名のプレフィックス（例: "db_cart", "db_account"）
- `DB_MAX_POOL_SIZE`: 最大接続プールサイズ（デフォルト: 100）
- `DB_MIN_POOL_SIZE`: 最小接続プールサイズ（デフォルト: 10）

### サービスURL
- `BASE_URL_MASTER_DATA`: マスターデータサービスURL
- `BASE_URL_TERMINAL`: ターミナルサービスURL
- `BASE_URL_CART`: カートサービスURL
- `BASE_URL_REPORT`: レポートサービスURL
- `BASE_URL_JOURNAL`: ジャーナルサービスURL
- `TOKEN_URL`: 認証トークンエンドポイントURL

### 認証設定
- `SECRET_KEY`: JWT秘密鍵（デフォルト: "1234567890" - 本番環境では変更してください！）
- `ALGORITHM`: JWTアルゴリズム（デフォルト: "HS256"）
- `TOKEN_EXPIRE_MINUTES`: トークン有効期限（デフォルト: 30分）

## ベストプラクティス

1. **本番環境**: 機密データには環境変数またはDockerシークレットを使用
2. **開発環境**: 利便性のため`.env`ファイルを使用
3. **テスト**: 一貫したテスト環境のためdocker-compose.override.yamlを使用
4. **デフォルト**: サービスのデフォルトが開発環境で安全かつ機能的であることを確認

## トラブルシューティング

### 使用されている設定を確認する方法：

1. **実行中のコンテナで環境変数を確認:**
```bash
docker-compose exec cart env | grep MONGODB_URI
```

2. **起動時のログを確認:**
```bash
docker-compose logs cart | grep "Connected to MongoDB"
```

3. **設定の読み込みをデバッグ:**
```python
# サービスコードに一時的に追加
from app.config.settings import settings
print(f"MONGODB_URI: {settings.MONGODB_URI}")
print(f"DB_NAME_PREFIX: {settings.DB_NAME_PREFIX}")
```

## バージョン履歴

- **v0.0.206**: `.env`ファイルを省略可能にし、全サービスに`env_ignore_empty=True`を追加
- **v0.0.205**: kugel_common DBSettingsにデフォルト値を追加
- **以前のバージョン**: 各サービスに`.env`ファイルが必須