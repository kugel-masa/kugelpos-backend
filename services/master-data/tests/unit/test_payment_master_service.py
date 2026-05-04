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

from app.services.payment_master_service import PaymentMasterService
from app.models.documents.payment_master_document import PaymentMasterDocument



# ---------------------------------------------------------------------------
# PaymentMasterService
# ---------------------------------------------------------------------------

class TestPaymentMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return PaymentMasterService(payment_master_repository=repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, repo):
        repo.get_payment_by_code.return_value = None
        doc = PaymentMasterDocument()
        repo.create_payment_async.return_value = doc

        result = await service.create_payment_async("PAY-01", "Cash", "Cash payment", 0, 1, [], [])
        assert result == doc

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, repo):
        repo.get_payment_by_code.return_value = MagicMock(tenant_id="T001")

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_payment_async("PAY-01", "Cash", "Cash payment", 0, 1, [], [])

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, repo):
        doc = PaymentMasterDocument()
        repo.get_payment_by_code.return_value = doc

        result = await service.get_payment_by_code("PAY-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_code_returns_none_when_not_found(self, service, repo):
        """get_payment_by_code is a pass-through — returns None without raising."""
        repo.get_payment_by_code.return_value = None

        result = await service.get_payment_by_code("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_payments(self, service, repo):
        repo.get_payment_by_filter_async.return_value = []
        await service.get_all_payments(limit=10, page=1, sort=[])
        repo.get_payment_by_filter_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_payments_paginated(self, service, repo):
        """Returns (list, total_count) from two separate repo calls."""
        mock_list = [PaymentMasterDocument()]
        repo.get_payment_by_filter_async.return_value = mock_list
        repo.get_payment_count_by_filter_async.return_value = 10

        result, total = await service.get_all_payments_paginated(limit=10, page=1, sort=[])
        assert result == mock_list
        assert total == 10

    @pytest.mark.asyncio
    async def test_update_success(self, service, repo):
        doc = PaymentMasterDocument()
        repo.get_payment_by_code.return_value = doc
        updated = PaymentMasterDocument()
        repo.update_payment_async.return_value = updated

        result = await service.update_payment_async("PAY-01", {"description": "Updated"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, repo):
        repo.get_payment_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_payment_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_success(self, service, repo):
        doc = PaymentMasterDocument()
        repo.get_payment_by_code.return_value = doc
        repo.delete_payment_async.return_value = None

        await service.delete_payment_async("PAY-01")
        repo.delete_payment_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.get_payment_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_payment_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# StaffMasterService
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# PaymentMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestPaymentMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return PaymentMasterService(payment_master_repository=repo)

    @pytest.mark.asyncio
    async def test_update_payment_code_mismatch_raises(self, service, repo):
        """Lines 143-145: payment_code in update_data differs from path."""
        with pytest.raises(InvalidRequestDataException):
            await service.update_payment_async(
                "PAY-01", {"payment_code": "PAY-XX", "description": "Updated"}
            )

    @pytest.mark.asyncio
    async def test_update_removes_payment_code_from_data(self, service, repo):
        """Line 155: payment_code is removed from update_data before repo call."""
        doc = PaymentMasterDocument()
        repo.get_payment_by_code.return_value = doc
        updated = PaymentMasterDocument()
        repo.update_payment_async.return_value = updated

        data = {"payment_code": "PAY-01", "description": "Updated"}
        result = await service.update_payment_async("PAY-01", data)

        assert result == updated
        # Verify payment_code was removed before passing to repo
        call_args = repo.update_payment_async.call_args
        assert "payment_code" not in call_args[0][1]


# ---------------------------------------------------------------------------
# StaffMasterService - additional coverage
# ---------------------------------------------------------------------------
