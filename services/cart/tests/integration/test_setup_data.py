# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
import os
from datetime import datetime

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.database import database as db_helper
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.database import database_setup
from app.models.repositories.tranlog_repository import TranlogRepository
from tests.log_maker import make_tran_log


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):
    """
    setup database
    create database and collections
    """
    await database_setup.execute(os.environ.get("TENANT_ID"))

    yield await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    print("Database setup completed")

    print("Shutting down database")
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase):

    assert setup_db is not None
    print("database name: ", setup_db.name)

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
        status="Opened",
        business_date=business_date,
        open_counter=open_counter,
        business_counter=business_counter,
        staff=staff if staff else {"id": "S001", "name": "Test Staff"},
        initial_amount=initial_amount,
        physical_amount=physical_amount,
        api_key="test_api_key",
        tags=["test"],
    )
