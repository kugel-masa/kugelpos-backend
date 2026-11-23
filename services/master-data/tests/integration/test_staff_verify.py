"""Staff verification against real MongoDB, through the app (issue #323).

The PIN is required only when the stored one is not empty. A staff member
created without a PIN signs in with their ID alone; an update that omits the
PIN keeps it, and one that sends "" clears it.
"""

import os
import uuid

import pytest

from kugel_common.utils.service_auth import create_service_token

pytestmark = pytest.mark.asyncio

PIN = "pin-sentinel-7c1e9a"


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


def _service_header() -> dict:
    return {"Authorization": f"Bearer {create_service_token(_tenant(), 'terminal')}"}


async def _create(http_client, admin_header, **pin_fields) -> str:
    staff_id = f"PV{uuid.uuid4().hex[:8]}"
    response = await http_client.post(
        f"/api/v1/tenants/{_tenant()}/staff",
        json={"id": staff_id, "name": "Probe", "roles": ["cashier"], **pin_fields},
        headers=admin_header,
    )
    assert response.status_code == 201, response.text
    return staff_id


async def _verify(http_client, staff_id, body):
    return await http_client.post(
        f"/api/v1/internal/tenants/{_tenant()}/staff/{staff_id}/verify", json=body, headers=_service_header()
    )


@pytest.mark.parametrize(
    "body, status, code",
    [
        ({"pin": PIN}, 200, None),
        ({"pin": "pin-wrong-3f80b2"}, 401, "405703"),
        ({}, 401, "405702"),
        ({"pin": ""}, 401, "405702"),
    ],
)
async def test_a_staff_member_with_a_pin(http_client, admin_header, body, status, code):
    staff_id = await _create(http_client, admin_header, pin=PIN)

    response = await _verify(http_client, staff_id, body)

    assert response.status_code == status, response.text
    if code:
        assert response.json()["userError"]["code"] == code
    else:
        assert response.json()["data"] == {"id": staff_id, "name": "Probe"}
    assert PIN not in response.text


@pytest.mark.parametrize("pin_fields", [{}, {"pin": ""}], ids=["omitted", "empty"])
@pytest.mark.parametrize("body", [{}, {"pin": "anything"}])
async def test_a_staff_member_without_a_pin(http_client, admin_header, pin_fields, body):
    staff_id = await _create(http_client, admin_header, **pin_fields)

    response = await _verify(http_client, staff_id, body)

    assert response.status_code == 200, response.text


async def test_a_missing_staff_member(http_client):
    response = await _verify(http_client, f"NOSUCH{uuid.uuid4().hex[:6]}", {"pin": PIN})

    assert response.status_code == 404, response.text
    assert response.json()["userError"]["code"] == "405701"


async def test_an_update_keeps_the_pin_unless_it_is_cleared(http_client, admin_header):
    staff_id = await _create(http_client, admin_header, pin=PIN)
    url = f"/api/v1/tenants/{_tenant()}/staff/{staff_id}"

    renamed = await http_client.put(url, json={"name": "Renamed", "roles": ["cashier"]}, headers=admin_header)
    assert renamed.status_code == 200, renamed.text
    assert (await _verify(http_client, staff_id, {})).json()["userError"]["code"] == "405702"

    cleared = await http_client.put(url, json={"name": "Renamed", "pin": "", "roles": ["cashier"]}, headers=admin_header)
    assert cleared.status_code == 200, cleared.text
    assert (await _verify(http_client, staff_id, {})).status_code == 200
