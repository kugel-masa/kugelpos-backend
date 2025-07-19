# Kugelposインストールガイド

このガイドでは、Kugelposプロジェクトに必要なすべてのツールのインストール手順を説明します。

## 概要

Kugelposは、以下のツールを必要とするマイクロサービスベースのPOS（Point of Sale）バックエンドシステムです：

- **Python 3.12+** - プログラミング言語ランタイム
- **Docker & Docker Compose** - コンテナランタイムとオーケストレーション
- **Pipenv** - Python依存関係管理
- **Dapr CLI**（オプション）- 分散アプリケーションランタイム

## テスト済み環境

このインストールガイドは以下の環境でテストされています：
- **OS**: Debian GNU/Linux 12 (bookworm)
- **アーキテクチャ**: ARM64 (aarch64)
- **カーネル**: Linux 6.1.0-37-cloud-arm64

## サポート環境

インストールスクリプトはDebianベースのLinuxディストリビューション向けに設計されており、以下の環境に対応しています：
- ネイティブLinux（Debian、Ubuntu）x86_64およびARM64アーキテクチャ
- Windows Subsystem for Linux（WSL1およびWSL2）
  - パフォーマンス向上のためWSL2を推奨
  - Docker Desktop統合サポート
  - WSL環境の自動検出

## クイックインストール

Linuxシステム用の自動インストールスクリプトを提供しています：

```bash
# リポジトリのクローン
git clone https://github.com/kugel-masa/kugelpos-backend.git
cd kugelpos-backend

# インストールスクリプトの実行
./install/install_tools.sh

# シェル設定の変更を適用
source ~/.bashrc
# またはログアウト後、再ログイン

# インストールの確認
./install/verify_installation.sh
```

## 詳細なインストール手順

### 1. システムの前提条件

システムを更新し、ビルド依存関係をインストールします：

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    python3-openssl \
    git
```

### 2. Python 3.12+のインストール

pyenvを使用してPythonバージョンを管理します：

```bash
# pyenvのインストール
curl -fsSL https://pyenv.run | bash

# シェルにpyenvを追加
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

# シェル設定の再読み込み
source ~/.bashrc

# Python 3.12.11のインストール
pyenv install 3.12.11
pyenv global 3.12.11

# インストールの確認
python --version  # Python 3.12.11と表示されるはずです
```

### 3. Dockerのインストール

公式スクリプトを使用してDockerとDocker Composeをインストールします：

```bash
# Dockerインストールスクリプトのダウンロードと実行
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm get-docker.sh

# ユーザーをdockerグループに追加
sudo usermod -aG docker $USER

# グループ変更を有効にするためログアウトして再ログイン
# または実行: newgrp docker

# インストールの確認
docker --version
docker compose version
```

### 4. Pipenvのインストール

Python依存関係管理のためPipenvをインストールします：

```bash
pip install pipenv

# インストールの確認
pipenv --version
```

### 5. Dapr CLIのインストール（オプション）

Daprはオプションですが、分散アプリケーション機能に推奨されます：

```bash
wget -q https://raw.githubusercontent.com/dapr/cli/master/install/install.sh -O - | /bin/bash

# インストールの確認
dapr --version
```

## インストール後の手順

### 1. すべてのインストールの確認

検証スクリプトを実行します：

```bash
./install/verify_installation.sh
```

期待される出力：
```
✓ python: 3.12.11
✓ docker: 28.3.2
✓ docker compose: v2.38.2
✓ pipenv: 2025.0.4
✓ dapr: 1.15.1
```

### 2. Docker設定

「Docker daemon not accessible」エラーが表示される場合：

```bash
# オプション1: Dockerサービスを開始
sudo systemctl start docker
sudo systemctl enable docker  # 起動時の自動開始を有効化

# オプション2: ログアウトせずにグループ変更を適用
newgrp docker
```

### 3. Daprの初期化（オプション）

Daprを使用する場合：

```bash
dapr init
dapr --version
```

## トラブルシューティング

### Python関連の問題

`python --version`が古いバージョンを表示する場合：
```bash
# pyenvが適切に初期化されていることを確認
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

