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

from kugel_common.exceptions import DocumentNotFoundException, DocumentAlreadyExistsException

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
