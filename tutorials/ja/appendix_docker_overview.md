# Docker と Docker Compose の概要

このドキュメントでは、Kugelpos プロジェクトで使用している Docker と Docker Compose について、図を用いてわかりやすく説明します。

## 目次

- [Docker とは](#docker-とは)
- [コンテナとは](#コンテナとは)
- [Docker の利点](#docker-の利点)
- [Docker イメージとコンテナの関係](#docker-イメージとコンテナの関係)
- [Docker Compose とは](#docker-compose-とは)
- [Kugelpos での利用例](#kugelpos-での利用例)

---

## Docker とは

Docker は、アプリケーションとその依存関係を**コンテナ**という単位でパッケージ化し、どこでも同じように実行できるようにするプラットフォームです。

### 従来の開発環境との比較

```mermaid
graph TB
    subgraph "従来の開発環境"
        A1[開発者Aのマシン]
        A2[OS: macOS]
        A3[Python 3.11]
        A4[MongoDB 5.0]
        A5[動くコード]

        B1[開発者Bのマシン]
        B2[OS: Windows]
        B3[Python 3.9]
        B4[MongoDB 4.4]
        B5[動かないコード❌]

        A1 --> A2 --> A3 --> A4 --> A5
        B1 --> B2 --> B3 --> B4 --> B5
    end

    style A5 fill:#90EE90
    style B5 fill:#FFB6C6
```

```mermaid
graph TB
    subgraph "Docker を使った開発環境"
        C1[開発者Aのマシン]
        C2[Docker]
        C3[コンテナ環境]
        C4[Python 3.12 + MongoDB 7.0]
        C5[動くコード✓]

        D1[開発者Bのマシン]
        D2[Docker]
        D3[同じコンテナ環境]
        D4[Python 3.12 + MongoDB 7.0]
        D5[動くコード✓]

        C1 --> C2 --> C3 --> C4 --> C5
        D1 --> D2 --> D3 --> D4 --> D5
    end

    style C5 fill:#90EE90
    style D5 fill:#90EE90
```

**ポイント**: どの環境でも同じコンテナを使うため、「私のマシンでは動くのに...」という問題が解決されます。

---

## コンテナとは

コンテナは、アプリケーションとその実行に必要なすべて（ライブラリ、設定ファイル、依存関係）を含む**軽量な実行環境**です。

### 仮想マシンとの比較

```mermaid
graph TB
    subgraph "仮想マシン（VM）"
        VM1[ホストOS]
        VM2[ハイパーバイザー]
        VM3[ゲストOS 1]
        VM4[ゲストOS 2]
        VM5[ゲストOS 3]
        VM6[アプリA]
        VM7[アプリB]
        VM8[アプリC]

        VM1 --> VM2
        VM2 --> VM3
        VM2 --> VM4
        VM2 --> VM5
        VM3 --> VM6
        VM4 --> VM7
        VM5 --> VM8
    end

    subgraph "Docker コンテナ"
        DC1[ホストOS]
        DC2[Docker エンジン]
        DC3[コンテナA]
        DC4[コンテナB]
        DC5[コンテナC]
        DC6[アプリA]
        DC7[アプリB]
        DC8[アプリC]

        DC1 --> DC2
        DC2 --> DC3
        DC2 --> DC4
        DC2 --> DC5
        DC3 --> DC6
        DC4 --> DC7
        DC5 --> DC8
    end
```

**違い:**
- **仮想マシン**: 各 VM が完全な OS を持つ（重い、起動が遅い）
- **Docker コンテナ**: ホスト OS のカーネルを共有（軽量、起動が速い）

---

## Docker の利点

### 1. 環境の一貫性

```mermaid
flowchart LR
    A[開発環境] -->|同じDockerイメージ| B[テスト環境]
    B -->|同じDockerイメージ| C[本番環境]

    style A fill:#E1F5FF
    style B fill:#E1F5FF
    style C fill:#E1F5FF
```

### 2. 素早いセットアップ

```mermaid
gantt
    title セットアップ時間の比較
    dateFormat X
    axisFormat %s秒

    section 手動インストール
    Python インストール: 0, 300
    MongoDB インストール: 300, 600
    依存関係インストール: 600, 900
    設定調整: 900, 1200

    section Docker
    docker compose up: 0, 60
```

### 3. クリーンな環境

```mermaid
graph LR
    A[ホストマシン] -->|完全に分離| B[コンテナ1]
    A -->|完全に分離| C[コンテナ2]
    A -->|完全に分離| D[コンテナ3]

    B --> B1[Python 3.12]
    C --> C1[MongoDB 7.0]
    D --> D1[Redis 7.2]

    style A fill:#FFE4B5
    style B fill:#E1F5FF
    style C fill:#E1F5FF
    style D fill:#E1F5FF
```

**ポイント**: ホストマシンを汚さず、コンテナを削除すれば完全にクリーンアップできます。

---

## Docker イメージとコンテナの関係

### イメージとコンテナの概念

```mermaid
graph TB
    subgraph "Dockerfile（設計図）"
        DF[Dockerfile]
    end

    subgraph "Docker イメージ（テンプレート）"
        IMG[kugelpos-cart:latest]
    end

    subgraph "実行中のコンテナ（インスタンス）"
        C1[cart コンテナ 1]
        C2[cart コンテナ 2]
        C3[cart コンテナ 3]
    end

    DF -->|docker build| IMG
    IMG -->|docker run| C1
    IMG -->|docker run| C2
    IMG -->|docker run| C3

    style DF fill:#FFF8DC
    style IMG fill:#E1F5FF
    style C1 fill:#90EE90
    style C2 fill:#90EE90
    style C3 fill:#90EE90
```

**類似例:**
- **Dockerfile** = 家の設計図
- **Docker イメージ** = プレハブ住宅のパーツ
- **コンテナ** = 実際に建てられた家

---

## Docker Compose とは

Docker Compose は、**複数のコンテナを定義・管理**するためのツールです。

### 単一コンテナ vs 複数コンテナ

```mermaid
graph TB
    subgraph "単一コンテナ（Docker）"
        DC1[docker run コマンド]
        DC2[1つのコンテナ起動]
    end

    subgraph "複数コンテナ（Docker Compose）"
        DCC1[docker compose up コマンド]
        DCC2[複数のコンテナを一括起動]
        DCC3[コンテナ1]
        DCC4[コンテナ2]
        DCC5[コンテナ3]
        DCC6[コンテナ4]

        DCC1 --> DCC2
        DCC2 --> DCC3
        DCC2 --> DCC4
        DCC2 --> DCC5
        DCC2 --> DCC6
    end

    DC1 --> DC2
```

### docker-compose.yaml の役割

```mermaid
graph TB
    YAML[docker-compose.yaml<br/>サービス定義ファイル]

    YAML --> S1[cart サービス]
    YAML --> S2[master-data サービス]
    YAML --> S3[mongodb サービス]
    YAML --> S4[redis サービス]

    S1 --> C1[cart コンテナ]
    S2 --> C2[master-data コンテナ]
    S3 --> C3[mongodb コンテナ]
    S4 --> C4[redis コンテナ]

    C1 -.ネットワーク.-> C3
    C1 -.ネットワーク.-> C4
    C2 -.ネットワーク.-> C3

    style YAML fill:#FFF8DC
    style C1 fill:#E1F5FF
    style C2 fill:#E1F5FF
    style C3 fill:#90EE90
    style C4 fill:#90EE90
```

**ポイント**: docker-compose.yaml に定義するだけで、複数のコンテナとそのネットワークが自動的に構築されます。

---

## Kugelpos での利用例

### アーキテクチャ全体像

```mermaid
graph TB
    subgraph "Docker Compose 管理"
        subgraph "マイクロサービス群"
            ACCOUNT[account<br/>ポート: 8000]
            TERMINAL[terminal<br/>ポート: 8001]
            MASTER[master-data<br/>ポート: 8002]
            CART[cart<br/>ポート: 8003]
            REPORT[report<br/>ポート: 8004]
            JOURNAL[journal<br/>ポート: 8005]
            STOCK[stock<br/>ポート: 8006]
        end

        subgraph "データストア"
            MONGO[(MongoDB<br/>ポート: 27017)]
            REDIS[(Redis<br/>ポート: 6379)]
        end

        subgraph "通信基盤"
            DAPR[Dapr Sidecar]
        end
    end

    ACCOUNT --> MONGO
    TERMINAL --> MONGO
    MASTER --> MONGO
    CART --> MONGO
    REPORT --> MONGO
    JOURNAL --> MONGO
    STOCK --> MONGO

    CART --> REDIS
    REPORT --> REDIS

    ACCOUNT -.Dapr.-> DAPR
    TERMINAL -.Dapr.-> DAPR
    CART -.Dapr.-> DAPR
    REPORT -.Dapr.-> DAPR

    style ACCOUNT fill:#E1F5FF
    style TERMINAL fill:#E1F5FF
    style MASTER fill:#E1F5FF
    style CART fill:#E1F5FF
    style REPORT fill:#E1F5FF
    style JOURNAL fill:#E1F5FF
    style STOCK fill:#E1F5FF
    style MONGO fill:#90EE90
    style REDIS fill:#90EE90
    style DAPR fill:#FFE4B5
```

### サービス起動フロー

```mermaid
sequenceDiagram
    participant User as 開発者
    participant DC as Docker Compose
    participant Mongo as MongoDB コンテナ
    participant Redis as Redis コンテナ
    participant Cart as Cart サービス
    participant Report as Report サービス

    User->>DC: docker compose up
    activate DC

    DC->>Mongo: MongoDB 起動
    activate Mongo
    Mongo-->>DC: 起動完了

    DC->>Redis: Redis 起動
    activate Redis
    Redis-->>DC: 起動完了

    DC->>Cart: Cart サービス起動
    activate Cart
    Cart->>Mongo: DB接続確認
    Mongo-->>Cart: 接続OK
    Cart-->>DC: 起動完了

    DC->>Report: Report サービス起動
    activate Report
    Report->>Mongo: DB接続確認
    Mongo-->>Report: 接続OK
    Report->>Redis: キャッシュ接続
    Redis-->>Report: 接続OK
    Report-->>DC: 起動完了

    DC-->>User: 全サービス起動完了
    deactivate DC
```

### 主要な Docker Compose コマンド

```mermaid
graph LR
    subgraph "開発ワークフロー"
        A[docker compose build] -->|イメージ作成| B[docker compose up]
        B -->|サービス起動| C[開発・テスト]
        C -->|ログ確認| D[docker compose logs]
        C -->|停止| E[docker compose down]
        E -->|再起動| B
    end

    style A fill:#FFF8DC
    style B fill:#90EE90
    style C fill:#E1F5FF
    style D fill:#FFE4B5
    style E fill:#FFB6C6
```

### Kugelpos での実際の使用例

```bash
# すべてのサービスをビルド
docker compose build

# すべてのサービスを起動（バックグラウンド）
docker compose up -d

# 特定のサービスのログを確認
docker compose logs -f cart

# サービスの状態を確認
docker compose ps

# 特定のサービスを再起動
docker compose restart cart

# すべてのサービスを停止・削除
docker compose down

# データも含めてすべて削除
docker compose down -v
```

---

## まとめ

### Docker の利点
- ✅ 環境の一貫性（開発・テスト・本番で同じ）
- ✅ 素早いセットアップ（数分で完全な環境構築）
- ✅ クリーンな環境（ホストマシンを汚さない）
- ✅ チーム間での環境共有が容易

### Docker Compose の利点
- ✅ 複数サービスを一括管理
- ✅ YAML ファイルで宣言的に定義
- ✅ ネットワークとボリュームを自動構築
- ✅ 簡単なコマンドで起動・停止

### Kugelpos での使い方

```mermaid
graph LR
    A[1. リポジトリクローン] --> B[2. docker compose build]
    B --> C[3. docker compose up]
    C --> D[4. ブラウザで確認<br/>localhost:8003]
    D --> E[5. 開発・テスト]
    E --> F[6. docker compose down]

    style A fill:#FFF8DC
    style B fill:#FFE4B5
    style C fill:#90EE90
    style D fill:#E1F5FF
    style E fill:#E1F5FF
    style F fill:#FFB6C6
```

---

## 参考リンク

- Docker 公式ドキュメント: https://docs.docker.com/
- Docker Compose 公式ドキュメント: https://docs.docker.com/compose/
- Kugelpos プロジェクト CLAUDE.md: [../../CLAUDE.md](../../CLAUDE.md)

---

**最終更新**: 2025年11月30日
