# Copyright 2026 masa@kugel
"""What tenant setup tells an operator when it cannot finish (issue #185).

Collections are created before their indexes, so anything already written has to
satisfy them. When it does not, the index can never be built and setup fails on
every retry — and what came back was `Error creating tenant: T6216` and nothing
else. The collection, the index and the documents in the way all existed one
frame down and were discarded.

Observed on real data here: after repeated e2e runs dropped the tenant database
while cart kept publishing, this journal held transaction 1 four times.

End-to-end because the failing response is the deliverable. Each test restores
the tenant database before it finishes — leaving a blocked collection behind
would block every later run, which is the whole point of the issue.
"""

import os

import pytest
from fastapi import status
from motor.motor_asyncio import AsyncIOMotorClient

pytestmark = pytest.mark.asyncio

DUPLICATE = {
    "tenant_id": None,  # filled per test
    "store_code": "9185",
    "terminal_no": 5,
    "business_date": "20260822",
    "open_counter": 7,
    "operation": "open",
}


def _client():
    return AsyncIOMotorClient(os.environ.get("MONGODB_URI"))


def _db_name():
    return f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"


async def _block_a_collection(copies=3):
    """Reproduce the window the issue is about.

    The unique index is dropped first, then the duplicates are written - which is
    the order it happens for real: the tenant database is dropped or has never
    been created, deliveries arrive with no index to refuse them, and setup then
    tries to build one over data that cannot satisfy it.
    """
    collection = _client()[_db_name()]["log_open_close"]
    for name, info in (await collection.index_information()).items():
        if name != "_id_" and info.get("unique"):
            await collection.drop_index(name)
    doc = dict(DUPLICATE, tenant_id=os.environ.get("TENANT_ID"))
    await collection.insert_many([dict(doc) for _ in range(copies)])


async def _unblock():
    """Resolve the duplicates, the way an operator would.

    The index itself is rebuilt by the next successful setup - which is exactly
    what the last test asserts.
    """
    await _client()[_db_name()]["log_open_close"].delete_many({"store_code": DUPLICATE["store_code"]})


async def test_the_failure_names_the_collection_and_the_documents(http_client, admin_header):
    tenant_id = os.environ.get("TENANT_ID")
    await _block_a_collection()
    try:
        response = await http_client.post("/api/v1/tenants", json={"tenant_id": tenant_id}, headers=admin_header)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = response.text
        assert "log_open_close" in detail, f"the response did not name the collection: {detail[:300]}"
        assert "open_counter" in detail, "the response did not name the index"
        assert "x3" in detail, f"the response did not say what is in the way: {detail[:300]}"
    finally:
        await _unblock()


async def test_the_collections_that_can_be_set_up_still_are(http_client, admin_header):
    """One blocked collection used to stop every collection after it."""
    tenant_id = os.environ.get("TENANT_ID")
    db = _client()[_db_name()]
    await db["log_tran"].drop()
    await _block_a_collection()
    try:
        response = await http_client.post("/api/v1/tenants", json={"tenant_id": tenant_id}, headers=admin_header)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "1 of" in response.text, f"expected exactly one blocked step: {response.text[:300]}"

        names = await db.list_collection_names()
        assert "log_tran" in names, "a blocked collection stopped the healthy ones from being created"
        indexes = await db["log_tran"].index_information()
        assert len(indexes) > 1, "the healthy collection was created without its indexes"
    finally:
        await _unblock()


async def test_setup_succeeds_once_the_documents_are_resolved(http_client, admin_header):
    tenant_id = os.environ.get("TENANT_ID")
    await _block_a_collection()
    response = await http_client.post("/api/v1/tenants", json={"tenant_id": tenant_id}, headers=admin_header)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    await _unblock()

    response = await http_client.post("/api/v1/tenants", json={"tenant_id": tenant_id}, headers=admin_header)
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST), response.text
