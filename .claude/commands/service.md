---
description: サービスの起動・停止・再起動を実行
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/service <ACTION> [SERVICES...] [OPTIONS]`

**Examples:**
- `/service start` → 全サービス起動
- `/service stop` → 全サービス停止
- `/service restart cart report` → cart, reportを再起動（Daprサイドカー含む）
- `/service stop --clean` → 停止 + データ削除
- `/service logs cart` → ログ表示

## Actions

| Action | Description |
|--------|-------------|
| `start` | サービス起動（MongoDB replica set初期化含む） |
| `stop` | サービス停止 |
| `restart` | サービス再起動（Daprサイドカー含む） |
| `status` | サービス状態確認 |
| `logs` | ログ表示 |

## Service & Dapr Sidecar Mapping

**重要:** 特定サービス再起動時は、Daprサイドカーも同時に再起動が必要

| Service | Dapr Sidecar | Port |
|---------|--------------|------|
| account | dapr_account | 8000 |
| terminal | dapr_terminal | 8001 |
| master-data | dapr_master_data | 8002 |
| cart | dapr_cart | 8003 |
| report | dapr_report | 8004 |
| journal | dapr_journal | 8005 |
| stock | dapr_stock | 8006 |

## Commands

### 全サービス起動
```bash
./scripts/start.sh
```

### 全サービス停止
```bash
./scripts/stop.sh
```

### 停止 + データ削除
```bash
./scripts/stop.sh --clean
```

### 特定サービス再起動（Daprサイドカー含む）
```bash
# cart を再起動
cd services && docker-compose restart cart dapr_cart

# 複数サービスを再起動
cd services && docker-compose restart cart dapr_cart report dapr_report

# master-data を再起動（アンダースコアに注意）
cd services && docker-compose restart master-data dapr_master_data
```

### 特定サービスのみ起動
```bash
cd services && docker-compose up -d cart dapr_cart
```

### 特定サービスのみ停止
```bash
cd services && docker-compose stop cart dapr_cart
```

### サービス状態確認
```bash
cd services && docker-compose ps
```

### ログ表示
```bash
# 全サービス
cd services && docker-compose logs -f

# 特定サービス + Dapr
cd services && docker-compose logs -f cart dapr_cart

# 直近100行
cd services && docker-compose logs --tail=100 cart dapr_cart
```

## Typical Workflows

### 開発開始
```bash
./scripts/start.sh
```

### 開発終了
```bash
./scripts/stop.sh
```

### コード変更後（特定サービス）
```bash
# ビルド → 再起動（Dapr含む）
cd scripts && ./build.sh cart
cd services && docker-compose restart cart dapr_cart
```

### 問題発生時（クリーンリスタート）
```bash
./scripts/stop.sh --clean
./scripts/start.sh
```

### デバッグ時
```bash
cd services
docker-compose restart cart dapr_cart && docker-compose logs -f cart dapr_cart
```

## Quick Reference

```bash
# よく使うコマンド
./scripts/start.sh                                    # 全起動
./scripts/stop.sh                                     # 全停止
cd services && docker-compose restart cart dapr_cart  # cart再起動
cd services && docker-compose logs -f cart            # ログ監視
cd services && docker-compose ps                      # 状態確認
```

## Service URLs (Local)

| Service | Docs | Health |
|---------|------|--------|
| account | http://localhost:8000/docs | http://localhost:8000/health |
| terminal | http://localhost:8001/docs | http://localhost:8001/health |
| master-data | http://localhost:8002/docs | http://localhost:8002/health |
| cart | http://localhost:8003/docs | http://localhost:8003/health |
| report | http://localhost:8004/docs | http://localhost:8004/health |
| journal | http://localhost:8005/docs | http://localhost:8005/health |
| stock | http://localhost:8006/docs | http://localhost:8006/health |

## Troubleshooting

### MongoDB接続エラー
```bash
./scripts/init-mongodb-replica.sh
```

### ポート競合
```bash
lsof -i :8003
kill -9 $(lsof -t -i :8003)
```

### 全リセット
```bash
./scripts/stop.sh --clean
./scripts/reset-mongodb.sh
./scripts/start.sh
```
