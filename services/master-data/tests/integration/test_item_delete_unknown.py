"""Deleting an item that does not exist answers 404, not success (#312)."""

import asyncio
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
    # Already marked: a second logical delete finds nothing to mark
    assert (await http_client.delete(url, params={"is_logical": "true"}, headers=admin_header)).status_code == 404
    assert (await http_client.delete(url, params={"is_logical": "false"}, headers=admin_header)).status_code == 200
    # Gone for good: a second physical delete finds nothing
    assert (await http_client.delete(url, params={"is_logical": "false"}, headers=admin_header)).status_code == 404


@pytest.mark.parametrize("is_logical", [False, True], ids=["physical", "logical"])
async def test_of_two_concurrent_deletes_one_succeeds_and_the_other_is_not_found(http_client, admin_header, is_logical):
    # Deciding existence and deleting in two queries let the second request answer
    # 200 having deleted nothing, or 500 (#312). One write decides now.
    tenant_id = os.environ.get("TENANT_ID")
    code = f"RACE{uuid.uuid4().hex[:6]}"
    url = f"/api/v1/tenants/{tenant_id}/items/{code}"
    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/items", json=_item(code), headers=admin_header)
    assert response.status_code == 201, response.text
    params = {"is_logical": str(is_logical).lower()}

    responses = await asyncio.gather(*[http_client.delete(url, params=params, headers=admin_header) for _ in range(4)])

    assert sorted(r.status_code for r in responses) == [200, 404, 404, 404], [r.text for r in responses]
    if is_logical:
        await http_client.delete(url, params={"is_logical": "false"}, headers=admin_header)
