# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import pytest_asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from httpx import AsyncClient

from kugel_common.utils.misc import get_app_time_str
from app.models.repositories.journal_repository import JournalRepository
from app.models.documents.jornal_document import JournalDocument


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    """
    setup database
    create database and collections
    """
    print("Setting up database")
    # Reset the database connection to ensure clean state
    await db_helper.close_client_async()

    tenant_id = os.environ.get("TENANT_ID")
    await database_setup.execute(tenant_id=os.environ.get("TENANT_ID"))
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")

    print("Database setup completed")

    yield db

    print("Shutdown database")
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase):
    assert setup_db is not None
    print(f"Database: {setup_db.name}")

    # get token from auth service
    tenant_id: str = os.environ.get("TENANT_ID")
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == 200
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # create terminal info
    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals"
    terminal_info = {
        "store_code": os.environ.get("STORE_CODE"),
        "terminal_no": os.environ.get("TERMINAL_NO"),
        "description": "test terminal",
    }
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.post(url=terminal_url, headers=header, json=terminal_info)
    res = response.json()
    print(f"create terminal response: {res}")

    # create journal collection
    db = setup_db
    tenant_id = os.environ.get("TENANT_ID")

    journal_repo = JournalRepository(db, tenant_id)
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_NO"))
    business_date_str = datetime.now().strftime("%Y%m%d")
    gen_date_time_str = get_app_time_str()

    # create journal collection for compatibility with old journal data
    try:
        journal = JournalDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            journal_seq_no=122,
            transaction_no=455,
            transaction_type=101,
            business_date=business_date_str,
            open_counter=1,
            business_counter=1,
            generate_date_time=gen_date_time_str,
            receipt_no=788,
            # amount=19800.0,
            # quantity=10,
            # staff_id="S001",
            # user_id="U001",
            content="example_content",
            journal_text="example_journal_text",
            receipt_text="example_receipt_text",
        )
        await journal_repo.create_journal_async(journal_doc=journal)
    except Exception as e:
        print(f"Failed to create journal: {e}")
        assert False, f"Failed to create journal: {e}"

    gen_date_time_str = get_app_time_str()
    try:
        journal = JournalDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            journal_seq_no=123,
            transaction_no=456,
            transaction_type=101,
            business_date=business_date_str,
            open_counter=1,
            business_counter=1,
            generate_date_time=gen_date_time_str,
            receipt_no=789,
            amount=19800.0,
            quantity=10,
            staff_id="S001",
            user_id="U001",
            content="example_content",
            journal_text="example_journal_text",
            receipt_text="example_receipt_text",
        )
        await journal_repo.create_journal_async(journal_doc=journal)
    except Exception as e:
        print(f"Failed to create journal: {e}")
        assert False, f"Failed to create journal: {e}"
