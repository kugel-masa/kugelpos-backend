# 上級ハンズオン: カテゴリ単位割引機能の実装

このハンズオンでは、Spec Kit を使ってプラグインアーキテクチャとルールエンジンを活用した高度な機能を実装します。

## 目次

1. [ハンズオンの概要](#ハンズオンの概要)
2. [前提条件](#前提条件)
3. [学習目標](#学習目標)
4. [機能要件](#機能要件)
5. [実装の流れ](#実装の流れ)
6. [Step 1: 仕様作成](#step-1-仕様作成)
7. [Step 2: 実装計画](#step-2-実装計画)
8. [Step 3: タスク分解](#step-3-タスク分解)
9. [Step 4: 実装](#step-4-実装)
10. [Step 5: テスト実行](#step-5-テスト実行)
11. [まとめ](#まとめ)

---

## ハンズオンの概要

### 実装する機能

**カテゴリ単位割引機能**

商品カテゴリ（`category_code`）に基づいて、特定期間中に自動的に割引を適用する機能を実装します。プラグインアーキテクチャを使用して拡張可能な設計を学びます。

### 対象サービス

- **master-data サービス**: プロモーションマスターの管理
- **cart サービス**: プロモーションエンジン（プラグイン）の実装
- **report サービス**: プロモーション効果測定レポート
- **journal サービス**: プロモーション適用履歴の記録

### 難易度

⭐⭐⭐⭐⭐（上級）

### 所要時間

8〜10時間

---

## 前提条件

### 必須

- [ ] 「取引キャンセル理由記録機能」ハンズオンを完了している
- [ ] プラグインアーキテクチャの基本理解
- [ ] デザインパターン（Strategy パターン）の理解
- [ ] Claude Code、Spec Kit がインストール済み
- [ ] Docker と Docker Compose が利用可能
- [ ] Python 3.12+ がインストール済み

### 確認コマンド

```bash
# 基本ツールの確認
claude --version
specify --help
docker --version
docker compose version
python --version

# 既存のプロモーション機能を確認
ls services/cart/app/strategies/promotions/
```

### 環境準備

```bash
# プロジェクトルートに移動
cd /home/masa/proj/kugelpos-public/worktree/ai-coding-lesson

# サービスが起動していない場合は起動
cd ../../../
./quick_start.sh

# 元のディレクトリに戻る
cd worktree/ai-coding-lesson
```

---

## 学習目標

このハンズオンを通じて以下を習得します：

### 高度なアーキテクチャパターン

- [ ] プラグインアーキテクチャの設計と実装
- [ ] Strategy パターンの実践
- [ ] ルールエンジンの構築
- [ ] プロモーション優先順位制御

### 複雑なビジネスロジック

- [ ] 複数プロモーションの組み合わせ処理
- [ ] 割引計算ロジックの実装
- [ ] カテゴリマスターとの連携
- [ ] 期間・条件判定の実装

### 拡張性と保守性

- [ ] プラグイン登録システム
- [ ] 設定ファイル駆動の実装
- [ ] テスタビリティの確保
- [ ] パフォーマンス最適化

---

## 機能要件

> **注意**: 以下は機能要件のサンプルです。実際のハンズオンでは `/speckit.specify` コマンドで生成される仕様書の内容に従ってください。

### ユーザーストーリー（サンプル）

以下は期待される仕様の例です。実際の仕様作成では、AI が対話を通じてより詳細な内容を生成します。

#### US1: プロモーションマスターの管理（優先度: P1）

**目的**: 管理者がカテゴリ単位のプロモーションを設定できるようにする

**主なシナリオ**:
- プロモーションの CRUD 操作
- 対象カテゴリの指定（複数カテゴリ対応）
- 適用期間の設定（開始日時・終了日時）
- 割引率・割引額の設定
- 優先順位の設定

---

#### US2: カート計算時にプロモーションを自動適用（優先度: P1）

**目的**: 商品追加時に該当するプロモーションを自動的に適用する

**主なシナリオ**:
- カテゴリコードによる対象商品判定
- 複数プロモーションの優先順位処理
- 割引額の計算と適用
- 割引情報の明細表示

---

#### US3: プロモーション効果測定レポート（優先度: P2）

**目的**: 管理者がプロモーションの効果を分析できるようにする

**主なシナリオ**:
- プロモーション別の適用回数・金額集計
- カテゴリ別の売上比較（プロモーション前後）
- 期間指定でのレポート取得

---

### 技術要件（参考）

実際の実装では、`/speckit.plan` で生成される計画に従います。

#### データモデル例

```python
# プロモーションマスター（イメージ）
{
    "promotion_code": "PROMO001",
    "promotion_name": "飲料カテゴリ10%オフ",
    "promotion_type": "category_discount",
    "target_category_codes": ["DRINK", "JUICE"],
    "discount_type": "percentage",  # percentage / fixed_amount
    "discount_value": 10.0,
    "start_datetime": "2025-12-01T00:00:00",
    "end_datetime": "2025-12-31T23:59:59",
    "priority": 1,
    "is_active": true,
    "tenant_code": "TENANT001"
}
```

#### プラグイン構造例

```python
# プロモーションプラグインインターフェース
class BasePromotionPlugin(ABC):
    @abstractmethod
    async def is_applicable(self, item, promotion) -> bool:
        """このプロモーションが適用可能か判定"""
        pass

    @abstractmethod
    async def calculate_discount(self, item, promotion) -> Decimal:
        """割引額を計算"""
        pass

    @abstractmethod
    def get_priority(self) -> int:
        """プラグインの優先順位"""
        pass
```

---

## 実装の流れ

### 全体フロー

```
Step 1: 仕様作成 (/speckit.specify)
    ↓
Step 2: 実装計画 (/speckit.plan)
    ↓
Step 3: タスク分解 (/speckit.tasks)
    ↓
Step 4: 実装 (/speckit.implement)
    ↓
Step 5: テスト実行 (全テストパス確認)
```

### タイムライン

| ステップ | 所要時間 | 内容 |
|---------|---------|------|
| Step 1 | 60分 | 仕様書作成、複雑な要件の明確化 |
| Step 2 | 90分 | 実装計画、アーキテクチャ設計 |
| Step 3 | 60分 | タスク分解、依存関係の整理 |
| Step 4 | 300分 | プラグイン実装、テスト作成 |
| Step 5 | 60分 | テスト実行、デバッグ、パフォーマンス確認 |

---

## Step 1: 仕様作成

### 目的

複雑なビジネスロジックを含む機能要件を明確にし、テスト可能な仕様書を作成します。

### 手順

1. **Claude Code を起動**

   ```bash
   # プロジェクトルートで起動
   claude
   ```

2. **仕様作成コマンドを実行**

   Claude Code のプロンプトで以下を入力：

   ```
   /speckit.specify 商品カテゴリ（category_code）に基づいて、特定期間中に自動的に割引を適用する機能を追加。複数カテゴリ対応、優先順位制御、プラグインアーキテクチャで拡張可能にする。
   ```

3. **AI との対話**

   AI が以下について質問する可能性があります：

   - 複数プロモーションが重複した場合の処理は？
   - 割引の最大値や最小値の制限は？
   - プロモーションコードの入力機能は必要か？
   - カテゴリ階層がある場合の適用範囲は？

   **推奨回答例**:
   ```
   - 複数プロモーション重複時は優先順位が高いものを1つだけ適用
   - 割引後の価格が0円未満にならないよう制御
   - プロモーションコード入力は不要（自動適用のみ）
   - カテゴリは単一レベル（category_code のみ）で階層は考慮しない
   ```

4. **生成された仕様書を確認**

   以下のファイルが生成されます：
   ```
   specs/NNN-category-discount/spec.md
   ```

   確認ポイント：
   - [ ] プロモーションの適用条件が明確
   - [ ] 優先順位のロジックが定義されている
   - [ ] エッジケース（重複、無効な設定など）が網羅されている
   - [ ] プラグイン拡張性の要件が記載されている

### チェックポイント

生成された仕様書が以下を満たしているか確認：

- [ ] **ユーザーストーリー**: 3つのストーリー（US1: マスター管理、US2: 自動適用、US3: 効果測定）
- [ ] **ビジネスルール**: 優先順位、重複処理、割引計算ルールが明確
- [ ] **拡張性**: プラグインで新しいプロモーションタイプを追加可能
- [ ] **パフォーマンス**: カート計算時の性能要件

### トラブルシューティング

**問題**: 仕様が曖昧（複数プロモーション重複時の挙動など）

**解決**: `/speckit.clarify` を使用して具体的なシナリオを質問

```bash
/speckit.clarify
```

---

## Step 2: 実装計画

### 目的

プラグインアーキテクチャとルールエンジンの技術設計を行います。

### 手順

1. **実装計画コマンドを実行**

   ```
   /speckit.plan
   ```

2. **AI が生成する成果物**

   以下のファイルが生成されます：
   ```
   specs/NNN-category-discount/plan.md
   specs/NNN-category-discount/research.md
   specs/NNN-category-discount/data-model.md
   specs/NNN-category-discount/contracts/
   ```

3. **生成された計画を確認**

   **plan.md** の確認ポイント：
   - [ ] プラグインアーキテクチャの設計図
   - [ ] プロモーションエンジンのフロー
   - [ ] 優先順位処理のアルゴリズム
   - [ ] パフォーマンス最適化戦略

   **data-model.md** の確認ポイント：
   - [ ] Promotion モデルの定義
   - [ ] CartItem への割引情報追加
   - [ ] プラグイン設定ファイルの構造

### Constitution Check

計画が以下の原則に準拠しているか確認：

- [ ] **プラグインアーキテクチャ**: 新しいプロモーションタイプを追加可能
- [ ] **テストファースト**: プラグインごとのテストケース定義
- [ ] **共有 Commons ライブラリ**: 基底クラスを commons に配置
- [ ] **パフォーマンス**: カート計算が200ms以内

### アーキテクチャ設計のポイント

#### プロモーションエンジンのフロー

```
1. カートに商品追加
    ↓
2. 該当カテゴリのプロモーション検索
    ↓
3. 適用可能なプロモーションをフィルタリング
    ↓
4. 優先順位でソート
    ↓
5. 最高優先度のプロモーション適用
    ↓
6. 割引額計算
    ↓
7. カート明細に反映
```

#### プラグイン登録

```python
# plugins.json
{
  "promotions": [
    {
      "name": "CategoryDiscountPlugin",
      "class": "app.strategies.promotions.category_discount.CategoryDiscountPlugin",
      "enabled": true,
      "priority": 10
    }
  ]
}
```

---

## Step 3: タスク分解

### 目的

複雑な機能を実装可能なタスクに分解します。

### 手順

1. **タスク分解コマンドを実行**

   ```
   /speckit.tasks
   ```

2. **生成されたタスクを確認**

   > **注意**: 以下はタスク分解の例です。実際には `/speckit.tasks` が生成する内容に従ってください。

   期待されるタスクの概要（サンプル）：

   - **Phase 1**: Setup（環境確認、既存プラグイン調査）
   - **Phase 2**: Foundational（US1: プロモーションマスター管理）
     - Promotion モデル、リポジトリ、API
     - テストデータ作成
   - **Phase 3**: US2（プロモーションエンジン実装）
     - 基底プラグインクラス（commons）
     - CategoryDiscountPlugin 実装
     - プラグインローダー
     - カート計算ロジック統合
   - **Phase 4**: US3（効果測定レポート）
     - レポートプラグイン
   - **Phase 5**: Polish（性能最適化、ドキュメント）

### 依存関係の確認

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← プロモーションマスターが必須
    ↓
Phase 3 (US2) ← プラグインエンジンのコア実装
    ↓
Phase 4 (US3) ← レポート機能
    ↓
Phase 5 (Polish)
```

### チェックポイント

- [ ] プラグイン基底クラスのタスクが最初に定義されている
- [ ] テストタスクが実装タスクより前にある
- [ ] パフォーマンステストが含まれている（カート計算速度）
- [ ] 複数プロモーション重複のテストケースがある

---

## Step 4: 実装

### 目的

プラグインアーキテクチャを使ってプロモーション機能を実装します。

### 手順

1. **実装コマンドを実行**

   ```
   /speckit.implement
   ```

2. **AI が順次実装**

   AI が以下の順序で実装を進めます：

   1. **基底プラグインクラスの作成** （commons または cart/app/strategies/promotions/base）
   2. **プロモーションマスターの実装**
   3. **CategoryDiscountPlugin の実装**
   4. **プラグインローダーの実装**
   5. **カート計算ロジックへの統合**
   6. **テストの作成と実行**

### 実装の詳細

> **注意**: 以下は実装イメージのサンプルです。実際のコードは AI が生成します。

AI が自動的に以下のようなコンポーネントを実装します：

**主な実装内容**:
- **commons または cart**: 基底プラグインクラス `BasePromotionPlugin`
- **master-data サービス**: Promotion モデル、リポジトリ、API
- **cart サービス**: CategoryDiscountPlugin、プラグインローダー、カート計算統合
- **report サービス**: プロモーション効果測定レポートプラグイン

**実装パターン**:
- Strategy パターンによるプラグイン設計
- プラグイン登録・検索・実行の仕組み
- 優先順位制御ロジック
- 割引計算アルゴリズム

### 重要な実装ポイント

#### 1. プラグインの動的ロード

プラグインは設定ファイル（`plugins.json`）から動的にロードされます。

#### 2. 優先順位制御

複数のプラグインが適用可能な場合、優先順位が高いものを選択します。

#### 3. 割引計算の正確性

- パーセンテージ割引: `元の価格 × (1 - 割引率 / 100)`
- 固定額割引: `元の価格 - 割引額`
- 最小価格: 割引後の価格が0円未満にならないよう制御

#### 4. パフォーマンス最適化

- プロモーション検索のキャッシング
- カテゴリマッピングの事前読み込み
- 不要なデータベースクエリの削減

### 進捗確認

実装中、定期的に以下を確認：

```bash
# ファイルが作成されているか確認
ls -la services/cart/app/strategies/promotions/
ls -la services/master-data/app/models/

# 構文エラーがないか確認
cd services/cart
pipenv run python -m py_compile app/strategies/promotions/category_discount.py

# プラグインが登録されているか確認
cat app/plugins.json
```

### トラブルシューティング

**問題**: プラグインがロードされない

**解決**:
1. `plugins.json` の設定を確認
2. クラスパスが正しいか確認
3. `__init__.py` ファイルが存在するか確認

**問題**: 割引計算が正しくない

**解決**:
1. 単体テストで計算ロジックを検証
2. Decimal 型を使用して精度を確保
3. エッジケース（価格0円、割引率100%など）をテスト

**問題**: パフォーマンスが遅い

**解決**:
1. プロモーション検索にインデックスを追加
2. カテゴリマッピングをキャッシュ
3. 不要な N+1 クエリを削減

---

## Step 5: テスト実行

### 目的

実装した機能が正しく動作し、パフォーマンス要件を満たすことを確認します。

### 手順

#### 1. Commons ライブラリの更新

```bash
# プロジェクトルートで実行
./scripts/update_common_and_rebuild.sh
```

#### 2. サービスの再起動

プロジェクトルートで以下を実行：

```bash
# サービスを停止
./scripts/stop.sh

# ビルドして起動（quick_start.sh が全て実行）
./quick_start.sh
```

#### 3. テストの実行

**master-data サービスのテスト**:

```bash
cd services/master-data
./run_all_tests.sh
```

期待される結果:
```
test_promotion.py::test_create_promotion PASSED
test_promotion.py::test_get_promotions PASSED
test_promotion.py::test_update_promotion PASSED
test_promotion.py::test_delete_promotion PASSED

========== 10+ passed ==========
```

**cart サービスのテスト**:

```bash
cd services/cart
./run_all_tests.sh
```

期待される結果:
```
test_category_discount.py::test_apply_category_discount PASSED
test_category_discount.py::test_multiple_promotions_priority PASSED
test_category_discount.py::test_promotion_period_check PASSED
test_category_discount.py::test_discount_calculation PASSED
test_category_discount.py::test_performance PASSED

========== 15+ passed ==========
```

**report サービスのテスト**:

```bash
cd services/report
./run_all_tests.sh
```

#### 4. 統合テスト

プロモーションが正しく適用されるか、エンドツーエンドでテスト：

```bash
# カート作成 → 商品追加 → プロモーション適用確認
cd services/cart
pipenv run pytest tests/test_integration_promotion.py -v
```

#### 5. パフォーマンステスト

```bash
# カート計算の性能テスト
cd services/cart
pipenv run pytest tests/test_performance.py -v
```

期待される結果:
- カート計算時間: < 200ms
- 10商品のカート: < 500ms
- 100件のプロモーション検索: < 100ms

### テスト失敗時の対応

#### デバッグ手順

1. **エラーメッセージの確認**

   ```bash
   # 詳細ログ付きで実行
   cd services/cart
   pipenv run pytest tests/test_category_discount.py -v -s
   ```

2. **サービスログの確認**

   ```bash
   # cart サービスのログ
   cd services
   docker compose logs -f cart
   ```

3. **データベースの確認**

   ```bash
   # MongoDB に接続
   docker exec -it mongodb mongosh

   # プロモーションマスターを確認
   use kugelpos_TENANT001
   db.promotions.find().pretty()
   ```

4. **プラグインロードの確認**

   ```bash
   # プラグイン設定を確認
   cat services/cart/app/plugins.json

   # プラグインがロードされているかログで確認
   docker compose logs cart | grep "promotion"
   ```

#### よくあるエラーと解決方法

**エラー1: プラグインが見つからない**

```
ImportError: cannot import name 'CategoryDiscountPlugin'
```

**解決**:
- クラスパスが正しいか確認
- `__init__.py` にクラスをエクスポート
- `plugins.json` の設定を確認

**エラー2: 割引計算が不正確**

```
AssertionError: expected 900.0, got 900.01
```

**解決**:
- Decimal 型を使用
- 四捨五入の方法を統一（`quantize`）
- 浮動小数点演算を避ける

**エラー3: パフォーマンステスト失敗**

```
AssertionError: Cart calculation took 350ms (expected < 200ms)
```

**解決**:
- プロモーション検索にインデックス追加
- カテゴリマッピングをキャッシュ
- データベースクエリを最適化（N+1問題）
- プラグインロードを1回だけにする

### チェックポイント

全てのテストがパスしたら、以下を確認：

- [ ] master-data サービス: 全テストパス
- [ ] cart サービス: 全テストパス（機能・性能）
- [ ] report サービス: 全テストパス
- [ ] 統合テスト: エンドツーエンドで動作確認
- [ ] パフォーマンステスト: 要件を満たす
- [ ] サービスログにエラーがない

---

## まとめ

### 達成したこと

このハンズオンを通じて、以下を達成しました：

- [ ] プラグインアーキテクチャの設計と実装
- [ ] Strategy パターンの実践的活用
- [ ] 複雑なビジネスロジックの実装
- [ ] ルールエンジンの構築
- [ ] パフォーマンス最適化
- [ ] 拡張可能な設計の実現

### 学んだ高度な技術

#### プラグインアーキテクチャ

- **基底クラス設計**: 共通インターフェースの定義
- **動的ロード**: 設定ファイルからのプラグイン読み込み
- **優先順位制御**: 複数プラグインの実行順序管理
- **拡張性**: 新しいプロモーションタイプの追加が容易

#### ビジネスロジック実装

- **割引計算**: パーセンテージ・固定額の両対応
- **期間判定**: 開始・終了日時のチェック
- **カテゴリ判定**: 商品マスターとの連携
- **優先順位ロジック**: 重複時の自動選択

#### パフォーマンス最適化

- **キャッシング**: プロモーション・カテゴリ情報
- **クエリ最適化**: N+1 問題の回避
- **インデックス設計**: 高速検索のための設計
- **計測**: パフォーマンステストの実装

### 成果物

以下のコンポーネントが作成されました：

```
services/master-data/
├── app/models/promotion.py
├── app/repositories/promotion_repository.py
├── app/services/promotion_service.py
└── tests/test_promotion.py

services/cart/
├── app/strategies/promotions/
│   ├── base_promotion_plugin.py
│   └── category_discount.py
├── app/services/promotion_engine.py
├── app/plugins.json
└── tests/
    ├── test_category_discount.py
    ├── test_promotion_engine.py
    └── test_performance.py

services/report/
├── app/plugins/promotion_report.py
└── tests/test_promotion_report.py
```

### 応用例

このアーキテクチャを使って、他のプロモーションタイプも簡単に追加できます：

1. **商品単位割引**: 特定商品に対する割引
2. **数量割引**: N個以上購入で割引
3. **合計金額割引**: カート合計額に応じた割引
4. **時間帯割引**: ハッピーアワーなど
5. **会員ランク割引**: 会員レベルによる割引

### 次のステップ

さらに機能を拡張するために：

1. **プロモーションコード**: 手動入力でのプロモーション適用
2. **併用ルール**: 複数プロモーションの併用可否設定
3. **除外設定**: 特定商品をプロモーション対象外にする
4. **A/Bテスト**: プロモーション効果の比較実験
5. **レコメンド連携**: プロモーション商品の推奨

### 他の上級機能に挑戦

- [ ] 在庫自動発注機能（バックグラウンド処理、Webhook）
- [ ] 複数支払い方法対応（決済プラグイン拡張）
- [ ] レシート印刷カスタマイズ（テンプレートエンジン）

---

## 参考資料

### デザインパターン

- **Strategy パターン**: プラグインアーキテクチャの基礎
- **Factory パターン**: プラグインの動的生成
- **Chain of Responsibility**: 優先順位処理

### プロジェクトドキュメント

- [プロジェクト憲章](../.specify/memory/constitution.md)
- [CLAUDE.md](../../CLAUDE.md)
- [README.md](../../README.md)

### Kugelpos アーキテクチャ

- プラグインアーキテクチャ（既存の支払い方法プラグイン）
- State Machine パターン（カートサービス）
- Repository パターン（データアクセス）

---

**最終更新**: 2025年11月29日

**作成者**: Kugelpos 開発チーム

**難易度**: 上級（⭐⭐⭐⭐⭐）

**推奨**: 中級ハンズオン完了後に挑戦してください
