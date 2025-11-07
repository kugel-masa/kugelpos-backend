# Release Notes v0.2.5

**リリース日**: 2025-11-07

## 概要

売上レポートの内税処理に関する重大なバグを修正。純売上に内税が含まれる問題（Issue #90）を解決し、全ての税タイプ（外税・内税・非課税）が正確に純売上から差し引かれるようになりました。

本リリースにより、**外税・内税のいずれのケースでも純売上が正確に税抜金額**として計算されます。

---

## 🐛 バグ修正

### Issue #90: 純売上に内税が含まれる（内税が差し引かれない）

**問題**:
- 純売上に内税が含まれ、税抜本体価格が算出されていない
- 内税のみの取引で純売上が税込金額のまま表示される

**具体例**:
```
商品: 1,100円 (税込、内税10% = 100円含む)

修正前:
 純売上: 1,100円 ← 誤り（内税が引かれていない）

修正後:
 純売上: 1,000円 ← 正しい（税抜本体価格）
```

**根本原因**:
- Cartサービスは`sales.tax_amount`フィールドに**外税のみ**を格納（仕様通り）
- 内税は`taxes`配列の中に`tax_type: "Internal"`として格納
- しかし、Reportサービスの集計パイプラインは`sales.tax_amount`のみ使用
- 結果として内税が純売上の計算から漏れていた

**修正内容**:

`services/report/app/services/plugins/sales_report_maker.py`:

1. **中間グループ化（line 485-507）**: `taxes`配列を収集
   ```python
   # 修正前: sales.tax_amount（外税のみ）を使用
   "sales_tax_amount": {"$first": "$sales.tax_amount"}

   # 修正後: taxes配列全体を収集（$addToSetで重複回避）
   "taxes": {"$addToSet": "$taxes"}
   ```

2. **最終グループ化（line 520-538）**: 全税額を計算
   ```python
   # 修正後: taxes配列から全税額を計算（外税+内税+非課税）
   # $reduceを使って各取引のtaxes配列内の税額を合計
   "total_tax_amount": {
       "$sum": {
           "$reduce": {
               "input": {"$ifNull": ["$taxes", []]},
               "initialValue": 0,
               "in": {"$add": ["$$value", {"$ifNull": ["$$this.tax_amount", 0]}]}
           }
       }
   }
   ```

**重要な技術的改善**:

初期の修正では`$sum`を2重にネストしていましたが、MongoDBが正しく解釈できませんでした：
```python
# ❌ 誤った実装（Issue #78テスト失敗）
"total_tax_amount": {
    "$sum": {
        "$sum": {
            "$map": {...}
        }
    }
}
```

最終的な修正では`$reduce`演算子を使用して正しく実装：
```python
# ✅ 正しい実装（全テスト成功）
"total_tax_amount": {
    "$sum": {
        "$reduce": {
            "input": {"$ifNull": ["$taxes", []]},
            "initialValue": 0,
            "in": {"$add": ["$$value", {"$ifNull": ["$$this.tax_amount", 0]}]}
        }
    }
}
```

**検証式**:
```
純売上 = 総売上 - 返品 - 値引 - 全税額（外税 + 内税）
       = 1,100 - 0 - 0 - 100
       = 1,000円 ✅
```

**影響範囲**:
- 売上レポートの純売上計算（内税取引）
- Flash/Daily/Terminalすべてのレポートスコープ
- 売上レポートの税額集計

**テスト**:
- `tests/test_issue_90_internal_tax_not_deducted.py`: **4つのテストケース**（オプションテスト2つを追加）
  1. `test_internal_tax_not_deducted_from_sales_net`: 内税のみのケース
  2. `test_mixed_tax_scenario`: 外税+内税の混合ケース
  3. `test_internal_tax_with_return`: **内税+返品のケース（新規追加）**
  4. `test_multiple_internal_tax_rates`: **複数の内税率（8%+10%）のケース（新規追加）**
- `tests/test_sales_report_formula_internal_tax.py`: 既存の内税テストのテストデータを修正（`sales.tax_amount: 0.0`に変更）
- `tests/test_critical_issue_78.py`: Cartesian product回帰テスト（3 passed）
- `tests/test_split_payment_bug.py`: 分割支払いバグ回帰テスト（2 passed）
- `tests/test_data_integrity.py`: データ整合性テスト（4 passed）
- `tests/test_comprehensive_aggregation.py`: 包括的集計テスト（5 passed）
- `tests/test_edge_cases.py`: エッジケーステスト（5 passed）

**オプションテストの詳細**:

