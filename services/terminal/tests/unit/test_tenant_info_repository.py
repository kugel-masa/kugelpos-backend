# Copyright 2026 masa@kugel
"""Unit tests for TestTenantInfoRepository (split from
test_repositories.py by class group)."""
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

import pytest

from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.terminallog_delivery_status_document import TerminallogDeliveryStatus
from kugel_common.exceptions import (
    AlreadyExistException,
    CannotCreateException,
    NotFoundException,
    UpdateNotWorkException,
    CannotDeleteException,
    DuplicateKeyException,
)
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from ._helpers import _mock_db, _tenant_info_doc, _store_info


# ===========================================================================

class TestTenantInfoRepository:
    """Tests for TenantInfoRepository."""

    def _make_repo(self, tenant_id="T1"):
        from app.models.repositories.tenant_info_repository import TenantInfoRepository
        return TenantInfoRepository(_mock_db(), tenant_id)

    # -- create_tenant_info_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_create_tenant_info_success(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_tenant_info_async("Tenant One", tags=["retail"])
            assert result.tenant_id == "T1"
            assert result.tenant_name == "Tenant One"
            assert result.shard_key == "T1"
            assert result.tags == ["retail"]

    @pytest.mark.asyncio
    async def test_create_tenant_info_fails(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(CannotCreateException):
                await repo.create_tenant_info_async("Tenant One")

    # -- get_tenant_info_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_tenant_info_found(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc) as mock_get:
            result = await repo.get_tenant_info_async()
            mock_get.assert_awaited_once_with({"tenant_id": "T1"})
            assert result.tenant_name == "Tenant One"

    @pytest.mark.asyncio
    async def test_get_tenant_info_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.get_tenant_info_async()

    # -- update_tenant_info_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_update_tenant_info_success(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.update_tenant_info_async("New Name", tags=["new"])
            assert result.tenant_name == "New Name"
            assert result.tags == ["new"]

    @pytest.mark.asyncio
    async def test_update_tenant_info_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.update_tenant_info_async("New Name")

    @pytest.mark.asyncio
    async def test_update_tenant_info_replace_fails(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(UpdateNotWorkException):
                await repo.update_tenant_info_async("New Name")

    # -- delete_tenant_info_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_tenant_info_success(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            result = await repo.delete_tenant_info_async()
            mock_del.assert_awaited_once_with({"tenant_id": "T1"})
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_tenant_info_fails(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(CannotDeleteException):
                await repo.delete_tenant_info_async()

    # -- add_store_async ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_add_store_success(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc(stores=[])
        new_store = _store_info(store_code="S2", store_name="Store Two")
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.add_store_async(new_store)
            assert len(result.stores) == 1
            assert result.stores[0].store_code == "S2"

    @pytest.mark.asyncio
    async def test_add_store_already_exists(self):
        repo = self._make_repo("T1")
        existing_store = _store_info(store_code="S1")
        doc = _tenant_info_doc(stores=[existing_store])
        new_store = _store_info(store_code="S1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            with pytest.raises(AlreadyExistException):
                await repo.add_store_async(new_store)

    @pytest.mark.asyncio
    async def test_add_store_tenant_not_found(self):
        repo = self._make_repo("T1")
        new_store = _store_info(store_code="S2")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.add_store_async(new_store)

    @pytest.mark.asyncio
    async def test_add_store_replace_fails(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc(stores=[])
        new_store = _store_info(store_code="S2")
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(UpdateNotWorkException):
                await repo.add_store_async(new_store)

    # -- get_stores_async -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_stores_no_sort(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1", store_name="B Store")
        s2 = _store_info(store_code="S2", store_name="A Store")
        doc = _tenant_info_doc(stores=[s1, s2])
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            result = await repo.get_stores_async(limit=10, page=1, sort=[])
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_stores_sorted_asc(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S2", store_name="B Store")
        s2 = _store_info(store_code="S1", store_name="A Store")
        doc = _tenant_info_doc(stores=[s1, s2])
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            result = await repo.get_stores_async(limit=10, page=1, sort=[("store_name", 1)])
            assert result[0].store_name == "A Store"
            assert result[1].store_name == "B Store"

    @pytest.mark.asyncio
    async def test_get_stores_sorted_desc(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1", store_name="A Store")
        s2 = _store_info(store_code="S2", store_name="B Store")
        doc = _tenant_info_doc(stores=[s1, s2])
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            result = await repo.get_stores_async(limit=10, page=1, sort=[("store_name", -1)])
            assert result[0].store_name == "B Store"
            assert result[1].store_name == "A Store"

    @pytest.mark.asyncio
    async def test_get_stores_tenant_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.get_stores_async(limit=10, page=1, sort=[])

    # -- get_store_async ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_store_found(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1")
        doc = _tenant_info_doc(stores=[s1])
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            result = await repo.get_store_async("S1")
            assert result.store_code == "S1"

    @pytest.mark.asyncio
    async def test_get_store_not_found(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc(stores=[_store_info(store_code="S1")])
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            result = await repo.get_store_async("S999")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_store_tenant_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.get_store_async("S1")

    # -- update_store_async ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_store_success(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1", store_name="Old Name")
        doc = _tenant_info_doc(stores=[s1])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.update_store_async("S1", {"store_name": "New Name"})
            assert result.store_name == "New Name"

    @pytest.mark.asyncio
    async def test_update_store_updates_status(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1", status="Active")
        doc = _tenant_info_doc(stores=[s1])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.update_store_async("S1", {"status": "Inactive"})
            assert result.status == "Inactive"

    @pytest.mark.asyncio
    async def test_update_store_updates_business_date(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1", business_date="20260101")
        doc = _tenant_info_doc(stores=[s1])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.update_store_async("S1", {"business_date": "20260102"})
            assert result.business_date == "20260102"

    @pytest.mark.asyncio
    async def test_update_store_updates_tags(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1", tags=None)
        doc = _tenant_info_doc(stores=[s1])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.update_store_async("S1", {"tags": ["vip"]})
            assert result.tags == ["vip"]

    @pytest.mark.asyncio
    async def test_update_store_tenant_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.update_store_async("S1", {"store_name": "X"})

    @pytest.mark.asyncio
    async def test_update_store_replace_fails(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1")
        doc = _tenant_info_doc(stores=[s1])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(UpdateNotWorkException):
                await repo.update_store_async("S1", {"store_name": "X"})

    # -- delete_store_async ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_store_success(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1")
        s2 = _store_info(store_code="S2")
        doc = _tenant_info_doc(stores=[s1, s2])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_replace,
        ):
            result = await repo.delete_store_async("S1")
            assert result is True
            # Verify the replaced doc no longer has S1
            replaced_doc = mock_replace.call_args[0][1]
            store_codes = [s.store_code for s in replaced_doc.stores]
            assert "S1" not in store_codes
            assert "S2" in store_codes

    @pytest.mark.asyncio
    async def test_delete_store_tenant_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.delete_store_async("S1")

    @pytest.mark.asyncio
    async def test_delete_store_replace_fails(self):
        repo = self._make_repo("T1")
        s1 = _store_info(store_code="S1")
        doc = _tenant_info_doc(stores=[s1])
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotDeleteException):
                await repo.delete_store_async("S1")

    # -- shard key ------------------------------------------------------------

    def test_shard_key_format(self):
        repo = self._make_repo("T1")
        doc = _tenant_info_doc(tenant_id="T1")
        key = repo._TenantInfoRepository__make_shard_key(doc)
        assert key == "T1"


# ===========================================================================
# CashInOutLogRepository