# Python 3.12.11をグローバルに設定
pyenv global 3.12.11
```

### Docker権限の問題

Dockerで「permission denied」エラーが発生する場合：
```bash
# dockerグループに所属していることを確認
groups | grep docker

# 所属していない場合は追加
sudo usermod -aG docker $USER

# 変更を適用
newgrp docker
```

### Pipenvが見つからない

`pipenv`コマンドが見つからない場合：
```bash
# pipが正しいPythonを使用していることを確認
which python
which pip

# pipenvを再インストール
pip install --user pipenv

# 必要に応じてPATHに追加
export PATH="$HOME/.local/bin:$PATH"
```

## 手動インストール（代替方法）

### macOSでのインストール

```bash
# Homebrewがインストールされていない場合はインストール
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# ツールのインストール
brew install python@3.12
brew install --cask docker
brew install pipenv

# Daprのインストール
curl -fsSL https://raw.githubusercontent.com/dapr/cli/master/install/install.sh | /bin/bash
```

### Windowsでのインストール

1. **Python**: [python.org](https://www.python.org/downloads/)からダウンロード
2. **Docker Desktop**: [docker.com](https://www.docker.com/products/docker-desktop)からダウンロード
3. **Pipenv**: コマンドプロンプトで`pip install pipenv`を実行
4. **Dapr**: [dapr.io](https://docs.dapr.io/getting-started/install-dapr-cli/)からダウンロード

## 次のステップ

インストールが成功した後：

1. Kugelposリポジトリをクローン（まだの場合）
2. プロジェクトディレクトリに移動
3. クイックスタートコマンドを実行：

```bash
# scriptsディレクトリに移動
cd scripts

# すべてのサービスをビルド
./build.sh

# すべてのサービスを開始
./start.sh
```

詳細な開発手順については、メインの[README.md](../README.md)と[CLAUDE.md](../CLAUDE.md)ファイルを参照してください。

## サポート

問題が発生した場合：

1. 上記のトラブルシューティングセクションを確認
2. すべてのシステム要件が満たされていることを確認
3. インストール出力のエラーメッセージを確認
4. GitHubのプロジェクトissuesを確認

## バージョン要件のまとめ

| ツール | 最小バージョン | 推奨バージョン |
|------|----------------|---------------------|
| Python | 3.12+ | 3.12.11 |
| Docker | 20.10+ | 最新安定版 |
| Docker Compose | 2.0+ | 最新安定版 |
| Pipenv | 最新版 | 最新安定版 |
| Dapr CLI | 1.10+ | 1.15.1 |

## アンインストール

このガイドでインストールしたツールを削除するには：

```bash
./install/uninstall_tools.sh
```

このスクリプトは以下を実行します：
- Pipenvの削除
- Dapr CLIとランタイムの削除
- DockerとDocker Composeの削除（オプションでデータも含む）
- Python 3.12.11の削除（オプションでpyenvも含む）
- オプションでビルド依存関係の削除

アンインストールスクリプトは、各削除ステップを確認する対話型プロンプトを提供します。

## WSL（Windows Subsystem for Linux）に関する注意

WSLで実行する場合：

### Dockerインストールオプション
1. **Docker Desktop（推奨）**
   - WindowsにDocker Desktopをインストール
   - Docker Desktop設定でWSL2統合を有効化
   - WSLでDockerコマンドがシームレスに動作

2. **WSL内のネイティブDocker**
   - スクリプトを使用してWSLに直接Dockerをインストール
   - 手動でデーモン管理が必要
   - systemdに関する制限がある可能性

### WSLベストプラクティス
- より良いパフォーマンスと互換性のためWSL2を使用
- Windowsドライブ（`/mnt/c/`）ではなくWSLファイルシステム（`/home/`）内で作業
- より良いサービス管理のためWSL2でsystemdを有効化

## 注意事項

- インストールスクリプトはDebianベースのLinuxディストリビューション（Ubuntu、Debian）向けに設計されています
- その他のオペレーティングシステムの場合は、手動インストール手順に従ってください
- Dockerにはroot権限または適切なグループメンバーシップが必要です
- すべてのツールはインストール後に個別に更新できます
- WSLユーザーはネイティブDockerインストールよりDocker Desktop統合を推奨します