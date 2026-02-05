---
description: サービスのビルドを実行
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/build [OPTIONS] [SERVICES...]`

**Examples:**
- `/build` → 全サービスをビルド
- `/build cart journal` → 特定サービスのみビルド
- `/build --with-common` → 共通パッケージ + 全サービス
- `/build --common-only` → 共通パッケージのみ
- `/build --no-cache` → キャッシュなしでビルド
- `/build --parallel` → 並列ビルド

## Build Options

| オプション | 説明 |
|-----------|------|
| `--with-common` | 共通パッケージをビルド後、全サービスをビルド |
| `--common-only` | 共通パッケージのみビルド（サービスはビルドしない） |
| `--no-cache` | Dockerキャッシュを使わずにビルド |
| `--parallel` | 並列でビルド（高速だがログが混在） |
| `--increment-version` | 共通パッケージのバージョンをインクリメント |

## Available Services

| Service | Port | Description |
|---------|------|-------------|
| account | 8000 | User authentication |
| terminal | 8001 | Terminal management |
| master-data | 8002 | Product catalog |
| cart | 8003 | Shopping cart |
| report | 8004 | Sales reports |
| journal | 8005 | Transaction log |
| stock | 8006 | Inventory |

## Build Commands

### 1. 全サービスビルド（Docker）
```bash
cd scripts && ./build.sh
```

### 2. 特定サービスのみビルド
```bash
cd scripts && ./build.sh cart journal
```

### 3. 共通パッケージ + 全サービス
```bash
# 共通パッケージをビルド＆配布し、pipenv環境を再構築
./scripts/update_common_and_rebuild.sh

# その後、Dockerイメージをビルド
cd scripts && ./build.sh
```

### 4. 共通パッケージのみ
```bash
# ビルドのみ
./scripts/run_build_common.sh

# ビルド＆全サービスに配布
./scripts/run_build_common.sh && ./scripts/run_copy_common.sh
```

### 5. バージョンインクリメント付きビルド
```bash
./scripts/update_common_and_rebuild.sh --increment-version
```

### 6. キャッシュなし / 並列ビルド
```bash
cd scripts && ./build.sh --no-cache
cd scripts && ./build.sh --parallel
cd scripts && ./build.sh --no-cache --parallel cart report
```

## Typical Workflows

### 開発中（コード変更後）
```bash
# 特定サービスのみ再ビルド
cd scripts && ./build.sh cart
```

### 共通パッケージ変更後
```bash
# 共通パッケージを全サービスに反映
./scripts/update_common_and_rebuild.sh
```

### クリーンビルド
```bash
cd scripts && ./build.sh --no-cache
```

### リリース前
```bash
# バージョンアップ + 全ビルド
./scripts/update_common_and_rebuild.sh --increment-version
cd scripts && ./build.sh
```

## Notes

- ビルド後は `./scripts/start.sh` でサービスを起動
- ビルドエラー時は `docker-compose logs <service>` でログ確認
- pipenv環境のみ再構築: `./scripts/rebuild_pipenv.sh`
