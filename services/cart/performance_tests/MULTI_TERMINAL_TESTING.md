# マルチターミナル性能テスト ガイド

## 概要

このガイドでは、**複数のterminal_idを使用した正確な性能テスト**の実施方法を説明します。

### 問題の背景

従来のテストでは、全ユーザーが同じ`terminal_id`を使用していたため：
- `transaction_no`生成時に`threading.Lock()`によるロック競合が発生
- 応答時間の変動性が非常に高くなる（CV 114-171%）
- 実際の本番環境（複数レジ＝複数terminal_id）と異なる状況でのテスト

### 解決策

各Locustユーザーに**異なるterminal_id**を割り当てることで：
- ロック競合を回避
- 本番環境と同等の条件でテスト
- 真の性能特性を測定

---

## セットアップ手順

### 1. 複数ターミナルの作成

```bash
cd /home/masa/proj/kugelpos-public/worktree/async-request-logging/services/cart/performance_tests

# デフォルト（50個のterminalを作成）
python setup_test_data_multi_terminal.py

# カスタム数のterminalを作成（例：100個）
python setup_test_data_multi_terminal.py 100
```

**実行内容:**
- 1つのtenant、1つのstoreを作成
- 指定された数のterminalを作成（各terminalは独自のAPI keyを持つ）
- 全terminalをopenにする
- 100個のテスト用アイテムを登録
- `terminals_config.json`に設定を保存

**実行時間:** 約5-10分（terminal数による）

### 2. 設定の確認

作成された`terminals_config.json`を確認：

```bash
cat terminals_config.json
```

```json
{
  "tenant_id": "T1234",
  "store_code": "5678",
  "terminals": [
    {
      "terminal_no": 1,
      "terminal_id": "T1234-5678-1",
      "api_key": "xxxxx..."
    },
    {
      "terminal_no": 2,
      "terminal_id": "T1234-5678-2",
      "api_key": "yyyyy..."
    },
    ...
  ],
  "created_at": "2025-10-21T12:00:00"
}
```

---

## テスト実行

### 基本的な実行

```bash
# マルチターミナル版locustfileを使用
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 20 \
  --spawn-rate 2 \
  --run-time 10m \
  --headless
```

### パターン別テスト（推奨）

```bash
# 20ユーザー
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 20 --spawn-rate 20 --run-time 10m --headless

# 30ユーザー
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 30 --spawn-rate 30 --run-time 10m --headless

# 40ユーザー
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 40 --spawn-rate 40 --run-time 10m --headless

# 50ユーザー
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 50 --spawn-rate 50 --run-time 10m --headless
```

---

## テストの仕組み

### Terminal割り当てロジック

```python
# locustfile_multi_terminal.py
def on_start(self):
    # ラウンドロビン方式でterminalを割り当て
    terminal_idx = self.__class__._user_counter % len(TERMINAL_POOL)
    terminal_info = TERMINAL_POOL[terminal_idx]

    self.terminal_id = terminal_info["terminal_id"]
    self.api_key = terminal_info["api_key"]
```

**例（20ユーザー、50 terminals）:**
- ユーザー1 → terminal_id: T1234-5678-1
- ユーザー2 → terminal_id: T1234-5678-2
- ユーザー3 → terminal_id: T1234-5678-3
- ...
- ユーザー20 → terminal_id: T1234-5678-20

**例（60ユーザー、50 terminals）:**
- ユーザー1 → terminal_id: T1234-5678-1
- ユーザー2 → terminal_id: T1234-5678-2
- ...
- ユーザー50 → terminal_id: T1234-5678-50
- ユーザー51 → terminal_id: T1234-5678-1 （ラウンドロビン）
- ユーザー52 → terminal_id: T1234-5678-2

---

## 推奨テスト設定

### Terminal数とユーザー数の関係

| テストユーザー数 | 推奨Terminal数 | 説明 |
|----------------|--------------|------|
| 20 | 20以上 | 全ユーザーが独立したterminal |
| 30 | 30以上 | 全ユーザーが独立したterminal |
| 40 | 40以上 | 全ユーザーが独立したterminal |
| 50 | 50以上 | 全ユーザーが独立したterminal |
| 100 | 50-100 | 一部共有も許容範囲 |

