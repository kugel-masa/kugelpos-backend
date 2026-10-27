# Copyright 2026 masa@kugel
"""cart reaches master-data's gRPC directly by default, or through the local Dapr sidecar when MASTER_DATA_GRPC_APP_ID is set.

The Dapr route mirrors the stpos fork (its #951), so the same code runs in a
deployment that routes through Dapr and in one that does not.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest
from kugel_common.grpc import item_service_pb2, item_service_pb2_grpc

import app.utils.grpc_channel_helper as channel_helper
from app.config.settings_cart import cart_settings


@pytest.fixture(autouse=True)
def clear_channel_cache():
    channel_helper._channels.clear()
    channel_helper._stubs.clear()
    yield
    channel_helper._channels.clear()
    channel_helper._stubs.clear()


async def _helper_arguments(monkeypatch, app_id: str) -> dict:
    monkeypatch.setattr(cart_settings, "MASTER_DATA_GRPC_APP_ID", app_id)
    monkeypatch.setattr(cart_settings, "DAPR_GRPC_PORT", 50001)
    monkeypatch.setattr(cart_settings, "MASTER_DATA_GRPC_URL", "master-data:50051")
    with patch("app.utils.grpc_channel_helper.GrpcClientHelper") as helper_class:
        helper_class.return_value.get_channel = AsyncMock(return_value=MagicMock())
        await channel_helper.get_master_data_grpc_stub("T001", "S001")
    return helper_class.call_args.kwargs


@pytest.mark.asyncio
async def test_without_an_app_id_the_channel_goes_straight_to_master_data(monkeypatch):
    kwargs = await _helper_arguments(monkeypatch, "")

    assert kwargs["target"] == "master-data:50051"
    assert kwargs["interceptors"] is None
    assert kwargs["pool_key"] == "master-data:50051"


@pytest.mark.asyncio
async def test_with_an_app_id_the_channel_goes_to_the_local_sidecar(monkeypatch):
    kwargs = await _helper_arguments(monkeypatch, "master-data-grpc")

    assert kwargs["target"] == "localhost:50001"
    assert [type(i) for i in kwargs["interceptors"]] == [channel_helper._DaprAppIdInterceptor]
    assert kwargs["pool_key"] == "localhost:50001#master-data-grpc"


class _RecordingItemService(item_service_pb2_grpc.ItemServiceServicer):
    def __init__(self):
        self.metadata: dict[str, str] = {}

    async def GetItemDetail(self, request, context):
        self.metadata = dict(context.invocation_metadata())
        return item_service_pb2.ItemDetailResponse(item_code=request.item_code)


@pytest.mark.asyncio
async def test_the_app_id_is_added_and_the_credential_kept_over_a_real_channel():
    """What a Dapr sidecar would receive: dapr-app-id to route by, and the terminal's credential to forward."""
    servicer = _RecordingItemService()
    server = grpc.aio.server()
    item_service_pb2_grpc.add_ItemServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        async with grpc.aio.insecure_channel(
            f"127.0.0.1:{port}", interceptors=[channel_helper._DaprAppIdInterceptor("master-data-grpc")]
        ) as channel:
            stub = item_service_pb2_grpc.ItemServiceStub(channel)
            response = await stub.GetItemDetail(
                item_service_pb2.ItemDetailRequest(item_code="ITEM001"),
                metadata=[("authorization", "Bearer terminal.jwt")],
            )
    finally:
        await server.stop(grace=None)

    assert response.item_code == "ITEM001"
    assert servicer.metadata["dapr-app-id"] == "master-data-grpc"
    assert servicer.metadata["authorization"] == "Bearer terminal.jwt"
