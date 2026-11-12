# Copyright 2026 masa@kugel
"""Records written straight to the database with gaps do not break the GETs.

The API always writes a tenant's stores, name, tags and creation time, and a
terminal's description, mode, status and counters. A migration or another system
need not, and one such record turned the tenant GET, the store list and the
terminal list into an error, and made every store operation on a tenant whose
stores were null raise TypeError. Uses its own tenant database so the shared one
is left alone.
"""

import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from fastapi import status

TENANT = "NULLGAP1"


@pytest.fixture
def header():
    from kugel_common.config.settings import settings

    payload = {
        "sub": "admin",
        "tenant_id": TENANT,
        "is_superuser": True,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return {"Authorization": f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"}


@pytest_asyncio.fixture
async def records_with_gaps():
    from kugel_common.database import database as db_helper

    from app.config.settings import settings

    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}"
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)
    db = await db_helper.get_db_async(db_name)
    # A tenant with null stores, no name, no tags and no creation time.
    await db[settings.DB_COLLECTION_NAME_TENANT_INFO].insert_one({"tenant_id": TENANT, "stores": None})
    # A terminal with only its identity.
    await db[settings.DB_COLLECTION_NAME_TERMINAL_INFO].insert_one(
        {"tenant_id": TENANT, "store_code": "S1", "terminal_no": 1, "terminal_id": f"{TENANT}-S1-1"}
    )
    try:
        yield
    finally:
        await client.drop_database(db_name)


@pytest.mark.asyncio
async def test_tenant_get_answers_200(http_client, header, records_with_gaps):
    response = await http_client.get(f"/api/v1/tenants/{TENANT}", headers=header)

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["stores"] == []
    assert data["entryDatetime"] is None


@pytest.mark.asyncio
async def test_store_list_answers_200(http_client, header, records_with_gaps):
    response = await http_client.get(f"/api/v1/tenants/{TENANT}/stores", headers=header)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_a_store_can_be_added_to_a_tenant_with_null_stores(http_client, header, records_with_gaps):
    response = await http_client.post(
        f"/api/v1/tenants/{TENANT}/stores",
        json={"storeCode": "S1", "storeName": "Store 1"},
        headers=header,
    )

    assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), response.text
    assert [s["storeCode"] for s in response.json()["data"]["stores"]] == ["S1"]


@pytest.mark.asyncio
async def test_terminal_list_answers_200(http_client, header, records_with_gaps):
    response = await http_client.get(f"/api/v1/terminals?tenant_id={TENANT}", headers=header)

    assert response.status_code == status.HTTP_200_OK, response.text
    terminals = response.json()["data"]
    assert [t["terminalId"] for t in terminals] == [f"{TENANT}-S1-1"]
    assert terminals[0]["description"] is None


@pytest.mark.asyncio
async def test_updating_a_store_on_a_tenant_with_null_stores_is_not_found(http_client, header, records_with_gaps):
    response = await http_client.put(
        f"/api/v1/tenants/{TENANT}/stores/NOPE", json={"storeName": "renamed"}, headers=header
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_updating_an_unknown_store_is_not_found_and_writes_nothing(http_client, header, records_with_gaps):
    from kugel_common.database import database as db_helper

    from app.config.settings import settings

    added = await http_client.post(
        f"/api/v1/tenants/{TENANT}/stores", json={"storeCode": "S1", "storeName": "Store 1"}, headers=header
    )
    assert added.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), added.text
    collection = (await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}"))[
        settings.DB_COLLECTION_NAME_TENANT_INFO
    ]
    before = await collection.find_one({"tenant_id": TENANT})

    response = await http_client.put(
        f"/api/v1/tenants/{TENANT}/stores/NOPE", json={"storeName": "renamed"}, headers=header
    )

    # It was a 400 "cannot update" from an UnboundLocalError, after rewriting the
    # tenant document unchanged.
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    after = await collection.find_one({"tenant_id": TENANT})
    assert after == before
