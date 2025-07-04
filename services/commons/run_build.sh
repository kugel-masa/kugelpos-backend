#!/bin/bash

# __about__.py のパス
ABOUT_FILE="src/kugel_common/__about__.py"

# 現在のバージョンを読み取る
CURRENT_VERSION=$(grep "__version__" $ABOUT_FILE | cut -d '"' -f 2)
echo "現在のバージョン: $CURRENT_VERSION"

# バージョンをインクリメント（ここでは単純な例としています）
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
VERSION_PARTS[-1]=$((VERSION_PARTS[-1]+1))
NEW_VERSION="${VERSION_PARTS[0]}.${VERSION_PARTS[1]}.${VERSION_PARTS[2]}"
echo "新しいバージョン: $NEW_VERSION"

# __about__.py を新しいバージョンで更新
sed -i "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" $ABOUT_FILE

# プロジェクトをビルド
# ここにビルドコマンドを挿入（例: python setup.py bdist_wheel）
hatch build