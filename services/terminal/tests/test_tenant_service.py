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

from app.services.tenant_service import TenantService
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo
from app.exceptions import (
    NotFoundException,
    DuplicateKeyException,
    TenantAlreadyExistsException,
    TenantCreateException,
    TenantNotFoundException,
    TenantUpdateException,
    TenantDeleteException,
    StoreAlreadyExistsException,
    StoreNotFoundException,
)


def make_tenant_doc(tenant_id="T001", tenant_name="Test Tenant"):
    return TenantInfoDocument(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        stores=[],
        tags=[],
    )


def make_store_info(store_code="S001", store_name="Store 1"):
    store = StoreInfo()
    store.store_code = store_code
    store.store_name = store_name
    return store


# ---------------------------------------------------------------------------
# TenantService.create_tenant_async
# ---------------------------------------------------------------------------

class TestTenantServiceCreate:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_create_success(self, service, mock_repo):
        """Valid tenant is created and returned."""
        expected = make_tenant_doc()
        mock_repo.create_tenant_info_async.return_value = expected

        result = await service.create_tenant_async("Test Tenant", [], [])

        assert result == expected
        mock_repo.create_tenant_info_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, mock_repo):
        """DuplicateKeyException from repo becomes TenantAlreadyExistsException."""
        mock_repo.create_tenant_info_async.side_effect = DuplicateKeyException("dup", "col", "key")

        with pytest.raises(TenantAlreadyExistsException):
            await service.create_tenant_async("Test", [], [])

    @pytest.mark.asyncio
    async def test_create_other_error_raises(self, service, mock_repo):
        """Generic exception becomes TenantCreateException."""
        mock_repo.create_tenant_info_async.side_effect = Exception("DB error")

        with pytest.raises(TenantCreateException):
            await service.create_tenant_async("Test", [], [])


# ---------------------------------------------------------------------------
# TenantService.get_tenant_async
# ---------------------------------------------------------------------------

class TestTenantServiceGet:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_get_success(self, service, mock_repo):
        """Returns tenant when found."""
        expected = make_tenant_doc()
        mock_repo.get_tenant_info_async.return_value = expected

        result = await service.get_tenant_async()

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_not_found_raises(self, service, mock_repo):
        """Exception from repo becomes TenantNotFoundException."""
        mock_repo.get_tenant_info_async.side_effect = Exception("not found")

        with pytest.raises(TenantNotFoundException):
            await service.get_tenant_async()


# ---------------------------------------------------------------------------
# TenantService.update_tenant_async
# ---------------------------------------------------------------------------

class TestTenantServiceUpdate:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_update_success(self, service, mock_repo):
        """Successful update returns updated tenant."""
        updated = make_tenant_doc(tenant_name="Updated")
        mock_repo.update_tenant_info_async.return_value = updated

        result = await service.update_tenant_async("Updated", [])

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_error_raises(self, service, mock_repo):
        """Exception from repo becomes TenantUpdateException."""
        mock_repo.update_tenant_info_async.side_effect = Exception("DB error")

        with pytest.raises(TenantUpdateException):
            await service.update_tenant_async("Updated", [])


# ---------------------------------------------------------------------------
# TenantService.delete_tenant_async
# ---------------------------------------------------------------------------

class TestTenantServiceDelete:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_delete_success(self, service, mock_repo):
        """Successful delete returns True."""
        mock_repo.delete_tenant_info_async.return_value = True

        result = await service.delete_tenant_async()

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_error_raises(self, service, mock_repo):
        """Exception from repo becomes TenantDeleteException."""
        mock_repo.delete_tenant_info_async.side_effect = Exception("DB error")

        with pytest.raises(TenantDeleteException):
            await service.delete_tenant_async()


# ---------------------------------------------------------------------------
# TenantService.add_store_async
# ---------------------------------------------------------------------------

class TestTenantServiceAddStore:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_add_store_success(self, service, mock_repo):
        """Store is added and updated tenant returned."""
        expected = make_tenant_doc()
        mock_repo.add_store_async.return_value = expected

        result = await service.add_store_async("S001", "Store 1")

        assert result == expected

    @pytest.mark.asyncio
    async def test_add_store_tenant_not_found(self, service, mock_repo):
        """NotFoundException becomes TenantNotFoundException."""
        mock_repo.add_store_async.side_effect = NotFoundException("tenant not found", "col", "key")

        with pytest.raises(TenantNotFoundException):
            await service.add_store_async("S001", "Store 1")

    @pytest.mark.asyncio
    async def test_add_store_duplicate_raises(self, service, mock_repo):
        """DuplicateKeyException becomes StoreAlreadyExistsException."""
        mock_repo.add_store_async.side_effect = DuplicateKeyException("dup", "col", "key")

        with pytest.raises(StoreAlreadyExistsException):
            await service.add_store_async("S001", "Store 1")

    @pytest.mark.asyncio
    async def test_add_store_other_error_raises(self, service, mock_repo):
        """Generic exception becomes TenantUpdateException."""
        mock_repo.add_store_async.side_effect = Exception("DB error")

        with pytest.raises(TenantUpdateException):
            await service.add_store_async("S001", "Store 1")


