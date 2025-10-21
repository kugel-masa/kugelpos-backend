# マルチターミナルモードへの移行完了

## 概要

性能テストスクリプトを**マルチターミナルモード**に完全移行しました。これにより、従来の実行手順をそのまま使用するだけで、自動的にマルチターミナルテストが実行されます。

## 変更内容

### 1. スクリプトの更新

#### `run_perf_test.sh`
- ✅ `setup_test_data()` をマルチターミナル版に変更
- ✅ `terminals_config.json` の存在を自動検出
- ✅ 存在する場合は `locustfile_multi_terminal.py` を使用
- ✅ ない場合は `locustfile.py` にフォールバック（警告表示）
- ✅ Terminal数をパラメータで指定可能: `./run_perf_test.sh setup 100`

#### `run_multiple_tests.sh`
- ✅ 各パターンでユーザー数+10のterminalを自動作成
- ✅ ヘッダーにマルチターミナルモードの説明を追加
- ✅ 実行時にマルチターミナルモードであることを明示

#### `README.md`
- ✅ マルチターミナルモードの説明を追加
- ✅ クイックスタートセクションを更新
- ✅ Web UIモードでの使用方法を追加

### 2. 新規ファイル

- ✅ `setup_test_data_multi_terminal.py` - 複数terminal作成スクリプト
- ✅ `locustfile_multi_terminal.py` - マルチターミナル対応Locustfile
- ✅ `MULTI_TERMINAL_TESTING.md` - 詳細ガイド
- ✅ `QUICKSTART_MULTI_TERMINAL.md` - クイックスタート
- ✅ `terminals_config.json` - Terminal設定（自動生成、.gitignore済）

---

## 使用方法（変更なし！）

### 従来通りの実行方法がそのまま使えます

```bash
cd services/cart/performance_tests

# パターン1: 自動実行（最も簡単）
./run_perf_test.sh

# パターン2: 手動セットアップ
./run_perf_test.sh setup      # 50 terminalsを作成（デフォルト）
./run_perf_test.sh setup 100  # 100 terminalsを作成
./run_perf_test.sh pattern1
./run_perf_test.sh cleanup

# パターン3: 複数パターン実行
./run_multiple_tests.sh
```

**重要:** コマンドは全く同じです！スクリプトが自動的にマルチターミナルモードを使用します。

---

## 動作の違い

### 従来（シングルターミナル）

```bash
./run_perf_test.sh setup
# → 1つのterminalのみ作成
# → terminal_id: T1234-5678-9

./run_perf_test.sh pattern1
# → 全20ユーザーが同じterminal_idを使用
# → threading.Lock()で順番待ち
# → CV > 100%（高い変動性）
```

### 現在（マルチターミナル）

```bash
./run_perf_test.sh setup
# → 50個のterminalを作成（デフォルト）
# → terminal_id: T1234-5678-1, T1234-5678-2, ..., T1234-5678-50
# → terminals_config.json に保存

./run_perf_test.sh pattern1
# → 各ユーザーが異なるterminal_idを使用
# → ロック競合なし
# → CV < 50%（低い変動性）期待
```

---

## 自動検出メカニズム

### `run_perf_test.sh` の動作

```bash
# Step 1: terminals_config.jsonの存在チェック
if [ -f "terminals_config.json" ]; then
    # マルチターミナルモード
    locustfile="locustfile_multi_terminal.py"
    echo "Using Multi-Terminal Mode"
else
    # シングルターミナルモード（フォールバック）
    locustfile="locustfile.py"
    echo "Warning: Using single-terminal mode"
    echo "Run './run_perf_test.sh setup' to enable multi-terminal"
fi
```

### `run_multiple_tests.sh` の動作

```bash
# 各パターンで自動的に適切な数のterminalを作成
for users in 20 30 40 50; do
    num_terminals=$((users + 10))  # 余裕を持たせる
    ./run_perf_test.sh setup "$num_terminals"
    ./run_perf_test.sh custom "$users" "10m"
done
```

---

## Terminal数の推奨設定

| テストユーザー数 | 推奨Terminal数 | コマンド |
|----------------|--------------|---------|
| 20 | 30 | `./run_perf_test.sh setup 30` |
| 30 | 40 | `./run_perf_test.sh setup 40` |
| 40 | 50 | `./run_perf_test.sh setup 50` |
| 50 | 60 | `./run_perf_test.sh setup 60` |
| 100 | 110-150 | `./run_perf_test.sh setup 150` |

**ルール:** Terminal数 ≥ ユーザー数 + 予備（10-50）

---

## トラブルシューティング

### Q1: terminals_config.json が見つからないエラー

**症状:**
```
Error: Terminal configuration file not found
```

**解決策:**
```bash
./run_perf_test.sh setup
```

### Q2: 以前のシングルターミナルテストと比較したい

**方法:**
```bash
# シングルターミナルで実行
./run_perf_test.sh setup 1
./run_perf_test.sh pattern1

# マルチターミナルで実行
./run_perf_test.sh setup 50
./run_perf_test.sh pattern1

# 結果比較
```

### Q3: カスタムTerminal数で実行したい

**方法:**
```bash
# 200 terminalsを作成
./run_perf_test.sh setup 200

# 150ユーザーでテスト
./run_perf_test.sh custom 150 10m
```

---

## 期待される効果

### 性能指標の改善

| 指標 | シングルターミナル | マルチターミナル | 改善 |
|------|------------------|----------------|------|
| **CV (変動係数)** | 114-171% | < 50% | **60-70%改善** |
| **中央値応答時間** | 42-61ms | 35-45ms | 15-25%改善 |
| **p95応答時間** | 200-350ms | 80-150ms | **50-60%改善** |
| **最大応答時間** | 1,688-2,937ms | 200-500ms | **80-85%改善** |
| **スループット** | 制限される | 向上 | 20-30%改善 |

### 測定の信頼性

- ✅ **再現性向上**: CVが低いため、テスト結果が安定
- ✅ **本番環境との一致**: 複数レジ（複数terminal_id）の実際の使用状況を再現
- ✅ **ボトルネック特定**: ロック競合による偽のボトルネックを排除

---

## 次のステップ

### 1. マルチターミナルテストの実行

```bash
cd services/cart/performance_tests
./run_multiple_tests.sh
```

### 2. 結果の確認

```bash
# バックアップディレクトリを確認
ls -la results_backup/

# 最新の結果を確認
ls -la results_backup/$(ls -t results_backup/ | head -1)/
```

### 3. レポート分析

- `MULTI_PATTERN_PERFORMANCE_ANALYSIS_ja.md` - 以前のシングルターミナル結果
- 新しいマルチターミナル結果と比較

### 4. コード改善（オプション）

マルチターミナルテストで真の性能を測定した後、さらなる最適化:

- `threading.Lock()` → MongoDB `findOneAndUpdate()` への置換
- カウンター事前割り当て方式の検討
- 非同期処理の最適化

---

## まとめ

✅ **変更完了**: すべてのスクリプトがマルチターミナル対応
✅ **後方互換性**: 既存のコマンドがそのまま使える
✅ **自動検出**: terminals_config.jsonの有無で自動切り替え
✅ **柔軟性**: Terminal数をカスタマイズ可能
✅ **ドキュメント充実**: 詳細ガイドとクイックスタートを用意

**今すぐ試せます:**
```bash
cd services/cart/performance_tests
./run_perf_test.sh
```

---

**作成日:** 2025-10-21
**バージョン:** 1.0
