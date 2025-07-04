#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Navigate to the commons directory
cd "$SCRIPT_DIR/../services/commons"

# __about__.py のパス
ABOUT_FILE="src/kugel_common/__about__.py"

# 現在のバージョンを読み取る
CURRENT_VERSION=$(grep "__version__" $ABOUT_FILE | cut -d '"' -f 2)
echo "現在のバージョン: $CURRENT_VERSION"

# ビルドされたホイールファイルの名前を更新
FILENAME="dist/kugel_common-${CURRENT_VERSION}-py3-none-any.whl"

# コピー先のディレクトリを配列に格納
DEST_DIRS=(
    "../template/commons/dist"
    "../cart/commons/dist"
    "../master-data/commons/dist"
    "../account/commons/dist"
    "../terminal/commons/dist"
    "../report/commons/dist"
    "../journal/commons/dist"
    "../stock/commons/dist"
)

# ログファイルのパス
LOGFILE="copy_log.txt"

# ログファイルを初期化
echo "コピー処理開始: $(date)" > "$LOGFILE"

# 各ディレクトリに対して処理を実行
for DIR in "${DEST_DIRS[@]}"; do
    # ディレクトリが存在しない場合は作成
    if [ ! -d "$DIR" ]; then
        mkdir -p "$DIR"
        echo "$(date): $DIR を作成しました。" >> "$LOGFILE"
    fi
    
    cp "$FILENAME" "$DIR"
    echo "$(date): $FILENAME を $DIR にコピーしました。" >> "$LOGFILE"
done

echo "コピー処理終了: $(date)" >> "$LOGFILE"
