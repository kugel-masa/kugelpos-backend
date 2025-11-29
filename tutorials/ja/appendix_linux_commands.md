# ハンズオンで使う Linux コマンド

このドキュメントでは、Kugelpos ハンズオンで使用する Linux コマンドについて説明します。

## 目次

- [ファイル・ディレクトリ操作](#ファイルディレクトリ操作)
- [ファイル内容の表示・編集](#ファイル内容の表示編集)
- [プロセス管理](#プロセス管理)
- [ネットワーク操作](#ネットワーク操作)
- [Docker コマンド](#docker-コマンド)
- [Git コマンド](#git-コマンド)
- [パイプとリダイレクト](#パイプとリダイレクト)
- [便利なショートカット](#便利なショートカット)
- [ハンズオンでよく使うコマンド](#ハンズオンでよく使うコマンド)

---

## ファイル・ディレクトリ操作

### pwd - 現在のディレクトリを表示

現在いる場所（カレントディレクトリ）のパスを表示します。

```bash
pwd
# 出力例: /home/masa/proj/kugelpos-public/worktree/ai-coding-lesson
```

### ls - ファイル一覧を表示

ディレクトリ内のファイルとサブディレクトリを一覧表示します。

```bash
# 基本的な使い方
ls

# 詳細情報を表示
ls -l

# 隠しファイルも含めて詳細表示
ls -la

# 人間が読みやすい形式でサイズ表示
ls -lh
```

**主なオプション:**

- `-l`: 詳細情報（権限、サイズ、更新日時など）を表示
- `-a`: 隠しファイル（`.` で始まるファイル）も表示
- `-h`: ファイルサイズを人間が読みやすい形式（KB, MB, GB）で表示
- `-t`: 更新日時順に並べ替え
- `-r`: 逆順で表示

**出力例:**

```bash
$ ls -lh
total 24K
drwxr-xr-x 3 masa masa 4.0K Nov 30 00:06 ja
-rw-r--r-- 1 masa masa 8.7K Nov 30 00:05 README.md
drwxr-xr-x 2 masa masa 4.0K Nov 29 23:16 specs
```

### cd - ディレクトリを移動

指定したディレクトリに移動します。

```bash
# 特定のディレクトリに移動
cd tutorials

# 親ディレクトリに移動
cd ..

# ホームディレクトリに移動
cd ~
cd

# 前のディレクトリに戻る
cd -

# 絶対パスで移動
cd /home/masa/proj/kugelpos-public
```

**パスの種類:**

- **絶対パス**: ルート（`/`）から始まるパス（例: `/home/masa/proj`）
- **相対パス**: 現在地からの相対的なパス（例: `../tutorials`）

### mkdir - ディレクトリを作成

新しいディレクトリを作成します。

```bash
# ディレクトリを作成
mkdir new-directory

# 親ディレクトリも含めて一括作成
mkdir -p path/to/new/directory
```

**オプション:**

- `-p`: 必要な親ディレクトリも同時に作成（存在する場合はエラーにしない）

### cp - ファイル・ディレクトリをコピー

ファイルやディレクトリをコピーします。

```bash
# ファイルをコピー
cp source.txt destination.txt

# ディレクトリを再帰的にコピー
cp -r source-dir/ destination-dir/

# 上書き前に確認
cp -i source.txt destination.txt
```

**主なオプション:**

- `-r`: ディレクトリを再帰的にコピー
- `-i`: 上書き前に確認
- `-v`: 処理内容を表示

### mv - ファイル・ディレクトリを移動/リネーム

ファイルやディレクトリを移動、またはリネームします。

```bash
# ファイルをリネーム
mv old-name.txt new-name.txt

# ファイルを別のディレクトリに移動
mv file.txt /path/to/directory/

# ディレクトリをリネーム
mv old-dir new-dir
```

**主なオプション:**

- `-i`: 上書き前に確認
- `-v`: 処理内容を表示

### rm - ファイル・ディレクトリを削除

ファイルやディレクトリを削除します。

```bash
# ファイルを削除
rm file.txt

# 複数のファイルを削除
rm file1.txt file2.txt

# ディレクトリを再帰的に削除
rm -r directory/

# 確認なしで強制削除（危険！）
rm -rf directory/
```

**⚠️ 警告:**

- `rm` で削除したファイルは復元できません
- `rm -rf` は非常に強力で危険です。使用時は十分注意してください
- 特に `rm -rf /` や `rm -rf /*` は絶対に実行しないでください

**主なオプション:**

- `-r`: ディレクトリを再帰的に削除
- `-f`: 確認せずに強制削除
- `-i`: 削除前に確認

---

## ファイル内容の表示・編集

### cat - ファイル内容を表示

ファイルの内容を標準出力に表示します。

```bash
# ファイル全体を表示
cat file.txt

# 複数ファイルを連結して表示
cat file1.txt file2.txt

# 行番号付きで表示
cat -n file.txt
```

**使用例:**

```bash
$ cat README.md
# Kugelpos Tutorial
This is a tutorial for...
```

### less - ファイル内容をページ単位で表示

ファイルの内容をページ単位で表示します。大きなファイルを見る際に便利です。

```bash
# ファイルをページ単位で表示
less file.txt

# ログファイルを表示
less /var/log/syslog
```

**操作キー:**

- `スペース`: 次のページ
- `b`: 前のページ
- `/検索語`: 前方検索
- `?検索語`: 後方検索
- `n`: 次の検索結果
- `N`: 前の検索結果
- `q`: 終了

### head - ファイルの先頭を表示

ファイルの先頭部分を表示します。

```bash
# 先頭10行を表示（デフォルト）
head file.txt

# 先頭20行を表示
head -n 20 file.txt

# 先頭5行を表示
head -5 file.txt
```

### tail - ファイルの末尾を表示

ファイルの末尾部分を表示します。ログファイルの監視に便利です。

```bash
# 末尾10行を表示（デフォルト）
tail file.txt

# 末尾20行を表示
tail -n 20 file.txt

# リアルタイムでログを監視（追記されたら表示）
tail -f logfile.log

# Ctrl+C で監視を終了
```

**使用例:**

```bash
# Docker ログをリアルタイム監視
tail -f /var/log/docker.log
```

### grep - 文字列を検索

ファイル内やコマンド出力から特定の文字列を検索します。

```bash
# ファイル内で文字列を検索
grep "search-term" file.txt

# 大文字小文字を区別せず検索
grep -i "error" logfile.txt

# ディレクトリ内を再帰的に検索
grep -r "TODO" ./src/

# 行番号を表示
grep -n "error" logfile.txt

# マッチした行の前後も表示
grep -C 3 "error" logfile.txt  # 前後3行
grep -A 2 "error" logfile.txt  # 後2行
grep -B 2 "error" logfile.txt  # 前2行
```

**主なオプション:**

- `-i`: 大文字小文字を区別しない
- `-r`: ディレクトリを再帰的に検索
- `-n`: 行番号を表示
- `-v`: マッチしない行を表示（反転）
- `-l`: マッチしたファイル名のみ表示
- `-c`: マッチした行数をカウント

---

## プロセス管理

### ps - プロセス一覧を表示

実行中のプロセスを表示します。

```bash
# 現在のターミナルのプロセスを表示
ps

# すべてのプロセスを詳細表示
ps aux

# 特定のプロセスを検索
ps aux | grep python

# プロセスツリー表示
ps auxf
```

**出力例:**

```bash
$ ps aux | grep python
masa    1234  2.5  1.5 150000 15000 ?  S  10:00  0:30 python app.py
```

**フィールドの意味:**

- `USER`: プロセスの所有者
- `PID`: プロセスID
- `%CPU`: CPU使用率
- `%MEM`: メモリ使用率
- `VSZ`: 仮想メモリサイズ
- `RSS`: 物理メモリサイズ
- `STAT`: プロセスの状態

### top - リアルタイムでプロセスを監視

システムのリソース使用状況とプロセスをリアルタイム表示します。

```bash
# リアルタイムでプロセスを監視
top

# 更新間隔を指定（秒）
top -d 5
```

**操作キー:**

- `q`: 終了
- `k`: プロセスを終了（PIDを入力）
- `M`: メモリ使用率順に並べ替え
- `P`: CPU使用率順に並べ替え
- `1`: CPU コアごとに表示

### kill - プロセスを終了

プロセスにシグナルを送信してプロセスを終了します。

```bash
# プロセスIDを指定して終了
kill 1234

# 強制終了
kill -9 1234

# プロセス名で終了
pkill python

# 確認しながら終了
pkill -i python
```

**主なシグナル:**

- `SIGTERM (15)`: 正常終了を要求（デフォルト）
- `SIGKILL (9)`: 強制終了（プロセスは対処できない）
- `SIGHUP (1)`: 再起動

---

## ネットワーク操作

### curl - HTTP リクエストを送信

HTTP/HTTPS リクエストを送信してレスポンスを取得します。

```bash
# GETリクエスト
curl http://localhost:8003/health

# POSTリクエスト（JSONデータ）
curl -X POST http://localhost:8003/api/v1/carts \
  -H "Content-Type: application/json" \
  -d '{"tenant_code": "TENANT01"}'

# レスポンスヘッダーも表示
curl -i http://localhost:8003/health

# レスポンスをファイルに保存
curl -o output.json http://localhost:8003/api/v1/carts

# 詳細な通信情報を表示
curl -v http://localhost:8003/health
```

**主なオプション:**

- `-X`: HTTPメソッドを指定（GET, POST, PUT, DELETE など）
- `-H`: ヘッダーを追加
- `-d`: リクエストボディ（データ）を指定
- `-i`: レスポンスヘッダーも表示
- `-o`: 出力をファイルに保存
- `-v`: 詳細な通信情報を表示

### ping - ネットワーク疎通を確認

指定したホストへの疎通を確認します。

```bash
# ホストへの疎通確認
ping google.com

# 4回だけ送信
ping -c 4 google.com

# 間隔を指定（秒）
ping -i 2 google.com
```

**Ctrl+C で停止**

---

## Docker コマンド

### docker ps - コンテナ一覧を表示

実行中の Docker コンテナを表示します。

```bash
# 実行中のコンテナを表示
docker ps

# すべてのコンテナを表示（停止中も含む）
docker ps -a

# コンテナIDのみ表示
docker ps -q
```

**出力例:**

```bash
CONTAINER ID   IMAGE              STATUS         PORTS                    NAMES
abc123def456   kugelpos-cart      Up 2 hours     0.0.0.0:8003->8003/tcp   cart
```

### docker logs - コンテナのログを表示

コンテナの標準出力・エラー出力を表示します。

```bash
# コンテナのログを表示
docker logs cart

# リアルタイムでログを追跡
docker logs -f cart

# 最新100行のログを表示
docker logs --tail 100 cart

# タイムスタンプ付きで表示
docker logs -t cart
```

**主なオプション:**

- `-f`: リアルタイムで追跡（follow）
- `--tail N`: 最新N行のみ表示
- `-t`: タイムスタンプを表示
- `--since`: 指定時刻以降のログを表示

### docker exec - コンテナ内でコマンドを実行

実行中のコンテナ内でコマンドを実行します。

```bash
# コンテナ内でコマンド実行
docker exec cart ls -la

# コンテナ内でシェルを起動（対話モード）
docker exec -it cart bash

# MongoDB コンテナに接続
docker exec -it mongodb mongosh

# root ユーザーで実行
docker exec -u root -it cart bash
```

**主なオプション:**

- `-i`: 標準入力を開いたままにする（interactive）
- `-t`: 疑似TTYを割り当てる（tty）
- `-u`: 実行ユーザーを指定

### docker compose - 複数コンテナを管理

docker-compose.yaml に定義された複数のコンテナを管理します。

```bash
# すべてのサービスをビルド
docker compose build

# すべてのサービスを起動（バックグラウンド）
docker compose up -d

# すべてのサービスを起動（フォアグラウンド）
docker compose up

# 特定のサービスのログを表示
docker compose logs -f cart

# サービスの状態を確認
docker compose ps

# 特定のサービスを再起動
docker compose restart cart

# すべてのサービスを停止・削除
docker compose down

# データボリュームも含めて削除
docker compose down -v
```

**主なコマンド:**

- `build`: イメージをビルド
- `up`: サービスを起動
- `down`: サービスを停止・削除
- `ps`: サービスの状態を表示
- `logs`: ログを表示
- `restart`: サービスを再起動
- `exec`: コンテナ内でコマンド実行

---

## Git コマンド

### git status - 変更状態を確認

現在の変更状態を確認します。

```bash
git status
```

**出力例:**

```bash
On branch main
Changes not staged for commit:
  modified:   app/main.py

Untracked files:
  app/new_feature.py
```

### git add - 変更をステージング

変更をステージングエリアに追加します（コミット対象として登録）。

```bash
# 特定のファイルを追加
git add file.txt

# すべての変更を追加
git add .

# 特定のディレクトリ配下を追加
git add app/

# 対話的に追加
git add -p
```

### git commit - 変更を記録

ステージングエリアの変更をリポジトリに記録します。

```bash
# コミットメッセージを指定
git commit -m "feat: Add new feature"

# エディタでメッセージを編集
git commit

# 変更の追加とコミットを同時に実行
git commit -am "fix: Fix bug"
```

**コミットメッセージの規約:**

- `feat:` 新機能
- `fix:` バグ修正
- `docs:` ドキュメント変更
- `refactor:` リファクタリング
- `test:` テスト追加・修正

### git push - リモートに送信

ローカルの変更をリモートリポジトリに送信します。

```bash
# 現在のブランチをリモートに送信
git push

# 初回プッシュ時（ブランチを追跡設定）
git push -u origin main

# 強制プッシュ（危険！）
git push -f
```

### git pull - リモートから取得

リモートリポジトリの変更を取得してマージします。

```bash
# リモートの変更を取得してマージ
git pull

# 特定のブランチから取得
git pull origin main
```

### git log - コミット履歴を表示

コミット履歴を表示します。

```bash
# コミット履歴を表示
git log

# 1行で表示
git log --oneline

# 最新5件のみ表示
git log -5

# グラフ形式で表示
git log --graph --oneline
```

---

## パイプとリダイレクト

### パイプ（|）

あるコマンドの出力を次のコマンドの入力として渡します。

```bash
# プロセス一覧からpythonを検索
ps aux | grep python

# ログからerrorを検索して件数を表示
docker logs cart | grep error | wc -l

# ファイル一覧をページ単位で表示
ls -la | less

# ファイル一覧を並べ替え
ls -l | sort -k5 -n
```

**使用例:**

```bash
# Docker コンテナのログから ERROR を含む行を抽出し、件数をカウント
docker logs cart | grep ERROR | wc -l
```

### リダイレクト（>、>>）

コマンドの出力をファイルに保存します。

```bash
# 出力をファイルに保存（上書き）
docker logs cart > cart.log

# 出力をファイルに追記
docker logs cart >> cart.log

# エラー出力をファイルに保存
command 2> error.log

# 標準出力とエラー出力を両方保存
command > output.log 2>&1

# 出力を破棄
command > /dev/null 2>&1
```

**記号の意味:**

- `>`: 標準出力をファイルに保存（上書き）
- `>>`: 標準出力をファイルに追記
- `2>`: エラー出力をファイルに保存
- `2>&1`: エラー出力を標準出力にリダイレクト

---

## 便利なショートカット

### キーボードショートカット

ターミナルで使える便利なショートカットキーです。

| ショートカット | 機能 |
|--------------|------|
| `Ctrl + C` | 実行中のコマンドを中断（終了） |
| `Ctrl + D` | 入力終了 / ログアウト |
| `Ctrl + Z` | プロセスを一時停止（バックグラウンドに移動） |
| `Ctrl + L` | 画面をクリア（`clear` コマンドと同じ） |
| `Ctrl + R` | コマンド履歴を検索（インクリメンタルサーチ） |
| `Ctrl + A` | 行頭に移動 |
| `Ctrl + E` | 行末に移動 |
| `Ctrl + U` | カーソル位置から行頭まで削除 |
| `Ctrl + K` | カーソル位置から行末まで削除 |
| `Ctrl + W` | カーソル位置の前の単語を削除 |
| `Tab` | コマンド・ファイル名の補完 |
| `↑` / `↓` | コマンド履歴を表示 |

### Tab 補完

Tab キーを押すことで、コマンドやファイル名を自動補完できます。

```bash
# "doc" まで入力して Tab を押すと...
$ cd doc[Tab]
$ cd docker/

# 候補が複数ある場合は Tab を2回押すと一覧表示
$ cd d[Tab][Tab]
data/  docker/  downloads/
```

### コマンド履歴検索

`Ctrl + R` でコマンド履歴を検索できます。

```bash
# Ctrl+R を押すと検索モードになる
(reverse-i-search)`doc': docker compose up -d

# さらに文字を入力して絞り込み
(reverse-i-search)`docker log': docker logs -f cart

# Enter で実行、Ctrl+C でキャンセル
```

### エイリアス（よく使うコマンドの短縮）

よく使うコマンドを短縮して登録できます。

```bash
# エイリアスを設定
alias ll='ls -la'
alias dc='docker compose'
alias dps='docker ps'
alias gs='git status'

# エイリアスを使用
ll              # ls -la と同じ
dc up -d        # docker compose up -d と同じ
dps             # docker ps と同じ
gs              # git status と同じ

# エイリアスを永続化（~/.bashrc または ~/.zshrc に追加）
echo "alias ll='ls -la'" >> ~/.bashrc
source ~/.bashrc
```

---

## ハンズオンでよく使うコマンド

### 1. サービス起動とログ確認

```bash
# プロジェクトディレクトリに移動
cd /home/masa/proj/kugelpos-public/worktree/ai-coding-lesson

# サービスを起動
docker compose up -d

# すべてのサービスの状態を確認
docker compose ps

# 特定のサービスのログをリアルタイム監視
docker compose logs -f cart

# 複数のサービスのログを監視
docker compose logs -f cart master-data
```

### 2. エラー調査

```bash
# ログからエラーを検索
docker logs cart | grep -i error

# エラー行数をカウント
docker logs cart | grep -i error | wc -l

# エラーをファイルに保存
docker logs cart | grep -i error > cart-errors.log

# 最新100行のログからエラーを検索
docker logs --tail 100 cart | grep -i error
```

### 3. データベース確認

```bash
# MongoDB に接続
docker exec -it mongodb mongosh

# MongoDB 内でコマンド実行（mongosh シェル内）
use TENANT01_kugelpos
db.carts.find().limit(5)
db.carts.countDocuments()
exit
```

### 4. ファイル編集後の確認

```bash
# ファイルを編集後、構文チェック
python -m py_compile app/main.py

# サービスを再ビルド
docker compose build cart

# サービスを再起動
docker compose restart cart

# ログで起動を確認
docker compose logs -f cart
```

### 5. Git ワークフロー

```bash
# 変更を確認
git status

# 変更内容を確認
git diff

# 変更を追加
git add .

# コミット
git commit -m "feat: Add new feature"

# リモートにプッシュ
git push

# コミット履歴を確認
git log --oneline -5
```

### 6. テスト実行

```bash
# サービスディレクトリに移動
cd services/cart

# テストを実行
pipenv run pytest tests/ -v

# 特定のテストファイルを実行
pipenv run pytest tests/test_cart.py -v

# カバレッジ付きでテスト実行
pipenv run pytest --cov=app tests/
```

---

## まとめ

### 最低限覚えるべきコマンド

| カテゴリ | コマンド | 用途 |
|---------|---------|------|
| **ナビゲーション** | `pwd` | 現在地確認 |
| | `ls -la` | ファイル一覧（詳細・隠しファイル含む） |
| | `cd <dir>` | ディレクトリ移動 |
| **ファイル操作** | `cat <file>` | ファイル内容表示 |
| | `less <file>` | ファイルをページ単位で表示 |
| | `grep <pattern> <file>` | 文字列検索 |
| **Docker** | `docker compose up -d` | サービスを起動 |
| | `docker compose logs -f <service>` | ログをリアルタイム監視 |
| | `docker compose down` | サービスを停止 |
| | `docker exec -it <container> bash` | コンテナ内でシェル起動 |
| **Git** | `git status` | 変更状態確認 |
| | `git add .` | すべての変更を追加 |
| | `git commit -m "<message>"` | コミット |
| | `git push` | リモートにプッシュ |
| **その他** | `Ctrl + C` | コマンド中断 |
| | `Ctrl + R` | コマンド履歴検索 |
| | `Tab` | コマンド・ファイル名補完 |

### トラブルシューティング時の基本フロー

1. **ログを確認**: `docker compose logs -f <service>`
2. **エラーを検索**: `docker logs <container> | grep -i error`
3. **コンテナの状態確認**: `docker compose ps`
4. **コンテナ内で確認**: `docker exec -it <container> bash`
5. **サービス再起動**: `docker compose restart <service>`

### ヘルプの表示方法

ほとんどのコマンドは `--help` オプションでヘルプを表示できます。

```bash
# コマンドのヘルプを表示
ls --help
docker --help
git --help

# man コマンドでマニュアルを表示
man ls
man grep
```

---

## 参考リンク

- Linux コマンド一覧: <https://ss64.com/bash/>
- Docker CLI リファレンス: <https://docs.docker.com/engine/reference/commandline/cli/>
- Git コマンド一覧: <https://git-scm.com/docs>

---

**最終更新**: 2025年11月30日
