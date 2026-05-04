# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
import pytest
from unittest.mock import AsyncMock, MagicMock

from kugel_common.exceptions import DocumentNotFoundException, DocumentAlreadyExistsException, InvalidRequestDataException

from app.services.item_store_master_service import ItemStoreMasterService
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from app.models.documents.item_common_master_document import ItemCommonMasterDocument



# ---------------------------------------------------------------------------
# ItemStoreMasterService
# ---------------------------------------------------------------------------

class TestItemStoreMasterService:
    @pytest.fixture
    def store_repo(self):
        return AsyncMock()

    @pytest.fixture
    def common_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, store_repo, common_repo):
        return ItemStoreMasterService(
            item_store_master_repo=store_repo,
            item_common_master_repo=common_repo,
        )

    @pytest.mark.asyncio
    async def test_create_success(self, service, store_repo, common_repo):
        common_repo.get_item_by_code_async.return_value = ItemCommonMasterDocument()
        store_repo.get_item_store_by_code.return_value = None
        doc = ItemStoreMasterDocument()
        store_repo.create_item_store_async.return_value = doc

        result = await service.create_item_async("ITEM-01", 120.0)
        assert result == doc

    @pytest.mark.asyncio
    async def test_create_common_item_not_found_raises(self, service, store_repo, common_repo):
        common_repo.get_item_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.create_item_async("NONEXISTENT", 120.0)

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, store_repo, common_repo):
        common_repo.get_item_by_code_async.return_value = ItemCommonMasterDocument()
        store_repo.get_item_store_by_code.return_value = MagicMock(tenant_id="T001")

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_item_async("ITEM-01", 120.0)

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, store_repo, common_repo):
        doc = ItemStoreMasterDocument()
        store_repo.get_item_store_by_code.return_value = doc

        result = await service.get_item_by_code_async("ITEM-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_code_not_found_raises(self, service, store_repo, common_repo):
        store_repo.get_item_store_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_item_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_all_items(self, service, store_repo, common_repo):
        store_repo.get_item_store_by_filter_async.return_value = []
        await service.get_item_all_async(limit=10, page=1, sort=[])
        store_repo.get_item_store_by_filter_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_items_paginated(self, service, store_repo, common_repo):
        mock_list = [ItemStoreMasterDocument()]
        store_repo.get_item_store_by_filter_async.return_value = mock_list
        store_repo.get_item_count_by_filter_async.return_value = 3

        result, count = await service.get_item_all_paginated_async(limit=10, page=1, sort=[])
        assert result == mock_list
        assert count == 3

    @pytest.mark.asyncio
    async def test_update_success(self, service, store_repo, common_repo):
        doc = ItemStoreMasterDocument()
        store_repo.get_item_store_by_code.return_value = doc
        updated = ItemStoreMasterDocument()
        store_repo.update_item_store_async.return_value = updated

        result = await service.update_item_async("ITEM-01", {"store_price": 150.0})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, store_repo, common_repo):
        store_repo.get_item_store_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_item_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_success(self, service, store_repo, common_repo):
        doc = ItemStoreMasterDocument()
        store_repo.get_item_store_by_code.return_value = doc
        store_repo.delete_item_store_async.return_value = None

        await service.delete_item_async("ITEM-01")
        store_repo.delete_item_store_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, store_repo, common_repo):
        store_repo.get_item_store_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_item_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# PaymentMasterService - additional coverage
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# ItemStoreMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestItemStoreMasterServiceAdditional:
    @pytest.fixture
    def store_repo(self):
        return AsyncMock()

    @pytest.fixture
    def common_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, store_repo, common_repo):
        return ItemStoreMasterService(
            item_store_master_repo=store_repo,
            item_common_master_repo=common_repo,
        )

    @pytest.mark.asyncio
    async def test_get_item_store_detail_with_store_data(self, service, store_repo, common_repo):
        """Lines 153-192: get detail combining common and store data."""
        common_doc = ItemCommonMasterDocument()
        common_doc.tenant_id = "T1"
        common_doc.item_code = "ITEM-01"
        common_doc.description = "Test Item"
        common_doc.description_short = "TI"
        common_doc.description_long = "Test Item Long"
        common_doc.unit_price = 100.0
        common_doc.unit_cost = 80.0
        common_doc.item_details = []
        common_doc.image_urls = []
        common_doc.category_code = "CAT-01"
        common_doc.tax_code = "TAX-01"
        common_doc.is_discount_restricted = False
        common_doc.updated_at = "2025-01-01"
        common_doc.created_at = "2025-01-01"
        common_repo.get_item_by_code_async.return_value = common_doc

        store_doc = ItemStoreMasterDocument()
        store_doc.store_code = "S1"
        store_doc.store_price = 120.0
        store_doc.updated_at = "2025-02-01"
        store_doc.created_at = "2025-02-01"
        store_repo.get_item_store_by_code.return_value = store_doc

        result = await service.get_item_store_detail_by_code_async("ITEM-01")

        assert result.item_code == "ITEM-01"
        assert result.store_code == "S1"
        assert result.store_price == 120.0
        assert result.description == "Test Item"

    @pytest.mark.asyncio
    async def test_get_item_store_detail_no_store_data(self, service, store_repo, common_repo):
        """Lines 181-184: store data not found, only common data returned."""
        common_doc = ItemCommonMasterDocument()
        common_doc.tenant_id = "T1"
        common_doc.item_code = "ITEM-01"
        common_doc.description = "Test Item"
        common_doc.unit_price = 100.0
        common_doc.unit_cost = 80.0
        common_repo.get_item_by_code_async.return_value = common_doc

        store_repo.get_item_store_by_code.return_value = None

        result = await service.get_item_store_detail_by_code_async("ITEM-01")

        assert result.item_code == "ITEM-01"
        assert result.store_code is None
        assert result.store_price is None

    @pytest.mark.asyncio
    async def test_get_item_store_detail_common_not_found_raises(self, service, store_repo, common_repo):
        """Lines 160-162: common item not found raises DocumentNotFoundException."""
        common_repo.get_item_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_item_store_detail_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_update_item_code_mismatch_raises(self, service, store_repo, common_repo):
        """Lines 211-213: item_code in update_data differs from path."""
        with pytest.raises(InvalidRequestDataException):
            await service.update_item_async(
                "ITEM-01", {"item_code": "ITEM-XX", "store_price": 150.0}
            )

    @pytest.mark.asyncio
    async def test_update_removes_item_code_from_data(self, service, store_repo, common_repo):
        """Lines 223-224: item_code is removed from update_data before repo call."""
        doc = ItemStoreMasterDocument()
        store_repo.get_item_store_by_code.return_value = doc
        updated = ItemStoreMasterDocument()
        store_repo.update_item_store_async.return_value = updated

        data = {"item_code": "ITEM-01", "store_price": 150.0}
        result = await service.update_item_async("ITEM-01", data)

        assert result == updated
        call_args = store_repo.update_item_store_async.call_args
        assert "item_code" not in call_args[0][1]