**ベストプラクティス:**
- **理想:** ユーザー数 = Terminal数（ロック競合ゼロ）
- **許容:** ユーザー数 ≤ Terminal数 × 2（軽微なロック競合）
- **避ける:** ユーザー数 > Terminal数 × 3（ロック競合が顕著）

### 単一ターミナル性能テスト（ワーストケース）

**目的:** 単一レジでの最大性能を測定

```bash
# setup時に1つのterminalのみ作成
python setup_test_data_multi_terminal.py 1

# 複数ユーザーが同じterminalを使用（従来のテストと同等）
locust -f locustfile_multi_terminal.py \
  --host=http://localhost:8003 \
  --users 20 --spawn-rate 2 --run-time 10m --headless
```

**期待される結果:**
- 高いCV値（100%以上）
- ロック待ちによる長い応答時間
- スループットの制限

---

## 比較テスト計画

### テストA: マルチターミナル（本番相当）

```bash
# 50個のterminalを作成
python setup_test_data_multi_terminal.py 50

# 20-50ユーザーでテスト
for users in 20 30 40 50; do
  locust -f locustfile_multi_terminal.py \
    --host=http://localhost:8003 \
    --users $users --spawn-rate $users --run-time 10m \
    --headless --html results/multi_terminal_${users}users.html
done
```

### テストB: シングルターミナル（ワーストケース）

```bash
# 1つのterminalのみ作成
python setup_test_data_multi_terminal.py 1

# 20-50ユーザーでテスト
for users in 20 30 40 50; do
  locust -f locustfile_multi_terminal.py \
    --host=http://localhost:8003 \
    --users $users --spawn-rate $users --run-time 10m \
    --headless --html results/single_terminal_${users}users.html
done
```

### 比較ポイント

| 指標 | マルチターミナル | シングルターミナル |
|------|----------------|------------------|
| CV (変動係数) | < 50% 期待 | > 100% （既存結果） |
| 平均応答時間 | 低い | 高い（ロック待ち） |
| p95応答時間 | 一貫性あり | 非常に高い |
| スループット | 高い | 制限される |

---

## トラブルシューティング

### エラー: "Terminal configuration file not found"

**原因:** `terminals_config.json`が存在しない

**解決策:**
```bash
python setup_test_data_multi_terminal.py
```

### エラー: "Failed to create terminal"

**原因:** Terminal serviceが起動していない、またはDB接続エラー

**確認:**
```bash
docker-compose ps
docker-compose logs terminal
```

### 警告: ユーザー数 > Terminal数

**症状:** Locust実行時に一部のユーザーがterminalを共有

**影響:** ロック競合が発生する可能性あり

**推奨:** Terminal数を増やして再セットアップ
```bash
# データクリーンアップ
python cleanup_test_data.py

# より多くのterminalで再作成
python setup_test_data_multi_terminal.py 100
```

---

## クリーンアップ

テストデータの削除：

```bash
# MongoDBからテストデータを削除
python cleanup_test_data.py

# または、MongoDB完全リセット
cd ../../../../scripts
./reset-mongodb.sh
```

---

## 期待される改善結果

### 従来のテスト（シングルターミナル）

```
20ユーザー: CV 114.7%, 中央値 42ms, p95 200ms
30ユーザー: CV 170.9%, 中央値 47ms, p95 350ms
```

### マルチターミナルテスト（予測）

```
20ユーザー: CV < 50%, 中央値 35-40ms, p95 80-120ms
30ユーザー: CV < 50%, 中央値 35-40ms, p95 80-120ms
40ユーザー: CV < 60%, 中央値 35-45ms, p95 100-150ms
50ユーザー: CV < 70%, 中央値 40-50ms, p95 120-180ms
```

**主要な改善:**
- **CV値が1/2～1/3に改善**（変動性が大幅に減少）
- **p95レイテンシが安定**（ロック待ちの除去）
- **スループットの向上**（並列処理の効果）
- **サービスクラッシュ閾値の向上**（リソース使用の最適化）

---

## 次のステップ

1. **マルチターミナルテスト実行** → 真の性能特性を測定
2. **シングルターミナルテスト実行** → ワーストケースの確認
3. **結果比較レポート作成** → 改善効果の定量化
4. **コード改善検討** → `threading.Lock()` → MongoDB `findOneAndUpdate`への移行

---

**作成日:** 2025-10-21
**バージョン:** 1.0
