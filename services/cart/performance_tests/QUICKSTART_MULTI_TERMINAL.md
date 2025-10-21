# クイックスタート - マルチターミナル性能テスト

## 最速で開始する（3ステップ）

### ステップ1: 複数ターミナルのセットアップ

```bash
cd /home/masa/proj/kugelpos-public/worktree/async-request-logging/services/cart/performance_tests

# 50個のterminalを作成（約5分）
python setup_test_data_multi_terminal.py 50
```

**出力例:**
```
================================================================================
Performance Test Data Setup - Multi Terminal Version
================================================================================
Tenant ID: T1234
Store Code: 5678
Number of Terminals: 50
================================================================================

[1/7] Creating account superuser...
  ✓ Superuser created: admin

[2/7] Getting authentication token...
  ✓ Token obtained

...

✓ All test data setup completed successfully!
✓ Configuration saved to terminals_config.json
```

### ステップ2: テスト実行

```bash
# 20ユーザーで10分間テスト
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 20 \
  --spawn-rate 20 \
  --run-time 10m \
  --headless \
  --html results/multi_terminal_20users.html
```

### ステップ3: 結果確認

```bash
# HTMLレポートを開く
open results/multi_terminal_20users.html

# または統計をコンソールで確認
cat results/multi_terminal_20users.html | grep "Total"
```

---

## 比較テスト（従来 vs マルチターミナル）

### A. 従来のテスト（問題のあるテスト）

```bash
# シングルターミナルのセットアップ
python setup_test_data_multi_terminal.py 1

# テスト実行
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 20 --spawn-rate 20 --run-time 10m --headless \
  --html results/single_terminal_20users.html
```

**期待される結果:**
- CV > 100%（高い変動性）
- ロック待ちによる遅延

### B. マルチターミナルテスト（正しいテスト）

```bash
# マルチターミナルのセットアップ
python setup_test_data_multi_terminal.py 50

# テスト実行
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 20 --spawn-rate 20 --run-time 10m --headless \
  --html results/multi_terminal_20users.html
```

**期待される結果:**
- CV < 50%（低い変動性）
- ロック競合なし
- 一貫した性能

---

## パターン別テスト（推奨）

```bash
# 複数パターンを連続実行
for users in 20 30 40 50; do
  echo "Testing with ${users} users..."
  locust -f locustfile_multi_terminal.py \
    --host=http://localhost:8003 \
    --users ${users} --spawn-rate ${users} --run-time 10m --headless \
    --html results/multi_terminal_${users}users.html \
    --csv results/multi_terminal_${users}users

  echo "Waiting 30 seconds before next test..."
  sleep 30
done

echo "All tests completed! Results in ./results/"
```

---

## トラブルシューティング

### エラー: "Terminal configuration file not found"

```bash
# 解決策: セットアップスクリプトを実行
python setup_test_data_multi_terminal.py 50
```

### エラー: "Connection refused"

```bash
# 解決策: カートサービスが起動しているか確認
cd ../../../../scripts
./start.sh

# サービス確認
docker-compose ps
curl http://localhost:8003/health
```

### テストデータのクリーンアップ

```bash
# MongoDBからテストデータを削除
python cleanup_test_data.py

# または完全リセット
cd ../../../../scripts
./reset-mongodb.sh
```

---

## 次に読むドキュメント

- **詳細ガイド:** [MULTI_TERMINAL_TESTING.md](./MULTI_TERMINAL_TESTING.md)
- **元のREADME:** [README.md](./README.md)
- **分析レポート:** [MULTI_PATTERN_PERFORMANCE_ANALYSIS_ja.md](./MULTI_PATTERN_PERFORMANCE_ANALYSIS_ja.md)

---

**最終更新:** 2025-10-21
