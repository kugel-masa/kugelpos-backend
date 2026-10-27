# Copyright 2026 masa@kugel
"""A gRPC call is authenticated from its metadata, with the credentials a REST call carries in headers (issue #134).

master-data's GetItemDetail read whichever tenant and store the request named,
for any caller that could reach the port.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import HTTPException

from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.security import GrpcCaller, get_grpc_caller
from kugel_common.utils.terminal_auth import create_terminal_token


def _terminal_token(**store) -> str:
    fields = {"tenant_id": "T001", "terminal_no": 1, "terminal_id": "T001-S001-01", **store}
    return create_terminal_token(TerminalInfoDocument(**fields))


def _user_token(secret: str = settings.SECRET_KEY) -> str:
    claims = {"sub": "admin", "tenant_id": "T001", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    return jwt.encode(claims, secret, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_a_terminal_jwt_names_its_tenant_and_store():
    caller = await get_grpc_caller([("authorization", f"Bearer {_terminal_token(store_code='S001')}")])

    assert caller == GrpcCaller("T001", "S001")


@pytest.mark.asyncio
async def test_a_user_jwt_names_its_tenant_and_no_store():
    caller = await get_grpc_caller([("authorization", f"Bearer {_user_token()}")])

    assert caller == GrpcCaller("T001", None)


@pytest.mark.asyncio
async def test_an_api_key_names_the_tenant_and_store_of_its_terminal():
    terminal = TerminalInfoDocument(tenant_id="T001", store_code="S001", terminal_no=1, terminal_id="T001-S001-01")
    with patch("kugel_common.security.get_terminal_info", new_callable=AsyncMock, return_value=terminal) as lookup:
        caller = await get_grpc_caller([("x-api-key", "key"), ("terminal-id", "T001-S001-01")])

    lookup.assert_awaited_once_with("T001-S001-01", "key")
    assert caller == GrpcCaller("T001", "S001")


@pytest.mark.asyncio
async def test_an_api_key_the_terminal_service_rejects_is_refused():
    rejected = HTTPException(status_code=401, detail="Invalid API key")
    with (
        patch("kugel_common.security.get_terminal_info", new_callable=AsyncMock, side_effect=rejected),
        pytest.raises(HTTPException) as raised,
    ):
        await get_grpc_caller([("x-api-key", "wrong"), ("terminal-id", "T001-S001-01")])

    assert raised.value.status_code == 401


@pytest.mark.parametrize(
    "metadata",
    [
        [],
        None,
        [("x-api-key", "key")],
        [("terminal-id", "T001-S001-01")],
        [("authorization", "Basic abc")],
        [("authorization", "Bearer ")],
    ],
)
@pytest.mark.asyncio
async def test_a_call_without_a_credential_is_refused(metadata):
    with pytest.raises(HTTPException) as raised:
        await get_grpc_caller(metadata)

    assert raised.value.status_code == 401


@pytest.mark.asyncio
async def test_a_token_signed_with_another_key_is_refused():
    with pytest.raises(HTTPException) as raised:
        await get_grpc_caller([("authorization", f"Bearer {_user_token(secret='x' * 32)}")])

    assert raised.value.status_code == 401


@pytest.mark.asyncio
async def test_a_terminal_jwt_naming_no_store_is_refused():
    """A terminal credential without a store must not reach every store of its tenant."""
    with pytest.raises(HTTPException) as raised:
        await get_grpc_caller([("authorization", f"Bearer {_terminal_token()}")])

    assert raised.value.status_code == 401


@pytest.mark.asyncio
async def test_an_api_key_whose_terminal_names_no_store_is_refused():
    terminal = TerminalInfoDocument(tenant_id="T001", terminal_no=1, terminal_id="T001-S001-01")
    with (
        patch("kugel_common.security.get_terminal_info", new_callable=AsyncMock, return_value=terminal),
        pytest.raises(HTTPException) as raised,
    ):
        await get_grpc_caller([("x-api-key", "key"), ("terminal-id", "T001-S001-01")])

    assert raised.value.status_code == 401
