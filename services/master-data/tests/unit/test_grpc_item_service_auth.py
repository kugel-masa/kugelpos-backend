# Copyright 2026 masa@kugel
"""GetItemDetail serves only the tenant and store its caller authenticated for (issue #134).

The RPC read whichever tenant's database the request named, with no
credential at all, on a port the compose files published to the host.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest
from fastapi import HTTPException
from kugel_common.grpc import item_service_pb2
from kugel_common.security import GrpcCaller

from app.grpc.item_service_impl import ItemServiceImpl

MODULE = "app.grpc.item_service_impl"


def _request(tenant_id: str = "T001", store_code: str = "S001") -> item_service_pb2.ItemDetailRequest:
    return item_service_pb2.ItemDetailRequest(tenant_id=tenant_id, store_code=store_code, item_code="ITEM001")


def _context() -> MagicMock:
    context = MagicMock()
    context.invocation_metadata.return_value = (("authorization", "Bearer token"),)
    return context


def _item() -> MagicMock:
    item = MagicMock(
        item_code="ITEM001",
        description="Item",
        store_price=None,
        unit_price=100,
        tax_code="01",
        category_code="C1",
        is_deleted=False,
        created_at=None,
        updated_at=None,
    )
    return item


async def _call(caller, request):
    master_service = MagicMock()
    master_service.get_item_store_detail_by_code_async = AsyncMock(return_value=_item())
    context = _context()
    with (
        patch(f"{MODULE}.get_grpc_caller", new_callable=AsyncMock, **caller) as get_caller,
        patch(f"{MODULE}.get_item_store_master_service_async", new_callable=AsyncMock, return_value=master_service) as get_service,
    ):
        response = await ItemServiceImpl().GetItemDetail(request, context)
    get_caller.assert_awaited_once_with(context.invocation_metadata.return_value)
    return response, context, get_service


@pytest.mark.asyncio
async def test_the_callers_own_tenant_and_store_are_served():
    response, context, get_service = await _call({"return_value": GrpcCaller("T001", "S001")}, _request())

    get_service.assert_awaited_once_with("T001", "S001")
    assert response.item_code == "ITEM001"
    context.set_code.assert_not_called()


@pytest.mark.asyncio
async def test_a_caller_without_a_store_is_served_any_store_of_its_tenant():
    response, _context, get_service = await _call({"return_value": GrpcCaller("T001", None)}, _request(store_code="S999"))

    get_service.assert_awaited_once_with("T001", "S999")
    assert response.item_code == "ITEM001"


@pytest.mark.asyncio
async def test_a_call_without_a_valid_credential_is_unauthenticated():
    rejected = HTTPException(status_code=401, detail="Could not validate credentials")
    response, context, get_service = await _call({"side_effect": rejected}, _request())

    context.set_code.assert_called_once_with(grpc.StatusCode.UNAUTHENTICATED)
    get_service.assert_not_awaited()
    assert response.item_code == ""


@pytest.mark.parametrize("tenant_id,store_code", [("T-OTHER", "S001"), ("T001", "S-OTHER")])
@pytest.mark.asyncio
async def test_another_tenant_or_store_is_denied(tenant_id, store_code):
    response, context, get_service = await _call(
        {"return_value": GrpcCaller("T001", "S001")}, _request(tenant_id, store_code)
    )

    context.set_code.assert_called_once_with(grpc.StatusCode.PERMISSION_DENIED)
    get_service.assert_not_awaited()
    assert response.item_code == ""


@pytest.mark.asyncio
async def test_an_internal_error_does_not_reach_the_caller():
    context = _context()
    with (
        patch(f"{MODULE}.get_grpc_caller", new_callable=AsyncMock, return_value=GrpcCaller("T001", "S001")),
        patch(
            f"{MODULE}.get_item_store_master_service_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("mongodb://user:secret@db"),
        ),
    ):
        await ItemServiceImpl().GetItemDetail(_request(), context)

    context.set_code.assert_called_once_with(grpc.StatusCode.INTERNAL)
    context.set_details.assert_called_once_with("Internal error")


@pytest.mark.asyncio
async def test_the_credential_travels_as_metadata_over_a_real_channel():
    """A real server and channel, so the metadata the cart sends is what the servicer reads."""
    from grpc import aio
    from kugel_common.grpc import item_service_pb2_grpc
    from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
    from kugel_common.utils.terminal_auth import create_terminal_token

    token = create_terminal_token(
        TerminalInfoDocument(tenant_id="T001", store_code="S001", terminal_no=1, terminal_id="T001-S001-01")
    )
    master_service = MagicMock()
    master_service.get_item_store_detail_by_code_async = AsyncMock(return_value=_item())

    server = aio.server()
    item_service_pb2_grpc.add_ItemServiceServicer_to_server(ItemServiceImpl(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        with patch(f"{MODULE}.get_item_store_master_service_async", new_callable=AsyncMock, return_value=master_service):
            async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = item_service_pb2_grpc.ItemServiceStub(channel)

                served = await stub.GetItemDetail(_request(), metadata=[("authorization", f"Bearer {token}")])
                assert served.item_code == "ITEM001"

                with pytest.raises(grpc.RpcError) as unauthenticated:
                    await stub.GetItemDetail(_request())
                assert unauthenticated.value.code() == grpc.StatusCode.UNAUTHENTICATED

                with pytest.raises(grpc.RpcError) as denied:
                    await stub.GetItemDetail(_request(tenant_id="T-OTHER"), metadata=[("authorization", f"Bearer {token}")])
                assert denied.value.code() == grpc.StatusCode.PERMISSION_DENIED
    finally:
        await server.stop(grace=None)
