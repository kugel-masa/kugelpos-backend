# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import pytest_asyncio
import os
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from httpx import AsyncClient
from fastapi import status

from kugel_common.database import database as db_helper
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.database import database_setup
from app.models.repositories.tranlog_repository import TranlogRepository
from tests.log_maker import make_tran_log


# 設定マスター登録のためのヘルパー関数を追加
async def register_invoice_registration_number(tenant_id, token):
    """
    INVOICE_REGISTRATION_NUMBERを設定マスターに登録するヘルパー関数
    """
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = 9
    header = {"Authorization": f"Bearer {token}"}

    settings_name = "INVOICE_REGISTRATION_NUMBER"
    settings_master = {
        "name": settings_name,
        "defaultValue": "T999999999999",
        "values": [
            {"storeCode": store_code, "terminalNo": terminal_no, "value": "T1234567890123"},
            {"storeCode": store_code, "value": "T1234567890111"},
        ],
    }

    async with AsyncClient() as client:
        response = await client.post(f"{base_url}/tenants/{tenant_id}/settings", json=settings_master, headers=header)
        return response.json()


# receipt headerの登録を行うためのヘルパー関数
async def register_receipt_header(tenant_id, token):
    """
    レシートヘッダーを設定マスターに登録するヘルパー関数
    """
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = 9
    header = {"Authorization": f"Bearer {token}"}

    header_list_default = [
        {"text": "header1", "align": "left"},
        {"text": "header2", "align": "center"},
        {"text": "header3", "align": "right"},
    ]

    header_list_terminal = [
        {"text": "terminal header1", "align": "left"},
        {"text": "terminal header2", "align": "center"},
        {"text": "terminal header3", "align": "right"},
    ]

    header_list_store = [
        {"text": "store header1", "align": "left"},
        {"text": "store header2", "align": "center"},
        {"text": "store header3", "align": "right"},
    ]

    receipt_header = {
        "name": "RECEIPT_HEADERS",
        "defaultValue": str(header_list_default),
        "values": [
            {"storeCode": store_code, "terminalNo": terminal_no, "value": str(header_list_terminal)},
            {"storeCode": store_code, "value": str(header_list_store)},
        ],
    }

    async with AsyncClient() as client:
        response = await client.post(f"{base_url}/tenants/{tenant_id}/settings", json=receipt_header, headers=header)
        return response.json()


# reeipt footerの登録を行うためのヘルパー関数
async def register_receipt_footer(tenant_id, token):
    """
    レシートフッターを設定マスターに登録するヘルパー関数
    """
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = 9
    header = {"Authorization": f"Bearer {token}"}

    footer_list_default = [
        {"text": "footer1", "align": "left"},
        {"text": "footer2", "align": "center"},
        {"text": "footer3", "align": "right"},
    ]

    footer_list_terminal = [
        {"text": "terminal footer1", "align": "left"},
        {"text": "terminal footer2", "align": "center"},
        {"text": "terminal footer3", "align": "right"},
    ]

    footer_list_store = [
        {"text": "store footer1", "align": "left"},
        {"text": "store footer2", "align": "center"},
        {"text": "store footer3", "align": "right"},
    ]

    receipt_footer = {
        "name": "RECEIPT_FOOTERS",
        "defaultValue": str(footer_list_default),
        "values": [
            {"storeCode": store_code, "terminalNo": terminal_no, "value": str(footer_list_terminal)},
            {"storeCode": store_code, "value": str(footer_list_store)},
        ],
    }

    async with AsyncClient() as client:
        response = await client.post(f"{base_url}/tenants/{tenant_id}/settings", json=receipt_footer, headers=header)
        return response.json()


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):
    """
    setup database
    create database and collections
    """
    # print("Setting up database")
    await database_setup.execute(os.environ.get("TENANT_ID"))

    """
    setup data :
    """

    yield await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    print("Database setup completed")

    print("Shutting down database")
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase):

    assert setup_db is not None
    print("database name: ", setup_db.name)

    #
    # create tranlog data for compatibility with old transaction log
    #

    business_date_str = datetime.now().strftime("%Y%m%d")

    terminal_info = _make_terminal_info(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=os.environ.get("STORE_CODE"),
        terminal_no=99,
        business_date=business_date_str,
    )
    tranlog_repo = TranlogRepository(db=setup_db, terminal_info=terminal_info)
    tranlog = make_tran_log(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=os.environ.get("STORE_CODE"),
        terminal_no=99,
        tran_type=101,
        tran_no=1001,
        receipt_no=1001,
        business_date=business_date_str,
        open_counter=1,
        business_counter=1234,
    )
    print(f"tranlog: {tranlog}")

    tranlog_created = None
    try:
        tranlog_created = await tranlog_repo.create_tranlog_async(tranlog)
    except Exception as e:
        print(f"Error: {e}")

    print(f"tranlog_created: {tranlog_created}")
    assert tranlog_created is not None


