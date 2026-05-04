# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
import pytest
from unittest.mock import AsyncMock, MagicMock

from kugel_common.exceptions import DocumentNotFoundException, DocumentAlreadyExistsException

from app.services.item_common_master_service import ItemCommonMasterService
from app.models.documents.item_common_master_document import ItemCommonMasterDocument



# ---------------------------------------------------------------------------
# ItemCommonMasterService
# ---------------------------------------------------------------------------

class TestItemCommonMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return ItemCommonMasterService(item_common_master_repo=repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, repo):
        repo.get_item_by_code_async.return_value = None
        doc = ItemCommonMasterDocument()
        repo.create_item_async.return_value = doc

        result = await service.create_item_async("ITEM-01", "Item 1", 100.0, 80.0, [], [], "CAT-01", "TAX-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, repo):
        repo.get_item_by_code_async.return_value = MagicMock(tenant_id="T001")

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_item_async("ITEM-01", "Item 1", 100.0, 80.0, [], [], "CAT-01", "TAX-01")

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, repo):
        doc = ItemCommonMasterDocument()
        repo.get_item_by_code_async.return_value = doc

        result = await service.get_item_by_code_async("ITEM-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_code_not_found_raises(self, service, repo):
        repo.get_item_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_item_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_all_items(self, service, repo):
        repo.get_item_by_filter_async.return_value = []
        await service.get_item_all_async(limit=10, page=1, sort=[])
        repo.get_item_by_filter_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_items_paginated(self, service, repo):
        mock_list = [ItemCommonMasterDocument()]
        repo.get_item_by_filter_async.return_value = mock_list
        repo.get_item_count_by_filter_async.return_value = 5

        result, count = await service.get_item_all_paginated_async(limit=10, page=1, sort=[])
        assert result == mock_list
        assert count == 5

    @pytest.mark.asyncio
    async def test_update_success(self, service, repo):
        doc = ItemCommonMasterDocument()
        repo.get_item_by_code_async.return_value = doc
        updated = ItemCommonMasterDocument()
        repo.update_item_async.return_value = updated

        result = await service.update_item_async("ITEM-01", {"description": "New"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_item_code_mismatch_raises(self, service, repo):
        """item_code in update_data must match the path item_code."""
        with pytest.raises(Exception):  # InvalidRequestDataException
            await service.update_item_async("ITEM-01", {"item_code": "ITEM-XX"})

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, repo):
        repo.get_item_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_item_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_physical_success(self, service, repo):
        """Physical delete (is_logical=False): uses get_item_by_filter_async."""
        repo.get_item_by_filter_async.return_value = [ItemCommonMasterDocument()]

        await service.delete_item_async("ITEM-01", is_logical=False)
        repo.delete_item_async.assert_called_once_with("ITEM-01", False)

    @pytest.mark.asyncio
    async def test_delete_logical_success(self, service, repo):
        """Logical delete (is_logical=True): uses get_item_by_code_async."""
        repo.get_item_by_code_async.return_value = ItemCommonMasterDocument()

        await service.delete_item_async("ITEM-01", is_logical=True)
        repo.delete_item_async.assert_called_once_with("ITEM-01", True)

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.get_item_by_filter_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_item_async("NONEXISTENT", is_logical=False)


# ---------------------------------------------------------------------------
# ItemStoreMasterService
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# ItemCommonMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestItemCommonMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return ItemCommonMasterService(item_common_master_repo=repo)

    @pytest.mark.asyncio
    async def test_update_removes_item_code_from_data(self, service, repo):
        """Line 178: item_code is removed from update_data when it matches."""
        doc = ItemCommonMasterDocument()
        repo.get_item_by_code_async.return_value = doc
        updated = ItemCommonMasterDocument()
        repo.update_item_async.return_value = updated

        data = {"item_code": "ITEM-01", "description": "New"}
        result = await service.update_item_async("ITEM-01", data)

        assert result == updated
        call_args = repo.update_item_async.call_args
        assert "item_code" not in call_args[0][1]


# ---------------------------------------------------------------------------
# TaxMasterService - additional coverage
# ---------------------------------------------------------------------------
