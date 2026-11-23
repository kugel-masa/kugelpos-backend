"""POST /api/v1/internal/tenants/{tenant_id}/staff/{staff_id}/verify (issue #323).

Internal only: a service-account token is the one credential it accepts, and
the tenant in the path must be the token's. The answer carries the staff ID and
name, never the PIN.
"""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import jwt

from kugel_common.config.settings import settings
from kugel_common.exceptions import register_exception_handlers
from kugel_common.utils.service_auth import create_service_token

from app.api.v1.internal import router as internal_router
from app.exceptions import (
    StaffVerifyPinMismatchException,
    StaffVerifyPinRequiredException,
    StaffVerifyStaffNotFoundException,
)
from app.models.documents.staff_master_document import StaffMasterDocument

TENANT = "T1"
PIN = "pin-sentinel-7c1e9a"
URL = f"/api/v1/internal/tenants/{TENANT}/staff/S1/verify"


def _app():
    app = FastAPI()
    app.include_router(internal_router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


def _token(**claims):
    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _service_headers(tenant=TENANT):
    return {"Authorization": f"Bearer {create_service_token(tenant, 'terminal')}"}


async def _post(body, headers, service=None):
    service = service or AsyncMock()
    with patch("app.api.v1.internal.get_staff_master_service_async", AsyncMock(return_value=service)):
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            return await client.post(URL, json=body, headers=headers), service


def _verifying(staff=None, error=None):
    service = AsyncMock()
    if error is not None:
        service.verify_staff_async.side_effect = error
    else:
        service.verify_staff_async.return_value = staff or StaffMasterDocument(
            tenant_id=TENANT, id="S1", name="Ann", pin=PIN, roles=["cashier"]
        )
    return service


@pytest.mark.asyncio
async def test_a_service_account_gets_the_staff_without_the_pin(caplog):
    caplog.set_level(logging.DEBUG)

    response, service = await _post({"pin": PIN}, _service_headers(), _verifying())

    assert response.status_code == 200
    assert set(response.json()["data"]) == {"id", "name"}
    assert response.json()["data"] == {"id": "S1", "name": "Ann"}
    service.verify_staff_async.assert_awaited_once_with("S1", PIN)
    assert PIN not in response.text
    assert PIN not in "\n".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("body, passed", [({}, None), ({"pin": None}, None), ({"pin": ""}, "")])
async def test_an_omitted_or_empty_pin_is_a_valid_request(body, passed):
    response, service = await _post(body, _service_headers(), _verifying())

    assert response.status_code == 200
    service.verify_staff_async.assert_awaited_once_with("S1", passed)


@pytest.mark.asyncio
async def test_a_pin_that_is_not_a_string_is_refused_without_echoing_it():
    response, service = await _post({"pin": 987654321}, _service_headers(), _verifying())

    assert response.status_code == 422
    assert "987654321" not in response.text
    service.verify_staff_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, status, code",
    [
        (StaffVerifyStaffNotFoundException("Staff verification failed: staff not found: staff_id->S1"), 404, "405701"),
        (StaffVerifyPinRequiredException("Staff verification failed: PIN required: staff_id->S1"), 401, "405702"),
        (StaffVerifyPinMismatchException("Staff verification failed: PIN mismatch: staff_id->S1"), 401, "405703"),
    ],
)
async def test_each_failure_has_its_own_code_and_no_details(error, status, code):
    response, _ = await _post({"pin": PIN}, _service_headers(), _verifying(error=error))

    assert response.status_code == status
    body = response.json()
    assert body["userError"]["code"] == code
    assert body["data"] is None
    assert "details" not in body
    assert PIN not in response.text


@pytest.mark.asyncio
async def test_a_terminal_token_is_refused():
    token = _token(sub="terminal:T1-S1-1", tenant_id=TENANT, token_type="terminal")

    response, service = await _post({"pin": PIN}, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    service.verify_staff_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_user_token_is_refused_even_for_a_superuser():
    token = _token(sub="admin", tenant_id=TENANT, is_superuser=True)

    response, service = await _post({"pin": PIN}, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    service.verify_staff_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_api_key_alone_is_refused():
    response, service = await _post({"pin": PIN}, {"X-API-KEY": "some-terminal-key"})

    assert response.status_code == 401
    service.verify_staff_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_another_tenants_service_token_is_refused():
    response, service = await _post({"pin": PIN}, _service_headers(tenant="OTHER"))

    assert response.status_code == 400
    service.verify_staff_async.assert_not_awaited()
