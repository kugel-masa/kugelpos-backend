# ハンズオン事前準備

本ハンズオンに参加するために、以下を事前にご準備ください。

## 1. GitHub アカウント（Codespaces が利用できるもの）

GitHub Codespaces を使用するため、GitHub アカウントが必要です。

### 取得方法

- GitHub アカウントをお持ちでない場合: https://github.com/signup
- 既存のアカウントで Codespaces が利用可能か確認: https://github.com/codespaces

### Codespaces 無料枠

- 個人アカウント: 月60時間（2コア環境）
- 詳細: https://docs.github.com/ja/billing/managing-billing-for-github-codespaces/about-billing-for-github-codespaces

### リポジトリのフォーク

本ハンズオンでは、Kugelpos リポジトリをフォークして作業します。

1. リポジトリページにアクセス: https://github.com/kugel-masa/kugelpos-backend
2. 画面右上の「Fork」ボタンをクリック
3. 自分のアカウントにリポジトリがコピーされます
4. フォークしたリポジトリで Codespaces を起動します

**注意**: Public リポジトリなので、アクセス権限のリクエストは不要です。

## 2. Visual Studio Code

GitHub Codespaces に接続するため、Visual Studio Code をローカル環境にインストールしてください。

### インストール方法

公式サイトからダウンロード: https://code.visualstudio.com/

### 対応 OS

- Windows
- macOS
- Linux

## 3. Claude Code 利用ライセンス

AI 支援開発ツール Claude Code を使用するため、以下のいずれかが必要です。

### オプション1: Anthropic API キー（推奨）

1. Anthropic Console にアクセス: https://console.anthropic.com/
2. サインアップまたはログイン
3. API Keys セクションで新しい API キーを作成
4. API キーをコピーして安全に保管

**注意**: API 使用料金は従量課金制です。クレジットカードの登録が必要です。

### オプション2: その他の利用可能なライセンス

Claude Code が利用できる他のライセンスをお持ちの場合は、そちらをご利用いただけます。

---

## 確認事項

ハンズオン開始前に、以下が準備できているか確認してください：

- [ ] GitHub アカウントを持っている
- [ ] GitHub Codespaces が利用可能である
- [ ] Kugelpos リポジトリをフォークしている
- [ ] Visual Studio Code がインストール済みである
- [ ] Claude Code の API キー（または利用ライセンス）を取得している

---

**次のステップ**: [Claude Code インストール手順](01_claude_code_installation.md)