@pytest.mark.asyncio
async def test_register_invoice_number(set_env_vars):
    """
    INVOICE_REGISTRATION_NUMBERを設定マスターに登録するテスト
    """
    # 認証トークンの取得
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}

    token = None
    async with AsyncClient() as http_auth_client:
        response = await http_auth_client.post(url=token_url, data=login_data)
        assert response.status_code == status.HTTP_200_OK
        res = response.json()
        token = res.get("access_token")
        assert token is not None

    # INVOICE_REGISTRATION_NUMBERの登録
    result = await register_invoice_registration_number(tenant_id, token)
    print(f"INVOICE_REGISTRATION_NUMBER registration result: {result}")

    # 登録結果の確認（既に存在する場合は400エラーでも成功とみなす）
    if result.get("code") == status.HTTP_400_BAD_REQUEST:
        # 既に登録されている場合
        assert "already exists" in result.get("message", "")
        print("INVOICE_REGISTRATION_NUMBER already registered, skipping...")
    else:
        # 新規登録の場合
        assert result.get("success") is True
        assert result.get("code") == status.HTTP_201_CREATED
        assert result.get("data").get("name") == "INVOICE_REGISTRATION_NUMBER"
        assert result.get("data").get("defaultValue") == "T999999999999"

        # 値の検証
        store_code = os.environ.get("STORE_CODE")
        terminal_no = 9
        assert result.get("data").get("values")[0].get("storeCode") == store_code
        assert result.get("data").get("values")[0].get("terminalNo") == terminal_no
        assert result.get("data").get("values")[0].get("value") == "T1234567890123"

    # receipt headerの登録
    result = await register_receipt_header(tenant_id, token)
    print(f"RECEIPT_HEADERS registration result: {result}")
    if result.get("code") == status.HTTP_400_BAD_REQUEST:
        assert "already exists" in result.get("message", "")
        print("RECEIPT_HEADERS already registered, skipping...")
    else:
        assert result.get("success") is True
        assert result.get("code") == status.HTTP_201_CREATED

    # receipt footerの登録
    result = await register_receipt_footer(tenant_id, token)
    print(f"RECEIPT_FOOTERS registration result: {result}")
    if result.get("code") == status.HTTP_400_BAD_REQUEST:
        assert "already exists" in result.get("message", "")
        print("RECEIPT_FOOTERS already registered, skipping...")
    else:
        assert result.get("success") is True
        assert result.get("code") == status.HTTP_201_CREATED


def _make_terminal_info(
    tenant_id: str,
    store_code: str,
    terminal_no: int,
    business_date: str,
    open_counter: int = 1,
    business_counter: int = 1001,
    staff: str = None,
    initial_amount: float = 0.0,
    physical_amount: float = 0.0,
) -> TerminalInfoDocument:
    return TerminalInfoDocument(
        tenant_id=tenant_id,
        store_code=store_code,
        terminal_no=terminal_no,
        description="Test Terminal",
        terminal_id=f"{tenant_id}-{store_code}-{terminal_no}",
        function_mode="Sales",
        status="Opened",  # ステータスをOpenedに変更
        business_date=business_date,
        open_counter=open_counter,
        business_counter=business_counter,
        staff=staff if staff else {"id": "S001", "name": "Test Staff"},  # staffオブジェクトを設定
        initial_amount=initial_amount,
        physical_amount=physical_amount,
        api_key="test_api_key",
        tags=["test"],
    )
