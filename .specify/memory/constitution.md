# Kugelpos Backend Constitution

## Core Principles

### I. マイクロサービスアーキテクチャ（必須・変更不可）
- 7つのコアサービス（account, terminal, master-data, cart, report, journal, stock）で構成
- 各サービスは独立してデプロイ可能
- サービス間通信はDaprを使用
- データベースはテナント毎に分離（マルチテナント対応）

### II. テストファースト開発（必須・変更不可）
- すべての機能実装前にテストを作成
- テスト実行順序: `test_clean_data.py` → `test_setup_data.py` → 機能テスト
- 非同期テストには `pytest-asyncio` を使用
- テストカバレッジを維持

### III. サーキットブレーカーパターン（必須・変更不可）
- 外部HTTP呼び出しには `HttpClientHelper` を使用
- Dapr通信には `DaprClientHelper` を使用
- 失敗閾値: 3回の連続失敗でサーキットオープン
- タイムアウト: 60秒後にhalf-open状態へ移行

### IV. イベント駆動通信
- トランザクションログはDapr pub/subで配信
- トピック: `tranlog_report`, `tranlog_status`, `cashlog_report`, `opencloselog_report`
- 非同期処理により疎結合を実現

### V. プラグインアーキテクチャ
- Cart: 支払い方法プラグイン（`/services/strategies/payments/`）
- Report: レポート生成プラグイン（`/services/plugins/`）
- プラグインは `plugins.json` で設定

### VI. 共通ライブラリ（commons）
- データベース抽象化（`AbstractRepository`, `AbstractDocument`）
- 例外処理とエラーコード（XXYYZZ形式）
- 認証・セキュリティユーティリティ
- HTTPクライアントヘルパー（`HttpClientHelper`, `DaprClientHelper`）

## 言語ポリシー

### ドキュメント言語
**すべてのSpecify成果物は日本語で作成すること（必須・変更不可）**

以下のドキュメントは日本語で作成：
- 仕様書（spec.md）
- 実装計画書（plan.md）
- タスク定義（tasks.md）
- チェックリスト（checklist.md）
- README とガイド
- コード内のコメント
- コミットメッセージ

### コード言語
以下は英語を使用すること：
- 変数名（例: `user_name`, `total_amount`, `is_deleted`）
- 関数名（例: `calculate_total`, `validate_input`, `delete_category_async`）
- クラス名（例: `CategoryMasterDocument`, `CartService`, `PaymentProcessor`）
- ファイル名（例: `category_master_service.py`, `cart_state_manager.py`）

### 理由
- ドキュメントを日本語にすることで、日本人開発者の理解を促進
- コードを英語にすることで、国際的な保守性とツールの互換性を確保
- この組み合わせにより、ローカルチームの効率と国際標準の両立を実現

## 技術標準

### プログラミング言語
- Python 3.12+ with FastAPI
- 非同期処理（async/await）を使用
- 型ヒント（type hints）を使用

### データベース
- MongoDB（Motor async driver）
- コレクション名は snake_case
- ドキュメントは `BaseDocumentModel` を継承
- リポジトリパターンを使用

### API規約
- エンドポイントはバージョン管理: `/api/v1/`
- Pydanticスキーマを使用
- Transformerクラスで内部モデルとAPIスキーマを変換
- OpenAPI自動生成

### エラーコード
- XXYYZZ形式（XX: サービス識別子、YY: 機能識別子、ZZ: 特定エラー番号）
- 例: 10=account, 20=terminal, 30=cart, 40=report, 50=journal, 60=stock, 70=master-data

### セキュリティ
- シークレット・APIキーをコミットしない
- 環境変数で設定管理
- APIキーはハッシュ化して保存
- すべてのエンドポイントで入力検証

## コード品質

### コーディング規約
- PEP 8に準拠
- 関数パラメータと戻り値に型ヒントを使用
- すべてのDB操作は非同期パターン
- コメントアウトされたコードを本番環境に含めない

### Git規約
- コミットメッセージは英語
- ブランチ命名: `feature/*`, `bugfix/*`, `hotfix/*`
- PRの説明は「why」を説明（「what」だけでなく）

## 可観測性とデバッグ

### ログ
- 構造化ログを使用
- ログメッセージは英語または日本語
- 重要な処理フローをログに記録

### ヘルスチェック
- 各サービスに `/health` エンドポイント
- Dapr接続状態を確認

### モニタリング
- サーキットブレーカーの状態を監視
- パフォーマンスメトリクスを収集

## 開発ワークフロー

### 新機能開発
1. Specify: `/speckit.specify` で仕様を作成（日本語）
2. Clarify: `/speckit.clarify` で曖昧さを明確化（必要に応じて）
3. Plan: `/speckit.plan` で実装計画を作成（日本語）
4. Tasks: `/speckit.tasks` でタスクに分解（日本語）
5. Implement: `/speckit.implement` で実装

### テスト実行
```bash
# 特定サービスのテスト
cd services/cart
./run_all_tests.sh

# すべてのサービスのテスト
./scripts/run_all_tests.sh
```

### ビルドとデプロイ
```bash
# サービスのビルド
./scripts/build.sh cart

# すべてのサービスを起動
./scripts/start.sh

# すべてのサービスを停止
./scripts/stop.sh
```

## Governance

### 憲章の優先順位
- この憲章はすべての開発プラクティスに優先する
- 「必須・変更不可」と明記された原則は例外なく遵守すること
- その他の原則は正当な理由があれば変更可能

### 憲章の修正
- 修正には文書化、承認、移行計画が必要
- 「必須・変更不可」原則の修正には特別な承認が必要

### コンプライアンス
- すべてのPR/レビューは憲章への準拠を確認
- 複雑性の追加には正当化が必要
- 疑問がある場合はCLAUDE.mdを参照

**Version**: 1.0.0 | **Ratified**: 2025-12-08 | **Last Amended**: 2025-12-08
