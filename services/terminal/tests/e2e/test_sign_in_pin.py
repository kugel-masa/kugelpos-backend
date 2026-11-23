"""Sign-in verifies the staff PIN through master-data, on the real stack (issue #323).

A staff member with a PIN signs in only with it; one without signs in by ID
alone. The three failures answer the same body. master-data's verification
endpoint cannot be reached with a terminal's credentials.
"""

import os
import re
import uuid

import pytest
from httpx import AsyncClient, Timeout

from tests.e2e.test_crud import admin_token  # noqa: F401 - fixture

PIN = "pin-sentinel-7c1e9a"
WRONG = "pin-wrong-3f80b2"


def _master_data() -> AsyncClient:
    return AsyncClient(base_url=os.environ["BASE_URL_MASTER_DATA"], timeout=Timeout(timeout=None))


async def _staff(admin_header, **pin_fields) -> str:
    staff_id = f"PIN{uuid.uuid4().hex[:6].upper()}"
    tenant_id = os.environ["TENANT_ID"]
    async with _master_data() as m:
        r = await m.post(
            f"/tenants/{tenant_id}/staff",
            json={"id": staff_id, "name": "PIN Probe", "roles": ["staff"], **pin_fields},
            headers=admin_header,
        )
    assert r.status_code == 201, r.text
    return staff_id


async def _terminal(http_client, admin_header):
    tenant_id = os.environ["TENANT_ID"]
    store_code = f"P{uuid.uuid4().hex[:4].upper()}"
    await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": store_code, "store_name": "PIN", "tags": []},
        headers=admin_header,
    )
    r = await http_client.post(
        "/api/v1/terminals", json={"store_code": store_code, "terminal_no": 1, "description": "PIN"}, headers=admin_header
    )
    assert r.status_code == 201, r.text
    terminal_id, api_key = r.json()["data"]["terminalId"], r.json()["data"]["apiKey"]
    r = await http_client.post(f"/api/v1/auth/token?terminal_id={terminal_id}", headers={"X-API-KEY": api_key})
    assert r.status_code == 200, r.text
    return terminal_id, api_key, {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _sign_in(http_client, terminal_id, headers, body):
    return await http_client.post(f"/api/v1/terminals/{terminal_id}/sign-in", json=body, headers=headers)


async def _sign_out(http_client, terminal_id, headers):
    r = await http_client.post(f"/api/v1/terminals/{terminal_id}/sign-out", headers=headers)
    assert r.status_code == 200, r.text


def _comparable(body: dict, staff_id: str) -> dict:
    """The failure body with the staff ID neutralised, so two staff IDs compare."""
    text = re.sub(re.escape(staff_id), "<staff>", str(body))
    return {"text": text}


@pytest.mark.asyncio
async def test_a_staff_member_with_a_pin(http_client, admin_token):  # noqa: F811
    admin = {"Authorization": f"Bearer {admin_token}"}
    staff_id = await _staff(admin, pin=PIN)
    terminal_id, _, headers = await _terminal(http_client, admin)

    failures = []
    for body in ({"staffId": staff_id, "pin": WRONG}, {"staffId": staff_id}, {"staffId": staff_id, "pin": ""}):
        r = await _sign_in(http_client, terminal_id, headers, body)
        assert r.status_code == 401, r.text
        assert r.json()["userError"]["code"] == "406004"
        assert PIN not in r.text and WRONG not in r.text
        failures.append(r.json())
    assert failures[0] == failures[1] == failures[2]

    missing = f"NOSUCH{uuid.uuid4().hex[:6].upper()}"
    r = await _sign_in(http_client, terminal_id, headers, {"staffId": missing, "pin": PIN})
    assert r.status_code == 401, r.text
    assert _comparable(r.json(), missing) == _comparable(failures[0], staff_id)

    r = await _sign_in(http_client, terminal_id, headers, {"staffId": staff_id, "pin": PIN})
    assert r.status_code == 200, r.text
    assert PIN not in r.text
    await _sign_out(http_client, terminal_id, {"Authorization": f"Bearer {r.headers['x-new-token']}"})


@pytest.mark.asyncio
@pytest.mark.parametrize("pin_fields", [{}, {"pin": ""}], ids=["omitted", "empty"])
async def test_a_staff_member_without_a_pin(http_client, admin_token, pin_fields):  # noqa: F811
    admin = {"Authorization": f"Bearer {admin_token}"}
    staff_id = await _staff(admin, **pin_fields)
    terminal_id, _, headers = await _terminal(http_client, admin)

    for body in ({"staffId": staff_id}, {"staffId": staff_id, "pin": "anything"}):
        r = await _sign_in(http_client, terminal_id, headers, body)
        assert r.status_code == 200, r.text
        await _sign_out(http_client, terminal_id, {"Authorization": f"Bearer {r.headers['x-new-token']}"})


@pytest.mark.asyncio
async def test_the_verification_endpoint_refuses_terminal_credentials(http_client, admin_token):  # noqa: F811
    admin = {"Authorization": f"Bearer {admin_token}"}
    staff_id = await _staff(admin, pin=PIN)
    terminal_id, api_key, terminal_jwt = await _terminal(http_client, admin)
    tenant_id = os.environ["TENANT_ID"]
    url = f"/internal/tenants/{tenant_id}/staff/{staff_id}/verify"

    async with _master_data() as m:
        by_key = await m.post(f"{url}?terminal_id={terminal_id}", json={"pin": PIN}, headers={"X-API-KEY": api_key})
        by_jwt = await m.post(url, json={"pin": PIN}, headers=terminal_jwt)
        by_admin = await m.post(url, json={"pin": PIN}, headers=admin)

    assert by_key.status_code == 401, by_key.text
    assert by_jwt.status_code == 403, by_jwt.text
    assert by_admin.status_code == 403, by_admin.text
