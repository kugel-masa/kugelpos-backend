"""StaffMasterWebRepository.verify_staff_async asks master-data to verify a staff member (issue #323).

Only the three business failures (405701-405703) become an authentication
failure. Anything else - master-data down, a 5xx, a 404 without a business
code - is a dependency failure and stays a RepositoryException, so a terminal
never tells a staff member their PIN is wrong when master-data is unreachable.
"""

import logging
import urllib.parse
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from kugel_common.config.settings import settings
from kugel_common.enums import StaffAuthenticationFailure
from kugel_common.exceptions import RepositoryException, StaffAuthenticationException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.repositories.staff_master_web_repository import StaffMasterWebRepository
from kugel_common.utils.http_client_helper import HttpClientError

PIN = "pin-sentinel-7c1e9a"
TENANT = "T1"


def _repo():
    terminal = TerminalInfoDocument(tenant_id=TENANT, store_code="S", terminal_no=1, terminal_id="T1-S-1", api_key="k")
    return StaffMasterWebRepository(tenant_id=TENANT, terminal_info=terminal)


def _client(post):
    client = MagicMock()
    client.post = post

    @asynccontextmanager
    async def factory(service_name, **kwargs):
        assert service_name == "master-data"
        yield client

    return factory


def _error(status, body):
    response = MagicMock()
    response.json.return_value = body
    return HttpClientError(f"HTTP error {status}", status_code=status, response=response)


def _failure(code, key="userError"):
    body = {"success": False, "code": 401, "message": "Staff verification failed", key: {"code": code, "message": "x"}}
    if key == "userError":
        body["user_error"] = body["userError"]
    return body


async def _verify(post, staff_id="S1", pin=PIN):
    with patch(
        "kugel_common.models.repositories.staff_master_web_repository.get_service_client", _client(post)
    ):
        return await _repo().verify_staff_async(staff_id, pin)


@pytest.mark.asyncio
async def test_it_posts_the_pin_in_the_body_with_a_service_token():
    post = AsyncMock(return_value={"success": True, "data": {"id": "S1", "name": "Ann"}})

    staff = await _verify(post)

    kwargs = post.await_args.kwargs
    assert post.await_args.args[0] == f"/internal/tenants/{TENANT}/staff/S1/verify"
    assert kwargs["json"] == {"pin": PIN}
    assert not kwargs.get("params")
    claims = jwt.decode(
        kwargs["headers"]["Authorization"].removeprefix("Bearer "), settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert claims["is_service_account"] is True
    assert claims["tenant_id"] == TENANT
    assert "X-API-KEY" not in kwargs["headers"]
    assert (staff.id, staff.name, staff.tenant_id, staff.pin) == ("S1", "Ann", TENANT, None)


@pytest.mark.asyncio
async def test_an_omitted_pin_is_sent_as_null():
    post = AsyncMock(return_value={"success": True, "data": {"id": "S1", "name": "Ann"}})

    await _verify(post, pin=None)

    assert post.await_args.kwargs["json"] == {"pin": None}


@pytest.mark.asyncio
@pytest.mark.parametrize("staff_id", ["a/b", "../admin", "x?y=1", "a b#c"])
async def test_the_staff_id_cannot_reshape_the_path(staff_id):
    post = AsyncMock(return_value={"success": True, "data": {"id": staff_id, "name": "Ann"}})

    await _verify(post, staff_id=staff_id)

    endpoint = post.await_args.args[0]
    head, tail = f"/internal/tenants/{TENANT}/staff/", "/verify"
    assert endpoint.startswith(head) and endpoint.endswith(tail)
    encoded = endpoint[len(head) : -len(tail)]
    assert not any(c in encoded for c in "/?# ")
    assert urllib.parse.unquote(encoded) == staff_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code, reason",
    [
        ("405701", StaffAuthenticationFailure.STAFF_NOT_FOUND),
        ("405702", StaffAuthenticationFailure.PIN_REQUIRED),
        ("405703", StaffAuthenticationFailure.PIN_MISMATCH),
    ],
)
@pytest.mark.parametrize("key", ["userError", "user_error"])
async def test_a_business_failure_is_an_authentication_failure(code, reason, key):
    status = 404 if code == "405701" else 401
    post = AsyncMock(side_effect=_error(status, _failure(code, key)))

    with pytest.raises(StaffAuthenticationException) as exc_info:
        await _verify(post)

    assert exc_info.value.reason is reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        _error(500, {"success": False, "code": 500, "userError": {"code": "900999", "message": "x"}}),
        _error(503, None),
        HttpClientError("Connection error: http://master-data", response="connection refused"),
        _error(404, {"detail": "Not Found"}),
        _error(401, {"detail": "Could not validate credentials"}),
        _error(400, {"success": False, "userError": {"code": "405001", "message": "x"}}),
    ],
    ids=["5xx", "5xx-no-body", "connection", "route-missing-404", "401-no-code", "other-code"],
)
async def test_anything_else_is_a_dependency_failure(error):
    post = AsyncMock(side_effect=error)

    with pytest.raises(RepositoryException) as exc_info:
        await _verify(post)

    assert not isinstance(exc_info.value, StaffAuthenticationException)


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_dependency_failure():
    response = MagicMock()
    response.json.side_effect = ValueError("not json")
    post = AsyncMock(side_effect=HttpClientError("HTTP error 401", status_code=401, response=response))

    with pytest.raises(RepositoryException) as exc_info:
        await _verify(post)

    assert not isinstance(exc_info.value, StaffAuthenticationException)


@pytest.mark.asyncio
async def test_no_exception_or_log_line_carries_the_pin(caplog):
    caplog.set_level(logging.DEBUG)
    texts = []
    for error in (_error(401, _failure("405703")), _error(500, None)):
        try:
            await _verify(AsyncMock(side_effect=error))
        except Exception as e:  # noqa: BLE001 - collecting what would be logged or answered
            texts.append(f"{e} {getattr(e, 'message', '')} {getattr(e, 'log_message', '')}")
    await _verify(AsyncMock(return_value={"success": True, "data": {"id": "S1", "name": "Ann"}}))

    assert PIN not in "\n".join(texts + [r.getMessage() for r in caplog.records])