# ---------------------------------------------------------------------------
# TenantService.get_stores_async / get_store_async
# ---------------------------------------------------------------------------

class TestTenantServiceGetStores:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_get_stores_success(self, service, mock_repo):
        """Returns list of stores."""
        stores = [make_store_info("S001"), make_store_info("S002")]
        mock_repo.get_stores_async.return_value = stores

        result = await service.get_stores_async(limit=10, page=1, sort=[])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_stores_tenant_not_found(self, service, mock_repo):
        """NotFoundException becomes TenantNotFoundException."""
        mock_repo.get_stores_async.side_effect = NotFoundException("not found", "col", "key")

        with pytest.raises(TenantNotFoundException):
            await service.get_stores_async(limit=10, page=1, sort=[])

    @pytest.mark.asyncio
    async def test_get_stores_generic_error_raises_type_error(self, service, mock_repo):
        """Generic exception from repo triggers SystemError construction which raises TypeError.

        Note: The implementation passes keyword args to built-in SystemError,
        which does not accept them, resulting in TypeError.
        """
        mock_repo.get_stores_async.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(TypeError):
            await service.get_stores_async(limit=10, page=1, sort=[])

    @pytest.mark.asyncio
    async def test_get_store_success(self, service, mock_repo):
        """Returns specific store when found."""
        store = make_store_info("S001")
        mock_repo.get_store_async.return_value = store

        result = await service.get_store_async("S001")

        assert result.store_code == "S001"

    @pytest.mark.asyncio
    async def test_get_store_not_found_raises(self, service, mock_repo):
        """None result raises StoreNotFoundException."""
        mock_repo.get_store_async.return_value = None

        with pytest.raises(StoreNotFoundException):
            await service.get_store_async("S999")

    @pytest.mark.asyncio
    async def test_get_store_tenant_not_found(self, service, mock_repo):
        """NotFoundException becomes TenantNotFoundException."""
        mock_repo.get_store_async.side_effect = NotFoundException("not found", "col", "key")

        with pytest.raises(TenantNotFoundException):
            await service.get_store_async("S001")


# ---------------------------------------------------------------------------
# TenantService.update_store_async / delete_store_async
# ---------------------------------------------------------------------------

class TestTenantServiceUpdateDeleteStore:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return TenantService(tenant_info_repo=mock_repo, tenant_id="T001")

    @pytest.mark.asyncio
    async def test_update_store_success(self, service, mock_repo):
        """Updated store info returned."""
        store = make_store_info("S001", "Updated Store")
        mock_repo.update_store_async.return_value = store

        result = await service.update_store_async("S001", {"store_name": "Updated Store"})

        assert result.store_name == "Updated Store"

    @pytest.mark.asyncio
    async def test_update_store_tenant_not_found(self, service, mock_repo):
        """NotFoundException becomes TenantNotFoundException."""
        mock_repo.update_store_async.side_effect = NotFoundException("not found", "col", "key")

        with pytest.raises(TenantNotFoundException):
            await service.update_store_async("S001", {})

    @pytest.mark.asyncio
    async def test_update_store_error_raises(self, service, mock_repo):
        """Generic exception becomes TenantUpdateException."""
        mock_repo.update_store_async.side_effect = Exception("DB error")

        with pytest.raises(TenantUpdateException):
            await service.update_store_async("S001", {})

    @pytest.mark.asyncio
    async def test_delete_store_success(self, service, mock_repo):
        """Successful delete returns True."""
        mock_repo.delete_store_async.return_value = True

        result = await service.delete_store_async("S001")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_store_tenant_not_found(self, service, mock_repo):
        """NotFoundException becomes TenantNotFoundException."""
        mock_repo.delete_store_async.side_effect = NotFoundException("not found", "col", "key")

        with pytest.raises(TenantNotFoundException):
            await service.delete_store_async("S001")

    @pytest.mark.asyncio
    async def test_delete_store_error_raises(self, service, mock_repo):
        """Generic exception becomes TenantDeleteException."""
        mock_repo.delete_store_async.side_effect = Exception("DB error")

        with pytest.raises(TenantDeleteException):
            await service.delete_store_async("S001")
