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

from app.services.staff_master_service import StaffMasterService
from app.models.documents.staff_master_document import StaffMasterDocument



# ---------------------------------------------------------------------------
# StaffMasterService
# ---------------------------------------------------------------------------

class TestStaffMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return StaffMasterService(staff_master_repo=repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, repo):
        repo.get_staff_by_id_async.return_value = None
        doc = StaffMasterDocument()
        repo.create_staff_async.return_value = doc

        result = await service.create_staff_async("ST01", "Alice", "1234", ["cashier"])
        assert result == doc

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, repo):
        repo.get_staff_by_id_async.return_value = MagicMock(tenant_id="T001")

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_staff_async("ST01", "Alice", "1234", [])

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, service, repo):
        doc = StaffMasterDocument()
        repo.get_staff_by_id_async.return_value = doc

        result = await service.get_staff_by_id_async("ST01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_raises(self, service, repo):
        repo.get_staff_by_id_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_staff_by_id_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_all_staff(self, service, repo):
        repo.get_staff_by_filter_async.return_value = []
        await service.get_staff_all_async(limit=10, page=1, sort=[])
        repo.get_staff_by_filter_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_staff_paginated(self, service, repo):
        """Returns (list, count) from two separate repo calls."""
        mock_list = [StaffMasterDocument()]
        repo.get_staff_by_filter_async.return_value = mock_list
        repo.get_staff_count_async.return_value = 5

        result, count = await service.get_staff_all_paginated_async(limit=10, page=1, sort=[])
        assert result == mock_list
        assert count == 5

    @pytest.mark.asyncio
    async def test_update_success(self, service, repo):
        doc = StaffMasterDocument()
        repo.get_staff_by_id_async.return_value = doc
        updated = StaffMasterDocument()
        repo.update_staff_async.return_value = updated

        result = await service.update_staff_async("ST01", {"staff_name": "Bob"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, repo):
        repo.get_staff_by_id_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_staff_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_success(self, service, repo):
        doc = StaffMasterDocument()
        repo.get_staff_by_id_async.return_value = doc
        repo.delete_staff_async.return_value = None

        await service.delete_staff_async("ST01")
        repo.delete_staff_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.get_staff_by_id_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_staff_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# TaxMasterService
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# StaffMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestStaffMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return StaffMasterService(staff_master_repo=repo)

    @pytest.mark.asyncio
    async def test_update_id_mismatch_raises(self, service, repo):
        """Lines 132-134: id in update_data differs from path staff_id."""
        with pytest.raises(InvalidRequestDataException):
            await service.update_staff_async(
                "ST01", {"id": "ST-OTHER", "staff_name": "Bob"}
            )

    @pytest.mark.asyncio
    async def test_update_removes_id_from_data(self, service, repo):
        """Line 145: id is removed from update_data before repo call."""
        doc = StaffMasterDocument()
        repo.get_staff_by_id_async.return_value = doc
        updated = StaffMasterDocument()
        repo.update_staff_async.return_value = updated

        data = {"id": "ST01", "staff_name": "Bob"}
        result = await service.update_staff_async("ST01", data)

        assert result == updated
        call_args = repo.update_staff_async.call_args
        assert "id" not in call_args[0][1]


# ---------------------------------------------------------------------------
# ItemCommonMasterService - additional coverage
# ---------------------------------------------------------------------------