3. **`test_internal_tax_with_return`**: 内税商品の返品処理を検証

   **目的**: 内税商品の返品時に税額が正しくキャンセルされることを確認

   **テストシナリオ**:
   - 売上取引: 1,100円（税込、内税10% = 100円含む）
   - 返品取引: -1,100円（税込、内税10% = -100円）

   **テストデータ**:
   ```python
   # 売上取引
   sale_transaction = BaseTransaction(
       line_items=[{
           "item_code": "INTERNAL_TAX_ITEM",
           "unit_price": 1100.0,  # 税込価格
           "quantity": 1,
           "amount": 1100.0,
           "tax_code": "02"  # 内税10%
       }],
       taxes=[{
           "tax_code": "02",
           "tax_type": "Internal",
           "tax_name": "内税10%",
           "tax_amount": 100.0,  # 1100 / 1.1 * 0.1
           "target_amount": 1000.0
       }],
       sales={
           "total_amount": 1100.0,
           "tax_amount": 0.0  # 内税はtaxes配列に格納（Cart service仕様）
       }
   )

   # 返品取引（同じ構造）
   return_transaction = BaseTransaction(...)
   ```

   **検証項目**:
   - ✅ 総売上: 1,100円（税込）
   - ✅ 返品: 1,100円（税込）
   - ✅ 税額: 100円 - 100円 = 0円（売上と返品でキャンセル）
   - ✅ 純売上: 1,100 - 1,100 - 0 = **0円**（正しく相殺）

   **重要性**: 返品時に内税が正しく処理されないと、純売上が誤って計算される

4. **`test_multiple_internal_tax_rates`**: 複数の内税率が混在するケースを検証

   **目的**: 軽減税率8%と標準税率10%の内税が混在する取引で、各税率が個別に集計されることを確認

   **テストシナリオ**:
   - 商品A: 1,080円（税込、軽減税率8% = 80円含む）
   - 商品B: 1,100円（税込、標準税率10% = 100円含む）

   **テストデータ**:
   ```python
   sale_transaction = BaseTransaction(
       line_items=[
           {
               "line_no": 1,
               "item_code": "INTERNAL_TAX_8",
               "unit_price": 1080.0,  # 1000円 + 8% = 1080円
               "quantity": 1,
               "amount": 1080.0,
               "tax_code": "03"  # 軽減税率8%
           },
           {
               "line_no": 2,
               "item_code": "INTERNAL_TAX_10",
               "unit_price": 1100.0,  # 1000円 + 10% = 1100円
               "quantity": 1,
               "amount": 1100.0,
               "tax_code": "02"  # 標準税率10%
           }
       ],
       taxes=[
           {
               "tax_code": "03",
               "tax_type": "Internal",
               "tax_name": "軽減税率8%",
               "tax_amount": 80.0,  # 1080 / 1.08 * 0.08
               "target_amount": 1000.0
           },
           {
               "tax_code": "02",
               "tax_type": "Internal",
               "tax_name": "内税10%",
               "tax_amount": 100.0,  # 1100 / 1.1 * 0.1
               "target_amount": 1000.0
           }
       ],
       sales={
           "total_amount": 2180.0,  # 1080 + 1100
           "tax_amount": 0.0  # 内税はtaxes配列に格納
       }
   )
   ```

   **検証項目**:
   - ✅ 総売上: 2,180円（税込合計）
   - ✅ 税額合計: 80円 + 100円 = 180円
   - ✅ 純売上: 2,180 - 180 = **2,000円**（税抜本体価格）
   - ✅ 税額内訳:
     - 軽減税率8%: 80円（target_amount: 1,000円）
     - 内税10%: 100円（target_amount: 1,000円）

   **重要性**: 軽減税率制度により、8%と10%の内税が混在する取引が実際に発生するため、
             各税率が個別に正しく集計されることが必須

**テスト結果**:
```
Issue #90 tests: 4 passed (うち新規追加2つ)
Issue #78 regression tests: 19 passed
Total: 23 tests passed
```

---

## 📝 変更されたファイル

**コード変更**:
- `services/report/app/services/plugins/sales_report_maker.py`: 集計パイプライン修正（taxes配列から全税額を計算）

**テスト追加・修正**:
- `services/report/tests/test_issue_90_internal_tax_not_deducted.py`: Issue #90検証テスト（新規、4ケース）
  - 基本テスト2ケース + オプションテスト2ケース（内税+返品、複数内税率）
- `services/report/tests/test_sales_report_formula_internal_tax.py`: テストデータ修正
  - `sales.tax_amount: 273.0` → `0.0`（Cart service仕様に準拠）
- `services/report/run_all_tests.sh`: テストリストに`test_issue_90_internal_tax_not_deducted.py`を追加

---

## 🔗 関連Issue・PR

- Issue #90: バグ: 純売上に内税が含まれている（内税が差し引かれない）
  - https://github.com/kugel-masa/kugelpos-backend-private/issues/90
- Issue #78: Cartesian product bug（回帰テスト実施）

---

## ⚠️ 重要な注意事項

