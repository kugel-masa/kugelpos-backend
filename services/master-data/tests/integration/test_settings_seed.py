# Copyright 2026 masa@kugel
"""Terminal-facing settings against a real database (issue #174).

The unit tests mock the repository, so they pin the decisions (what is seeded,
what is left alone) but not the document that actually lands. That distinction
is not academic: the first version of this seeding inserted documents directly,
which looked correct in Mongo and then made GET /settings fail with a 422,
because the response schema renders entry_datetime from created_at - a field
only the repository stamps. These tests exercise the real write and the real
read-back.
"""

import os

import pytest
from fastapi import status

from app.database import database_setup
from app.database.database_setup import TERMINAL_FACING_SETTING_NAMES

pytestmark = pytest.mark.asyncio


async def _collection():
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    return db["master_settings"]


class TestSeededDocuments:
    async def test_tenant_setup_left_both_settings_behind(self):
        # The session fixture runs database_setup.execute().
        collection = await _collection()
        names = {doc["name"] async for doc in collection.find({"name": {"$in": list(TERMINAL_FACING_SETTING_NAMES)}})}

        assert names == set(TERMINAL_FACING_SETTING_NAMES)

    async def test_the_documents_carry_what_the_service_layer_needs(self):
        collection = await _collection()
        doc = await collection.find_one({"name": "RECEIPT_NO_START_VALUE"})

        assert doc["default_value"] == "111111"
        assert doc["tenant_id"] == os.environ.get("TENANT_ID")
        assert doc["shard_key"]
        # entry_datetime in the API response is rendered from this; a document
        # without it fails response validation on the list endpoint.
        assert doc["created_at"] is not None


class TestReadBackThroughTheApi:
    async def test_the_settings_list_renders(self, http_client, admin_header):
        """The 422 this seeding once caused would fail exactly here."""
        tenant_id = os.environ.get("TENANT_ID")
        response = await http_client.get(f"/api/v1/tenants/{tenant_id}/settings", headers=admin_header)

        assert response.status_code == status.HTTP_200_OK, response.text
        names = {s["name"] for s in response.json()["data"]}
        assert set(TERMINAL_FACING_SETTING_NAMES) <= names

    @pytest.mark.parametrize(
        "name,expected", [("RECEIPT_NO_START_VALUE", "111111"), ("RECEIPT_NO_END_VALUE", "999999")]
    )
    async def test_the_value_lookup_answers(self, http_client, admin_header, name, expected):
        tenant_id = os.environ.get("TENANT_ID")
        response = await http_client.get(
            f"/api/v1/tenants/{tenant_id}/settings/{name}/value?store_code=5678&terminal_no=9",
            headers=admin_header,
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["data"]["value"] == expected


class TestRerunningSetup:
    async def test_does_not_duplicate(self):
        tenant_id = os.environ.get("TENANT_ID")
        await database_setup.execute(tenant_id)

        collection = await _collection()
        for name in TERMINAL_FACING_SETTING_NAMES:
            assert await collection.count_documents({"name": name}) == 1

    async def test_does_not_overwrite_a_configured_value(self, http_client, admin_header):
        """Setup re-runs are how migrations reach existing tenants, so a value an
        operator changed has to survive one."""
        tenant_id = os.environ.get("TENANT_ID")
        name = "RECEIPT_NO_START_VALUE"
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/settings/{name}",
            json={"name": name, "defaultValue": "500000", "values": []},
            headers=admin_header,
        )
        assert response.status_code == status.HTTP_200_OK, response.text

        try:
            await database_setup.execute(tenant_id)

            collection = await _collection()
            doc = await collection.find_one({"name": name})
            assert doc["default_value"] == "500000"
        finally:
            await http_client.put(
                f"/api/v1/tenants/{tenant_id}/settings/{name}",
                json={"name": name, "defaultValue": "111111", "values": []},
                headers=admin_header,
            )
