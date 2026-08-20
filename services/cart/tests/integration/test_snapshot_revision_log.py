# Copyright 2026 masa@kugel
"""The revision reaches the request log (issue #165).

Here rather than in e2e because the request log is buffered: in-process the
buffer can be flushed on demand, so the assertion is about the recording and not
about how long a batch takes to land.
"""

import base64
import os

import pytest
from fastapi import status

from app.config.settings import settings
from app.services import snapshot_service
from kugel_common.middleware.request_log_buffer import get_request_log_buffer

KEY_SPEC = "it-v1:" + base64.b64encode(b"integration-test-key-32-bytes!!!").decode()


@pytest.fixture
def snapshot_keys(monkeypatch):
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)
    yield KEY_SPEC
    snapshot_service.init_snapshot_signer(force=True)


pytestmark = pytest.mark.asyncio


def _api_headers():
    return {"X-API-KEY": "test-api-key-12345", "Content-Type": "application/json"}


def _terminal_id():
    return f"{os.environ.get('TENANT_ID')}-5678-9"


async def _logged_snapshot_marks(cart_id):
    """Flush the request-log buffer, then read back what it recorded."""
    from kugel_common.database import database as db_helper

    await get_request_log_buffer().shutdown()
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    rows = (
        await db["log_request"]
        .find({"snapshot_info.cart_id": cart_id}, {"snapshot_info": 1, "request_info.accept_time": 1})
        .sort("request_info.accept_time", 1)
        .to_list(length=50)
    )
    return [r["snapshot_info"] for r in rows]


async def _cart_with_snapshots(http_client, snapshot_keys, mutations=2):
    terminal_id, headers = _terminal_id(), _api_headers()
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Revision"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    cart_id, snapshots = data["cartId"], [data["signedSnapshot"]]

    for _ in range(mutations):
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json={"signedSnapshot": snapshots[-1], "payload": [{"itemCode": "49-01", "quantity": 1}]},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        snapshots.append(response.json()["data"]["signedSnapshot"])

    return cart_id, snapshots


async def test_presented_revisions_are_recorded(http_client, snapshot_keys):
    cart_id, _ = await _cart_with_snapshots(http_client, snapshot_keys)

    marks = await _logged_snapshot_marks(cart_id)

    assert marks, "no snapshot marks were recorded for the carried requests"
    assert [m["revision"] for m in marks] == sorted(m["revision"] for m in marks)
    assert all(m["schema_version"] == 2 for m in marks)
    assert all(m["kid"] for m in marks)


async def test_a_replayed_envelope_is_visible_as_a_lower_revision(http_client, snapshot_keys):
    """The point of the issue: the rollback cannot be refused, but it is findable."""
    cart_id, snapshots = await _cart_with_snapshots(http_client, snapshot_keys)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={_terminal_id()}",
        json={"signedSnapshot": snapshots[0], "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=_api_headers(),
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    presented = [m["revision"] for m in await _logged_snapshot_marks(cart_id)]

    assert presented, "no snapshot marks were recorded"
    rollbacks = [(before, after) for before, after in zip(presented, presented[1:]) if after < before]
    assert rollbacks, f"the replay is not visible in {presented}"


async def test_ordinary_use_records_no_rollback(http_client, snapshot_keys):
    cart_id, _ = await _cart_with_snapshots(http_client, snapshot_keys, mutations=3)

    presented = [m["revision"] for m in await _logged_snapshot_marks(cart_id)]

    assert presented == sorted(presented), f"unexpected rollback in {presented}"


async def test_a_request_carrying_nothing_records_nothing(http_client, snapshot_keys):
    # A phase 1 request has no envelope, so there is no revision to record.
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={_terminal_id()}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Legacy"},
        headers=_api_headers(),
    )
    cart_id = response.json()["data"]["cartId"]
    await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={_terminal_id()}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=_api_headers(),
    )

    assert await _logged_snapshot_marks(cart_id) == []
