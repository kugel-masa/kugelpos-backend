# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.grpc_client_helper.

The pool is a module-level dict so each test clears it explicitly.
gRPC channel creation is mocked via patch — we never actually connect.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kugel_common.utils import grpc_client_helper as gch


@pytest.fixture(autouse=True)
def _clear_pool():
    """Clear the module-level channel pool before and after each test."""
    gch._grpc_client_pool.clear()
    yield
    gch._grpc_client_pool.clear()


class TestGrpcClientHelperConstruction:
    def test_target_stored(self):
        helper = gch.GrpcClientHelper(target="localhost:50051")
        assert helper.target == "localhost:50051"

    def test_default_options_present(self):
        helper = gch.GrpcClientHelper(target="localhost:50051")
        keys = {opt[0] for opt in helper.options}
        assert "grpc.max_send_message_length" in keys
        assert "grpc.keepalive_time_ms" in keys

    def test_custom_options_override_defaults(self):
        custom = [("grpc.x", 1)]
        helper = gch.GrpcClientHelper(target="localhost:50051", options=custom)
        assert helper.options == custom


class TestGetChannel:
    @pytest.mark.asyncio
    async def test_creates_channel_first_time(self):
        with patch("grpc.aio.insecure_channel", return_value=MagicMock()) as mock_create:
            helper = gch.GrpcClientHelper(target="server:1234")
            channel = await helper.get_channel()
        mock_create.assert_called_once()
        assert "server:1234" in gch._grpc_client_pool

    @pytest.mark.asyncio
    async def test_reuses_pooled_channel(self):
        with patch("grpc.aio.insecure_channel", return_value=MagicMock()) as mock_create:
            helper = gch.GrpcClientHelper(target="server:1234")
            ch1 = await helper.get_channel()
            ch2 = await helper.get_channel()
        assert ch1 is ch2
        assert mock_create.call_count == 1


class TestCloseAll:
    @pytest.mark.asyncio
    async def test_close_all_via_helper_clears_pool(self):
        ch = MagicMock()
        ch.close = AsyncMock()
        gch._grpc_client_pool["server:1234"] = ch

        helper = gch.GrpcClientHelper(target="server:1234")
        await helper.close_all()

        ch.close.assert_awaited_once()
        assert gch._grpc_client_pool == {}

    @pytest.mark.asyncio
    async def test_close_all_module_function(self):
        ch1 = MagicMock()
        ch1.close = AsyncMock()
        ch2 = MagicMock()
        ch2.close = AsyncMock()
        gch._grpc_client_pool["a:1"] = ch1
        gch._grpc_client_pool["b:2"] = ch2

        await gch.close_all_grpc_channels()
        ch1.close.assert_awaited_once()
        ch2.close.assert_awaited_once()
        assert gch._grpc_client_pool == {}

    @pytest.mark.asyncio
    async def test_close_all_swallows_individual_close_errors(self):
        bad = MagicMock()
        bad.close = AsyncMock(side_effect=RuntimeError("boom"))
        good = MagicMock()
        good.close = AsyncMock()
        gch._grpc_client_pool["bad:1"] = bad
        gch._grpc_client_pool["good:2"] = good

        await gch.close_all_grpc_channels()
        # Both attempted
        bad.close.assert_awaited_once()
        good.close.assert_awaited_once()
        # Pool cleared even though one failed
        assert gch._grpc_client_pool == {}
