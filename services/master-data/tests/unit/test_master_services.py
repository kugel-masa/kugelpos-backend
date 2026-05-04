# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
from unittest.mock import AsyncMock, MagicMock

from kugel_common.exceptions import DocumentNotFoundException, DocumentAlreadyExistsException, InvalidRequestDataException

from app.services.category_master_service import CategoryMasterService
from app.models.documents.category_master_document import CategoryMasterDocument

from app.services.payment_master_service import PaymentMasterService
from app.models.documents.payment_master_document import PaymentMasterDocument

from app.services.staff_master_service import StaffMasterService
from app.models.documents.staff_master_document import StaffMasterDocument

from app.services.tax_master_service import TaxMasterService
from app.models.documents.tax_master_document import TaxMasterDocument

from app.services.settings_master_service import SettingsMasterService
from app.models.documents.settings_master_document import SettingsMasterDocument

from app.services.item_common_master_service import ItemCommonMasterService
from app.models.documents.item_common_master_document import ItemCommonMasterDocument

from app.services.item_store_master_service import ItemStoreMasterService
from app.models.documents.item_store_master_document import ItemStoreMasterDocument


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
        repo.get_category_by_code_async.return_value = MagicMock(tenant_id="T001")

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
        doc = CategoryMasterDocument()
        repo.get_category_by_code_async.return_value = doc
        repo.delete_category_async.return_value = None

        await service.delete_category_async("CAT-01")
        repo.delete_category_async.assert_called_once_with("CAT-01")

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.get_category_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_category_async("NONEXISTENT")


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

class TestTaxMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return TaxMasterService(tax_master_repo=repo)

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, repo):
        doc = TaxMasterDocument()
        repo.get_tax_by_code.return_value = doc

        result = await service.get_tax_by_code_async("TAX-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_code_not_found_raises(self, service, repo):
        repo.get_tax_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_tax_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_all_taxes(self, service, repo):
        repo.load_all_taxes.return_value = []
        await service.get_all_taxes_async()
        repo.load_all_taxes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_taxes_paginated(self, service, repo):
        """Returns (paginated_list, total_count) tuple."""
        taxes = [TaxMasterDocument(), TaxMasterDocument(), TaxMasterDocument()]
        repo.load_all_taxes.return_value = taxes

        result, total = await service.get_all_taxes_paginated_async(limit=2, page=1, sort=[])
        assert total == 3
        assert len(result) == 2


# ---------------------------------------------------------------------------
# SettingsMasterService
# ---------------------------------------------------------------------------

class TestSettingsMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return SettingsMasterService(settings_master_repo=repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, repo):
        repo.get_settings_by_name_async.return_value = None
        doc = SettingsMasterDocument()
        repo.create_settings_async.return_value = doc

        result = await service.create_settings_async("KEY-01", "value", [])
        assert result == doc

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, repo):
        repo.get_settings_by_name_async.return_value = MagicMock(tenant_id="T001")

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_settings_async("KEY-01", "value", [])

    @pytest.mark.asyncio
    async def test_get_by_name_success(self, service, repo):
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_by_name_async("KEY-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_name_returns_none_when_not_found(self, service, repo):
        """get_settings_by_name_async returns None (no raise) when not found."""
        repo.get_settings_by_name_async.return_value = None

        result = await service.get_settings_by_name_async("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_settings(self, service, repo):
        repo.get_settings_all_async.return_value = []
        await service.get_settings_all_async(limit=10, page=1, sort=[])
        repo.get_settings_all_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_settings_paginated(self, service, repo):
        """Returns (list, count) tuple from separate repo calls."""
        mock_list = [SettingsMasterDocument()]
        repo.get_settings_all_async.return_value = mock_list
        repo.get_settings_count_async.return_value = 5

        result, count = await service.get_settings_all_paginated_async(limit=10, page=1, sort=[])
        assert result == mock_list
        assert count == 5

    @pytest.mark.asyncio
    async def test_update_success(self, service, repo):
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        result = await service.update_settings_async("KEY-01", {"default_value": "new"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, repo):
        repo.get_settings_by_name_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_settings_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_success(self, service, repo):
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        repo.delete_settings_async.return_value = None

        await service.delete_settings_async("KEY-01")
        repo.delete_settings_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.get_settings_by_name_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_settings_async("NONEXISTENT")


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

class TestTaxMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return TaxMasterService(tax_master_repo=repo)

    @pytest.mark.asyncio
    async def test_get_all_taxes_paginated_with_reverse_sort(self, service, repo):
        """Lines 82-84: sort with direction=-1 (reverse)."""
        tax1 = TaxMasterDocument()
        tax1.tax_code = "A"
        tax2 = TaxMasterDocument()
        tax2.tax_code = "B"
        tax3 = TaxMasterDocument()
        tax3.tax_code = "C"
        repo.load_all_taxes.return_value = [tax1, tax2, tax3]

        result, total = await service.get_all_taxes_paginated_async(
            limit=10, page=1, sort=[("tax_code", -1)]
        )

        assert total == 3
        # Should be sorted in reverse order by tax_code
        assert result[0].tax_code == "C"
        assert result[1].tax_code == "B"
        assert result[2].tax_code == "A"

    @pytest.mark.asyncio
    async def test_get_all_taxes_paginated_ascending_sort(self, service, repo):
        """Sort with direction=1 (ascending)."""
        tax1 = TaxMasterDocument()
        tax1.tax_code = "C"
        tax2 = TaxMasterDocument()
        tax2.tax_code = "A"
        repo.load_all_taxes.return_value = [tax1, tax2]

        result, total = await service.get_all_taxes_paginated_async(
            limit=10, page=1, sort=[("tax_code", 1)]
        )

        assert total == 2
        assert result[0].tax_code == "A"
        assert result[1].tax_code == "C"


# ---------------------------------------------------------------------------
# SettingsMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestSettingsMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return SettingsMasterService(settings_master_repo=repo)

    @pytest.mark.asyncio
    async def test_get_settings_value_store_terminal_match(self, service, repo):
        """Lines 112-122: priority lookup - store+terminal specific match."""
        from app.models.documents.settings_master_document import SettingsValue

        doc = SettingsMasterDocument()
        doc.default_value = "default"
        doc.values = [
            SettingsValue(store_code="S1", terminal_no=1, value="store_terminal"),
            SettingsValue(store_code="S1", terminal_no=None, value="store_only"),
            SettingsValue(store_code=None, terminal_no=None, value="global"),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S1", 1)
        assert result == "store_terminal"

    @pytest.mark.asyncio
    async def test_get_settings_value_store_only_match(self, service, repo):
        """Priority lookup - store specific match (no terminal match)."""
        from app.models.documents.settings_master_document import SettingsValue

        doc = SettingsMasterDocument()
        doc.default_value = "default"
        doc.values = [
            SettingsValue(store_code="S1", terminal_no=None, value="store_only"),
            SettingsValue(store_code=None, terminal_no=None, value="global"),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S1", 99)
        assert result == "store_only"

    @pytest.mark.asyncio
    async def test_get_settings_value_global_match(self, service, repo):
        """Priority lookup - global match (no store/terminal match)."""
        from app.models.documents.settings_master_document import SettingsValue

        doc = SettingsMasterDocument()
        doc.default_value = "default"
        doc.values = [
            SettingsValue(store_code=None, terminal_no=None, value="global"),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S2", 1)
        assert result == "global"

    @pytest.mark.asyncio
    async def test_get_settings_value_falls_back_to_default(self, service, repo):
        """Lines 124-125: no values match, returns default_value."""
        doc = SettingsMasterDocument()
        doc.default_value = "fallback"
        doc.values = [
            MagicMock(
                model_dump=MagicMock(
                    return_value={"store_code": "OTHER", "terminal_no": 99, "value": "nope"}
                )
            ),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S1", 1)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_get_settings_value_not_found_raises(self, service, repo):
        """Lines 107-109: setting not found raises DocumentNotFoundException."""
        repo.get_settings_by_name_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_settings_value_by_name_async("MISSING", "S1", 1)

    @pytest.mark.asyncio
    async def test_update_name_mismatch_raises(self, service, repo):
        """Lines 176-178: name in update_data differs from path name."""
        with pytest.raises(InvalidRequestDataException):
            await service.update_settings_async(
                "KEY-01", {"name": "KEY-OTHER", "default_value": "new"}
            )

    @pytest.mark.asyncio
    async def test_update_removes_name_from_data(self, service, repo):
        """Lines 188-189: name is removed from update_data before repo call."""
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        data = {"name": "KEY-01", "default_value": "new"}
        result = await service.update_settings_async("KEY-01", data)

        assert result == updated
        call_args = repo.update_settings_async.call_args
        assert "name" not in call_args[0][1]

    @pytest.mark.asyncio
    async def test_update_processes_default_value_json(self, service, repo):
        """Lines 192-193: default_value is processed through ensure_json_format."""
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        data = {"default_value": "[{'a': 1}]"}
        await service.update_settings_async("KEY-01", data)

        call_args = repo.update_settings_async.call_args
        assert call_args[0][1]["default_value"] == '[{"a": 1}]'

    @pytest.mark.asyncio
    async def test_update_processes_values_list(self, service, repo):
        """Lines 196-197: values list is processed through process_setting_values."""
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        data = {"values": [{"value": "[{'x': 1}]"}]}
        await service.update_settings_async("KEY-01", data)

        call_args = repo.update_settings_async.call_args
        assert call_args[0][1]["values"][0]["value"] == '[{"x": 1}]'


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
