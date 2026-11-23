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

from app.services.category_master_service import CategoryMasterService
from app.models.documents.category_master_document import CategoryMasterDocument



# ---------------------------------------------------------------------------
# CategoryMasterService
# ---------------------------------------------------------------------------

class TestCategoryMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return CategoryMasterService(category_master_repo=repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, repo):
        repo.get_category_by_code_async.return_value = None
        doc = CategoryMasterDocument()
        doc.category_code = "CAT-01"
        repo.create_category_async.return_value = doc

        result = await service.create_category_async("CAT-01", "Cat 1", "C1", "TAX-01")

        assert result == doc

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, repo):
        repo.get_category_by_code_async.return_value = MagicMock(tenant_id="T001", is_deleted=False)

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_category_async("CAT-01", "Cat 1", "C1", "TAX-01")

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, repo):
        doc = CategoryMasterDocument()
        doc.category_code = "CAT-01"
        repo.get_category_by_code_async.return_value = doc

        result = await service.get_category_by_code_async("CAT-01")

        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_code_not_found_raises(self, service, repo):
        repo.get_category_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_category_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_categories(self, service, repo):
        repo.get_category_by_filter_async.return_value = []
        result = await service.get_categories_async(limit=10, page=1, sort=[])
        repo.get_category_by_filter_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_categories_paginated(self, service, repo):
        mock_result = MagicMock()
        repo.get_category_by_filter_paginated_async.return_value = mock_result
        result = await service.get_categories_paginated_async(limit=10, page=1, sort=[])
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_update_success(self, service, repo):
        doc = CategoryMasterDocument()
        doc.category_code = "CAT-01"
        repo.get_category_by_code_async.return_value = doc
        updated = CategoryMasterDocument()
        repo.update_category_async.return_value = updated

        result = await service.update_category_async("CAT-01", {"description": "New"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, repo):
        repo.get_category_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_category_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_success(self, service, repo):
        repo.delete_category_async.return_value = True

        await service.delete_category_async("CAT-01")
        # Logical by default; the write itself decides whether it existed (issue #324)
        repo.delete_category_async.assert_called_once_with("CAT-01", True)

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.delete_category_async.return_value = False

        with pytest.raises(DocumentNotFoundException):
            await service.delete_category_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# PaymentMasterService
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Restore on create (issue #324)
# ---------------------------------------------------------------------------


class TestCategoryRestoreOnCreate:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        from app.services.category_master_service import CategoryMasterService

        return CategoryMasterService(repo)

    @pytest.mark.asyncio
    async def test_a_new_code_is_inserted(self, service, repo):
        repo.get_category_by_code_async.return_value = None

        await service.create_category_async("C1", "Cat", "C", "01")

        repo.get_category_by_code_async.assert_awaited_once_with("C1", include_deleted=True)
        repo.create_category_async.assert_awaited_once()
        repo.restore_category_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_deleted_code_is_restored(self, service, repo):
        repo.get_category_by_code_async.return_value = MagicMock(tenant_id="T001", is_deleted=True)
        repo.restore_category_async.return_value = True

        doc = await service.create_category_async("C1", "New", "N", "01")

        repo.restore_category_async.assert_awaited_once()
        assert repo.restore_category_async.await_args.args[0].description == "New"
        assert doc.description == "New"
        repo.create_category_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_restore_lost_to_another_answers_already_exists(self, service, repo):
        repo.get_category_by_code_async.return_value = MagicMock(tenant_id="T001", is_deleted=True)
        repo.restore_category_async.return_value = False

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_category_async("C1", "New", "N", "01")
