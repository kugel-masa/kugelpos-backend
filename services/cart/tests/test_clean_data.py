# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest, os, asyncio
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient


@pytest_asyncio.fixture(scope="function")
async def clean_db(set_env_vars):
    """データベースのクリーンアップを行うフィクスチャ"""

    from kugel_common.database import database as db_helper

    try:
        # データベース接続の取得
        db_client = await db_helper.get_client_async()

        # クリーンアップ対象のデータベース名
        target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
        print(f"対象データベース: {target_db_name}")

        # データベースの存在確認
        db_names = await db_client.list_database_names()
        if target_db_name in db_names:
            print(f"データベースを削除: {target_db_name}")
            await db_client.drop_database(target_db_name)
        else:
            print(f"データベースが存在しません: {target_db_name}")

        # クライアントを閉じて結果を返す
        return await db_helper.close_client_async()
    except Exception as e:
        print(f"データベースクリーンアップエラー: {str(e)}")
        # エラーが発生してもクライアントを閉じる
        await db_helper.close_client_async()
        raise e


@pytest.mark.asyncio
async def test_clean_data(clean_db):
    """データベースクリーンアップのテスト"""
    print("テスト完了: データベースクリーンアップ")
    assert True  # クリーンアップ操作が例外なく完了したことをチェック
