"""Deleting an item that does not exist answers 404, not success (#312)."""

import os
import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _item(code: str) -> dict:
    return {
        "itemCode": code,
        "description": "Delete probe",
        "unitPrice": 100,
        "unitCost": 50,
        "itemDetails": [],
        "imageUrls": [],
        "categoryCode": "001",
        "taxCode": "01",
    }


@pytest.mark.parametrize("is_logical", [False, True], ids=["physical", "logical"])
async def test_deleting_an_unknown_item_is_not_found(http_client, admin_header, is_logical):
    tenant_id = os.environ.get("TENANT_ID")

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/items/NOSUCH{uuid.uuid4().hex[:6]}",
        params={"is_logical": str(is_logical).lower()},
        headers=admin_header,
    )

    assert response.status_code == 404, response.text


async def test_a_logically_deleted_item_can_still_be_deleted_physically(http_client, admin_header):
    tenant_id = os.environ.get("TENANT_ID")
    code = f"DEL{uuid.uuid4().hex[:6]}"
    url = f"/api/v1/tenants/{tenant_id}/items/{code}"
    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/items", json=_item(code), headers=admin_header)
    assert response.status_code == 201, response.text

    assert (await http_client.delete(url, params={"is_logical": "true"}, headers=admin_header)).status_code == 200
    assert (await http_client.delete(url, params={"is_logical": "false"}, headers=admin_header)).status_code == 200
    # Gone for good: a second physical delete finds nothing
    assert (await http_client.delete(url, params={"is_logical": "false"}, headers=admin_header)).status_code == 404
