# Kugelpos - POSバックエンドサービス

## 概要
Kugelposは小売業向けの包括的なPOS（Point of Sale）バックエンドサービスです。複数のマイクロサービスで構成され、スケーラブルで柔軟なアーキテクチャを特徴としています。

## 機能とコンポーネント
- **Account Service**: ユーザー管理と認証
- **Terminal Service**: 端末と店舗の管理
- **Cart Service**: 商品登録と取引処理
- **Master-data Service**: マスターデータ管理
- **Report Service**: 売上レポート生成
- **Journal Service**: 電子ジャーナル検索
- **Stock Service**: 在庫管理

## アーキテクチャ
![Architecture Diagram](docs/diagrams/azure_architecture_diagram.svg)

## 前提条件

前提となるツール群の詳細なインストール手順については、以下を参照してください：
- 📚 [インストールガイド（英語）](install/install_doc.md)
- 🇯🇵 [インストールガイド（日本語）](install/install_doc_ja.md)

必要なツール：
- Docker と Docker Compose
- Python 3.12以上
- pipenv（Python依存関係管理用）
- MongoDB 7.0+（Dockerで自動的に提供）
- Redis（Dockerで自動的に提供）

## クイックスタート

### 1. ローカルにコピー
```bash
git clone https://github.com/kugel-masa/kugelpos-backend.git
cd kugelpos-backend
```

### 2. クイックスタートスクリプトの実行
```bash
# まず、スクリプトに実行権限を付与します
chmod +x quick_start.sh

# 次にスクリプトを実行します。以下の手順を自動的に処理します：
# - Python環境の構築
# - Dockerイメージのビルド
# - 全サービスの起動
./quick_start.sh
```

### 3. サービスへのアクセス
- Account API: http://localhost:8000/docs
- Terminal API: http://localhost:8001/docs
- Master Data API: http://localhost:8002/docs
- Cart API: http://localhost:8003/docs
- Report API: http://localhost:8004/docs
- Journal API: http://localhost:8005/docs
- Stock API: http://localhost:8006/docs

### 4. テストの実行（任意）
```bash
# 全サービスの一括テスト実行
./scripts/run_all_tests_with_progress.sh
```

### 5. サービスの停止
```bash
# 全サービスの停止
./scripts/stop.sh

# データも含めて完全にクリーンアップする場合
./scripts/stop.sh --clean
```

## 手動セットアップ（代替方法）

セットアップ手順を手動で実行したい場合：

### 1. 環境設定

#### 環境変数（開発環境では任意）
サービスには開発用のデフォルト値が含まれていますが、カスタマイズすることも可能です：

- `SECRET_KEY`: JWT署名用の秘密鍵（デフォルト: "test-secret-key-for-development-only"）
- `PUBSUB_NOTIFY_API_KEY`: Pub/Sub通知用のAPIキー（デフォルト値あり）

⚠️ **重要**: 本番環境では、これらの値を変更してください！

```bash
# 任意：開発用のカスタム環境変数を設定
export SECRET_KEY="your-secure-secret-key-here"
export PUBSUB_NOTIFY_API_KEY="your-api-key-here"

# テスト用の.env.testファイルを準備してください（テナントIDのみ変更）
cp .env.test.sample .env.test
```

### 2. スクリプトの準備
```bash
# 全てのスクリプトファイルに実行権限を付与
chmod +x ./scripts/make_scripts_executable.sh
./scripts/make_scripts_executable.sh
```

### 3. 開発環境の準備
```bash
# Python仮想環境の構築
./scripts/rebuild_pipenv.sh
```

### 4. サービスの構築と起動
```bash
# 全サービスのビルド実行
./scripts/build.sh

# 全サービスの起動
./scripts/start.sh
```

### 補足: ビルドオプション
```bash
# 特定のサービスのみビルド
./scripts/build.sh cart journal

# キャッシュを使わずにビルド
./scripts/build.sh --no-cache

# 並列ビルド
./scripts/build.sh --parallel
```


## 開発

### Dockerを使わないローカル開発

各サービスは開発用にローカルで実行できます：

```bash
# servicesディレクトリに移動
cd services

# インフラストラクチャサービスのみを起動
docker-compose up -d mongodb redis

# 特定のサービスをローカルで実行（例：cartサービス）
cd cart
pipenv install

# 方法1: run.pyスクリプトを使用（最も簡単）
pipenv run python run.py

# 方法2: uvicornを直接使用（リロード付き開発用）
pipenv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
```

サービスポートマッピング：
- account: ポート 8000
- terminal: ポート 8001
- master-data: ポート 8002
- cart: ポート 8003
- report: ポート 8004
- journal: ポート 8005
- stock: ポート 8006

### ユーティリティスクリプト

#### スクリプトの実行権限設定
プロジェクトをクローンまたはコピーした際、シェルスクリプトの実行権限を復元する必要がある場合があります：

```bash
# プロジェクト全体の.shファイルを実行可能にする（デフォルト）
./scripts/make_scripts_executable.sh

# 特定のディレクトリ内の全ての.shファイルを実行可能にする
./scripts/make_scripts_executable.sh /path/to/directory

# 詳細モード - 変更されたファイルのリストを表示
./scripts/make_scripts_executable.sh . -v
```

このスクリプトはプロジェクト内の全ての.shファイルを検索し、実行可能にします：
- `/scripts` ディレクトリ内のスクリプト
- `/services/*/run_all_tests.sh` のサービステストスクリプト
- その他のサブディレクトリ内の全ての.shファイル

### ディレクトリ構造
```
kugelpos/
├── services/
│   ├── account/    # アカウント管理サービス
│   ├── terminal/   # 端末管理サービス
│   ├── cart/       # カート・取引処理サービス
│   ├── master-data/# マスターデータサービス
│   ├── report/     # レポート生成サービス
│   ├── journal/    # 電子ジャーナルサービス
│   ├── stock/      # 在庫管理サービス
│   ├── commons/    # 共通ライブラリ
│   └── dapr/       # Daprコンポーネント設定ファイル
├── scripts/        # ユーティリティスクリプト
└── docs/           # ドキュメント
```

### 処理フロー概要

以下の順でAPIを呼び出して処理を行います：

1. **Account Service**
   - スーパーユーザー登録
   - ログイン（トークン取得）
   - 必要に応じて追加ユーザー登録

2. **Terminal Service**
   - テナント情報登録
   - 店舗登録
   - 端末登録

3. **Master-data Service**
   - スタッフマスター登録
   - 支払い方法マスター登録
   - カテゴリマスター登録
   - 共通商品マスター登録
   - 店舗別商品マスター登録
   - 商品プリセットマスター登録

4. **Cart Service**（Terminal IDとAPI KEYを指定）
   - サインイン
   - 端末オープン
   - カート作成（取引開始）
   - 商品登録と修正
   - 小計処理
   - 支払い登録
   - 取引確定
   - レポート取得
   - 電子ジャーナル検索
   - 端末クローズ
   - サインアウト

5. **Report Service**
   - 速報売上レポート生成
   - 日次売上レポート生成

6. **Journal Service**
   - 取引ジャーナル検索

## ライセンス
Apache License 2.0