このバグ修正により、売上レポートの純売上金額が変わります:

**内税取引の影響**:
- **修正前**: 純売上に内税が含まれる（税込表示）
- **修正後**: 純売上から内税が除外される（税抜表示）
- **影響**: 内税取引の純売上が減少（正しい税抜金額になる）

**計算式の確認**:
```
純売上 = 総売上 - 返品 - 値引 - 税額（外税 + 内税 + 非課税）
```

既存のレポートと比較すると金額が異なりますが、これは**修正後が正しい**金額です。

---

## 📊 影響を受ける機能

- 売上レポートの純売上計算（内税取引）
- Flash/Daily/Terminalすべてのレポートスコープ
- 売上レポートAPI（`/api/v1/reports/sales`）
- 売上レポート印字データ

---

## 🚀 アップグレード手順

### ローカル環境

```bash
# 1. 最新版に更新
git checkout v0.2.5

# 2. report サービスを再ビルド
cd services
./scripts/build.sh report

# 3. 全サービスを再起動
./scripts/stop.sh
./scripts/start.sh

# 4. テスト実行（推奨）
cd report
./run_all_tests.sh
```

### Azure Container Apps

```bash
# 1. Dockerイメージのビルドとプッシュ
cd /home/masa/proj/kugelpos-private
echo "y" | ./scripts/build-and-push-azure.sh -t v0.2.5 --push

# 2. report サービスのみ更新
echo "y" | ./scripts/update-azure-container-apps.sh -t v0.2.5 -s "report"

# 3. ヘルスチェック
./scripts/check_service_health.sh -a thankfulbeach-66ab2349.japaneast.azurecontainerapps.io -v
```

**ダウンタイム**: サービス再起動のみ（1-2分）

---

## 🎯 技術的詳細

### MongoDB Aggregation演算子の使用

**$reduce vs $sum + $map**:

本修正では、taxes配列内の税額を合計するために`$reduce`演算子を使用しました。

```python
# ❌ 失敗した実装（Issue #78回帰）
"total_tax_amount": {
    "$sum": {
        "$sum": {
            "$map": {
                "input": {"$ifNull": ["$taxes", []]},
                "as": "tax",
                "in": {"$ifNull": ["$$tax.tax_amount", 0]}
            }
        }
    }
}
```

上記の実装では、外側の`$sum`（グループアキュムレータ）と内側の`$sum`（配列演算子）が混在し、MongoDBが正しく解釈できませんでした。

```python
# ✅ 成功した実装
"total_tax_amount": {
    "$sum": {  # グループアキュムレータ：全取引にわたって合計
        "$reduce": {  # 配列演算子：各取引のtaxes配列を合計
            "input": {"$ifNull": ["$taxes", []]},
            "initialValue": 0,
            "in": {"$add": ["$$value", {"$ifNull": ["$$this.tax_amount", 0]}]}
        }
    }
}
```

`$reduce`を使用することで：
1. 各取引の`taxes`配列を個別に合計
2. その結果を外側の`$sum`で全取引にわたって合計

という明確な処理フローが実現されました。

### Cartesian Product対策の維持

Issue #78で実装されたCartesian product対策（`$addToSet`の使用）は維持されています：

```python
# 中間グループ化でtaxes配列を収集
"taxes": {"$addToSet": "$taxes"}  # 重複を除外

# 最終グループ化で税額を計算
"total_tax_amount": {
    "$sum": {
        "$reduce": {...}  # 収集されたtaxes配列から税額を計算
    }
}
```

---

## 🧪 テストカバレッジ

### Issue #90 専用テスト（4ケース）
1. **内税のみのケース**: 基本的なバグ検出
2. **外税+内税の混合ケース**: 複数税タイプの同時処理
3. **内税+返品のケース**（新規追加）: 返品時の内税処理を検証
   - 売上と返品で内税が正しくキャンセルされることを確認
4. **複数の内税率（8%+10%）のケース**（新規追加）: 異なる内税率の混在
   - 軽減税率8%と標準税率10%が個別に集計されることを確認

### テストデータの改善
- `test_sales_report_formula_internal_tax.py`: Cart service仕様に準拠
  - 内税取引の`sales.tax_amount`を`0.0`に修正（従来は`273.0`で不正確）
  - これにより、v0.2.4では検出できなかったバグを確実に検出可能に

### Issue #78 回帰テスト
- 店舗全体の複数端末集計（Cartesian product リスク）
- 極端な分割支払い（5分割 × 3税率 = 15倍リスク）
- データ整合性検証（基本的なPOS方程式）
- 包括的集計テスト
- エッジケーステスト

**合計**: 23テスト、全て成功（Issue #90: 4ケース、Issue #78回帰: 19ケース）

---

**リリース担当**: Claude Code
**レビュー**: masa@kugel
