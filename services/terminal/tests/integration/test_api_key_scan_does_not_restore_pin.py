# Copyright 2026 masa@kugel
"""The API-key scan path does not copy a stored staff PIN back into memory.

POST /auth/token without a terminal_id scans the tenant databases and rebuilt
the signed-in staff from the stored document, pin included. The PIN's supply is
closed (#136), but a record written before that can still hold one in plain
text, and copying it back put it into the in-memory terminal again. Nothing
downstream of a token reads it, so it is no longer copied. The same applies to
commons' transform_terminal_info, which the terminal_id path goes through.
"""

import os
import secrets

import pytest
import pytest_asyncio

TENANT = "PINSCAN1"


@pytest_asyncio.fixture
async def stored_terminal():
    from kugel_common.database import database as db_helper

    from app.config.settings import settings

    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}"
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)
    db = await db_helper.get_db_async(db_name)
    api_key = secrets.token_hex(16)
    await db[settings.DB_COLLECTION_NAME_TERMINAL_INFO].insert_one(
        {
            "tenant_id": TENANT,
            "store_code": "S1",
            "terminal_no": 1,
            "terminal_id": f"{TENANT}-S1-1",
            "api_key": api_key,
            "status": "Idle",
            "staff": {"id": "S001", "name": "Staff One", "pin": "1234"},
        }
    )
    try:
        yield api_key
    finally:
        await client.drop_database(db_name)


@pytest.mark.asyncio
async def test_the_scan_path_keeps_the_staff_but_not_the_pin(stored_terminal):
    from app.api.v1.auth import _get_terminal_info_by_api_key_scan

    terminal = await _get_terminal_info_by_api_key_scan(stored_terminal)

    assert terminal.staff.id == "S001"
    assert terminal.staff.name == "Staff One"
    assert terminal.staff.pin is None


@pytest.mark.asyncio
async def test_the_terminal_id_path_keeps_the_staff_but_not_the_pin(stored_terminal):
    from kugel_common.security import get_terminal_info_for_terminal_service

    terminal = await get_terminal_info_for_terminal_service(f"{TENANT}-S1-1", stored_terminal)

    assert terminal.staff.id == "S001"
    assert terminal.staff.pin is None
