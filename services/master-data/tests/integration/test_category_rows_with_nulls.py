"""A category row written straight to the database with null columns does not
turn the category GETs into 422.

The API requires the text columns on create and update, but a row inserted by a
migration or another system can lack them, or lack ``created_at``. One such row
used to make the single GET and the whole tenant's list answer 422.
"""
import os

import pytest
import pytest_asyncio
from fastapi import status

from app.config.settings import settings

ROWS = [
    # The top of a merchandise hierarchy: no short description, no tax group.
    {"category_code": "NULL-TOP", "description": "Top level", "description_short": None, "tax_code": None},
    # Inserted without created_at, so entryDatetime has nothing to show.
    {"category_code": "NULL-NOTS", "description": "No timestamp", "description_short": "NoTs", "tax_code": "01"},
]


@pytest_asyncio.fixture
async def rows_with_nulls():
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")
    collection = db[settings.DB_COLLECTION_NAME_CATEGORY_MASTER]
    await collection.insert_many([{**row, "tenant_id": tenant_id} for row in ROWS])
    try:
        yield tenant_id
    finally:
        await collection.delete_many({"category_code": {"$in": [row["category_code"] for row in ROWS]}})


@pytest.mark.asyncio
async def test_list_returns_rows_with_nulls(http_client, admin_header, rows_with_nulls):
    tenant_id = rows_with_nulls

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/categories", params={"limit": 100}, headers=admin_header
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    by_code = {row["categoryCode"]: row for row in response.json()["data"]}
    assert by_code["NULL-TOP"]["descriptionShort"] is None
    assert by_code["NULL-TOP"]["taxCode"] is None
    assert by_code["NULL-NOTS"]["entryDatetime"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("category_code", [row["category_code"] for row in ROWS])
async def test_single_get_returns_row_with_nulls(http_client, admin_header, rows_with_nulls, category_code):
    tenant_id = rows_with_nulls

    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/categories/{category_code}", headers=admin_header)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["categoryCode"] == category_code
