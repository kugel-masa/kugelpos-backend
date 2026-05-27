# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Unit tests for ItemMasterGrpcRepository on the shared cache base.

Caching behavior is owned by AbstractMasterDataRepository and exercised in
test_abstract_master_data_repository.py. These tests focus on what the gRPC
subclass is uniquely responsible for: invoking the channel helper with the
right request and translating responses / errors into ItemMasterDocument /
exceptions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import grpc

from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend

from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
import app.utils.grpc_channel_helper as channel_helper


@pytest.fixture
def terminal_info():
    return TerminalInfoDocument(
        terminal_id="TEST001",
        store_code="STORE01",
        terminal_name="Test Terminal",
    )


@pytest.fixture
def repository(terminal_info):
    return ItemMasterGrpcRepository(
        tenant_id="test_tenant",
        store_code="STORE01",
        terminal_info=terminal_info,
        cache_backend=InMemoryCacheBackend(),
    )


@pytest.fixture(autouse=True)
def clear_channel_cache():
    channel_helper._channels.clear()
    channel_helper._stubs.clear()
    yield
    channel_helper._channels.clear()
    channel_helper._stubs.clear()


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_invokes_channel_helper_with_tenant_and_store(repository):
    """Patch where the name is used (repository module), not the helper module."""
    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new_callable=AsyncMock,
    ) as mock_get_stub:
        mock_stub = MagicMock()
        mock_response = MagicMock(
            item_code="ITEM001",
            item_name="Test Item",
            price=100.0,
            tax_code="T1",
            category_code="CAT1",
            is_active=True,
        )
        mock_stub.GetItemDetail = AsyncMock(return_value=mock_response)
        mock_get_stub.return_value = mock_stub

        item = await repository.get_item_by_code_async("ITEM001")

        mock_get_stub.assert_called_once_with("test_tenant", "STORE01")
        assert item.item_code == "ITEM001"
        assert item.description == "Test Item"
        assert item.unit_price == 100.0
        assert item.tax_code == "T1"
        assert item.category_code == "CAT1"


@pytest.mark.asyncio
async def test_fetch_constructs_request_with_terminal_id(repository):
    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new_callable=AsyncMock,
    ) as mock_get_stub:
        mock_stub = MagicMock()
        mock_response = MagicMock(
            item_code="ITEM001", item_name="x", price=1.0,
            tax_code="T", category_code="C", is_active=True,
        )
        mock_stub.GetItemDetail = AsyncMock(return_value=mock_response)
        mock_get_stub.return_value = mock_stub

        await repository.get_item_by_code_async("ITEM001")

        request = mock_stub.GetItemDetail.call_args[0][0]
        assert request.tenant_id == "test_tenant"
        assert request.store_code == "STORE01"
        assert request.item_code == "ITEM001"
        assert request.terminal_id == "TEST001"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_item_code_in_response_raises_not_found(repository):
    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new_callable=AsyncMock,
    ) as mock_get_stub:
        mock_stub = MagicMock()
        empty = MagicMock(item_code="", item_name="", price=0.0,
                          tax_code="", category_code="", is_active=False)
        mock_stub.GetItemDetail = AsyncMock(return_value=empty)
        mock_get_stub.return_value = mock_stub

        with pytest.raises(NotFoundException):
            await repository.get_item_by_code_async("MISSING")


@pytest.mark.asyncio
async def test_grpc_not_found_maps_to_not_found_exception(repository):
    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new_callable=AsyncMock,
    ) as mock_get_stub:
        mock_stub = MagicMock()
        rpc_error = grpc.RpcError()
        rpc_error.code = lambda: grpc.StatusCode.NOT_FOUND
        rpc_error.details = lambda: "not found"
        mock_stub.GetItemDetail = AsyncMock(side_effect=rpc_error)
        mock_get_stub.return_value = mock_stub

        with pytest.raises(NotFoundException):
            await repository.get_item_by_code_async("ITEM_X")


@pytest.mark.asyncio
async def test_other_grpc_error_maps_to_repository_exception(repository):
    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new_callable=AsyncMock,
    ) as mock_get_stub:
        mock_stub = MagicMock()
        rpc_error = grpc.RpcError()
        rpc_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        rpc_error.details = lambda: "service down"
        mock_stub.GetItemDetail = AsyncMock(side_effect=rpc_error)
        mock_get_stub.return_value = mock_stub

        with pytest.raises(RepositoryException):
            await repository.get_item_by_code_async("ITEM_X")


@pytest.mark.asyncio
async def test_generic_exception_maps_to_repository_exception(repository):
    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new_callable=AsyncMock,
    ) as mock_get_stub:
        mock_stub = MagicMock()
        mock_stub.GetItemDetail = AsyncMock(side_effect=RuntimeError("boom"))
        mock_get_stub.return_value = mock_stub

        with pytest.raises(RepositoryException):
            await repository.get_item_by_code_async("ITEM_X")
