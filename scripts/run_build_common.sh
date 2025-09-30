#!/bin/bash

# Default values
INCREMENT_VERSION=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --increment-version|-i) INCREMENT_VERSION=true ;;
        --help|-h) 
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --increment-version, -i  Increment the patch version before building"
            echo "  --help, -h              Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Navigate to the commons directory
cd "$SCRIPT_DIR/../services/commons"

# __about__.py のパス
ABOUT_FILE="src/kugel_common/__about__.py"

# 現在のバージョンを読み取る
CURRENT_VERSION=$(grep "__version__" $ABOUT_FILE | cut -d '"' -f 2)
echo "現在のバージョン: $CURRENT_VERSION"

if [ "$INCREMENT_VERSION" = true ]; then
    # バージョンをインクリメント（ここでは単純な例としています）
    IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
    VERSION_PARTS[-1]=$((VERSION_PARTS[-1]+1))
    NEW_VERSION="${VERSION_PARTS[0]}.${VERSION_PARTS[1]}.${VERSION_PARTS[2]}"
    echo "新しいバージョン: $NEW_VERSION"
    
    # __about__.py を新しいバージョンで更新
    sed -i "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" $ABOUT_FILE
else
    echo "バージョンは変更しません"
fi

# プロジェクトをビルド
# ここにビルドコマンドを挿入（例: python setup.py bdist_wheel）
hatch build