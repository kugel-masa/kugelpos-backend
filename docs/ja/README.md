# Kugelpos ドキュメント一覧

Kugelpos POSシステムの日本語ドキュメント一覧です。各カテゴリごとに整理されています。

## 📋 目次

- [Kugelpos ドキュメント一覧](#kugelpos-ドキュメント一覧)
  - [📋 目次](#-目次)
  - [一般ドキュメント](#一般ドキュメント)
  - [共通機能](#共通機能)
  - [サービス別ドキュメント](#サービス別ドキュメント)
    - [Account サービス](#account-サービス)
    - [Cart サービス](#cart-サービス)
    - [Journal サービス](#journal-サービス)
    - [Master Data サービス](#master-data-サービス)
    - [Report サービス](#report-サービス)
    - [Stock サービス](#stock-サービス)
    - [Terminal サービス](#terminal-サービス)
  - [📝 補足情報](#-補足情報)
    - [ドキュメント規約](#ドキュメント規約)
    - [関連リンク](#関連リンク)

---

## 一般ドキュメント

システム全体のアーキテクチャや設計に関するドキュメントです。

- [**アーキテクチャ仕様**](general/architecture.md) - システム全体のアーキテクチャ概要
- [**設定優先順位**](general/configuration-priority.md) - 環境変数と設定ファイルの優先順位
- [**デザインパターン**](general/design-patterns.md) - システムで使用されている設計パターン
- [**エラーコード仕様**](general/error_code_spec.md) - エラーコード体系と一覧
- [**HTTP通信仕様**](general/http-communication.md) - サービス間のHTTP通信規約

## 共通機能

全サービスで共通して使用される機能のドキュメントです。

- [**共通機能仕様書**](commons/common-function-spec.md) - kugel_common ライブラリの詳細仕様

## サービス別ドキュメント

各マイクロサービスのAPI仕様とデータモデル仕様です。

### Account サービス

ユーザー認証とJWTトークン管理を提供するサービスです。

- [**API仕様**](account/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](account/model-specification.md) - データモデルとデータベース構造

### Cart サービス

ショッピングカートとトランザクション処理を管理するサービスです。

- [**API仕様**](cart/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](cart/model-specification.md) - データモデルとステートマシン仕様

### Journal サービス

電子ジャーナル管理機能を提供するサービスです。

- [**API仕様**](journal/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](journal/model-specification.md) - データモデルとイベント処理仕様

### Master Data サービス

商品・店舗・支払方法などのマスタデータを管理するサービスです。

- [**API仕様**](master-data/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](master-data/model-specification.md) - 各種マスタデータのモデル仕様

### Report サービス

各種レポート生成機能を提供するサービスです。

- [**API仕様**](report/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](report/model-specification.md) - レポートデータモデル仕様

### Stock サービス

在庫管理機能を提供するサービスです。

- [**API仕様**](stock/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](stock/model-specification.md) - 在庫データモデル仕様
- [**スナップショット仕様**](stock/snapshot-specification.md) - 在庫スナップショット機能仕様
- [**WebSocket仕様**](stock/websocket-specification.md) - リアルタイム在庫更新のWebSocket仕様

### Terminal サービス

端末管理とAPIキー認証を提供するサービスです。

- [**API仕様**](terminal/api-specification.md) - REST APIエンドポイント仕様
- [**モデル仕様**](terminal/model-specification.md) - 端末データモデル仕様

---

## 📝 補足情報

### ドキュメント規約

- **API仕様**: 各サービスのRESTエンドポイント、リクエスト/レスポンス形式、認証方法を記載
- **モデル仕様**: データベーススキーマ、データモデル定義、ビジネスロジックを記載
- **ファイル名**: すべて小文字、ハイフン区切り（kebab-case）で統一

### 関連リンク

- [英語版ドキュメント](../en/README.md)
- [プロジェクトルート](../../README.md)