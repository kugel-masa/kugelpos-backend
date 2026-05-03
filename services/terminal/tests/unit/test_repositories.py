"""
Unit tests for the terminal service repository layer.

Tests verify that repository methods construct correct filter dicts,
generate proper shard keys, handle duplicate key scenarios,
and raise appropriate exceptions.
"""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db():
    """Create a MagicMock that stands in for AsyncIOMotorDatabase."""
    return MagicMock()


def _terminal_info_doc(**overrides) -> TerminalInfoDocument:
    defaults = dict(
        tenant_id="T1",
        store_code="S1",
        terminal_no=1,
        terminal_id="T1-S1-1",
        description="test terminal",
        function_mode="MainMenu",
        status="Idle",
        business_date=None,
        open_counter=0,
        business_counter=0,
        staff=None,
        api_key="key123",
        tags=None,
        shard_key="T1_S1_1",
    )
    defaults.update(overrides)
    return TerminalInfoDocument(**defaults)


def _tenant_info_doc(**overrides) -> TenantInfoDocument:
    defaults = dict(
        tenant_id="T1",
        tenant_name="Tenant One",
        stores=[],
        tags=None,
        shard_key="T1",
    )
    defaults.update(overrides)
    return TenantInfoDocument(**defaults)


def _store_info(**overrides) -> StoreInfo:
    defaults = dict(store_code="S1", store_name="Store One", status="Active", business_date="20260101", tags=None)
    defaults.update(overrides)
    return StoreInfo(**defaults)


def _cash_log(**overrides) -> CashInOutLog:
    defaults = dict(
        tenant_id="T1",
        store_code="S1",
        terminal_no=1,
        business_date="20260101",
        generate_date_time="2026-01-01T10:00:00",
        amount=100.0,
        description="cash in",
    )
    defaults.update(overrides)
    return CashInOutLog(**defaults)


def _open_close_log(**overrides) -> OpenCloseLog:
    defaults = dict(
        tenant_id="T1",
        store_code="S1",
        terminal_no=1,
        business_date="20260101",
        open_counter=1,
        operation="open",
    )
    defaults.update(overrides)
    return OpenCloseLog(**defaults)


# ===========================================================================
# TerminalInfoRepository
# ===========================================================================

class TestTerminalInfoRepository:
    """Tests for TerminalInfoRepository."""

    def _make_repo(self, tenant_id="T1"):
        from app.models.repositories.terminal_info_repository import TerminalInfoRepository
        return TerminalInfoRepository(_mock_db(), tenant_id)

    # -- get_terminal_info_by_id_async ----------------------------------------

    @pytest.mark.asyncio
    async def test_get_terminal_info_by_id_found(self):
        repo = self._make_repo()
        doc = _terminal_info_doc()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc):
            result = await repo.get_terminal_info_by_id_async("T1-S1-1")
            repo.get_one_async.assert_awaited_once_with({"terminal_id": "T1-S1-1"})
            assert result.terminal_id == "T1-S1-1"

    @pytest.mark.asyncio
    async def test_get_terminal_info_by_id_not_found(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.get_terminal_info_by_id_async("T1-S1-999")

    # -- get_terminal_info_list_async -----------------------------------------

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_without_store_code(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.get_terminal_info_list_async(limit=10, page=1, sort=[("created_at", -1)])
            call_args = mock_get.call_args
            assert call_args[0][0] == {"tenant_id": "T1"}
            assert call_args[0][1] == 10
            assert call_args[0][2] == 1

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_with_store_code(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.get_terminal_info_list_async(limit=5, page=2, sort=[], store_code="S1")
            call_args = mock_get.call_args
            assert call_args[0][0] == {"tenant_id": "T1", "store_code": "S1"}

    # -- get_terminal_info_list_paginated_async --------------------------------

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_paginated_without_store_code(self):
        repo = self._make_repo("T1")
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="created_at:-1", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=paginated) as mock_get:
            result = await repo.get_terminal_info_list_paginated_async(limit=10, page=1, sort=[("created_at", -1)])
            call_args = mock_get.call_args
            assert call_args[0][0] == {"tenant_id": "T1"}
            assert result.metadata.total == 0

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_paginated_with_store_code(self):
        repo = self._make_repo("T1")
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=paginated) as mock_get:
            await repo.get_terminal_info_list_paginated_async(limit=10, page=1, sort=[], store_code="S2")
            call_args = mock_get.call_args
            assert call_args[0][0] == {"tenant_id": "T1", "store_code": "S2"}

    # -- create_terminal_info -------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_terminal_info_success(self):
        repo = self._make_repo("T1")
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_terminal_info(store_code="S1", terminal_no=1, description="desc", tags=["tag1"])
            assert result.terminal_id == "T1-S1-1"
            assert result.shard_key == "T1_S1_1"
            assert result.function_mode == "MainMenu"
            assert result.status == "Idle"
            assert result.open_counter == 0
            assert result.business_counter == 0
            assert result.tags == ["tag1"]
            assert result.api_key is not None

    @pytest.mark.asyncio
    async def test_create_terminal_info_already_exists(self):
        repo = self._make_repo("T1")
        existing = _terminal_info_doc()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=existing):
            with pytest.raises(AlreadyExistException):
                await repo.create_terminal_info(store_code="S1", terminal_no=1)

    @pytest.mark.asyncio
    async def test_create_terminal_info_create_fails(self):
        repo = self._make_repo("T1")
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_terminal_info(store_code="S1", terminal_no=1)

    # -- update_terminal_info_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_update_terminal_info_success(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update:
            result = await repo.update_terminal_info_async("T1-S1-1", {"status": "Opened"})
            mock_update.assert_awaited_once_with({"terminal_id": "T1-S1-1"}, {"status": "Opened"})
            assert result is True

    @pytest.mark.asyncio
    async def test_update_terminal_info_fails(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(UpdateNotWorkException):
                await repo.update_terminal_info_async("T1-S1-1", {"status": "Opened"})

    # -- replace_terminal_info_async ------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_terminal_info_success(self):
        repo = self._make_repo()
        doc = _terminal_info_doc()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_replace:
            result = await repo.replace_terminal_info_async("T1-S1-1", doc)
            mock_replace.assert_awaited_once_with({"terminal_id": "T1-S1-1"}, doc)
            assert result is True

    @pytest.mark.asyncio
    async def test_replace_terminal_info_fails(self):
        repo = self._make_repo()
        doc = _terminal_info_doc()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(UpdateNotWorkException):
                await repo.replace_terminal_info_async("T1-S1-1", doc)

    # -- delete_terminal_info_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_terminal_info_success(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            result = await repo.delete_terminal_info_async("T1-S1-1")
            mock_del.assert_awaited_once_with({"terminal_id": "T1-S1-1"})
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_terminal_info_fails(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(CannotDeleteException):
                await repo.delete_terminal_info_async("T1-S1-1")

    # -- shard key ------------------------------------------------------------

    def test_shard_key_format(self):
        repo = self._make_repo("T1")
        doc = _terminal_info_doc(tenant_id="T1", store_code="S1", terminal_no=1)
        # Access name-mangled private method
        key = repo._TerminalInfoRepository__make_shard_key(doc)
        assert key == "T1_S1_1"

    # -- helper functions -----------------------------------------------------

    def test_make_terminal_id(self):
        from app.models.repositories.terminal_info_repository import make_terminal_id
        assert make_terminal_id("T1", "S1", 1) == "T1-S1-1"
        assert make_terminal_id("tenant", "store", 99) == "tenant-store-99"

    def test_make_api_key_is_unique(self):
        from app.models.repositories.terminal_info_repository import make_api_key
        key1 = make_api_key()
        key2 = make_api_key()
        assert isinstance(key1, str)
        assert len(key1) > 0
        assert key1 != key2


# ===========================================================================
# TenantInfoRepository
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
# ===========================================================================

class TestCashInOutLogRepository:
    """Tests for CashInOutLogRepository."""

    def _make_repo(self, tenant_id="T1"):
        from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
        return CashInOutLogRepository(_mock_db(), tenant_id)

    # -- create_cash_in_out_log -----------------------------------------------

    @pytest.mark.asyncio
    async def test_create_cash_in_out_log_success(self):
        repo = self._make_repo()
        log = _cash_log()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_cash_in_out_log(log)
            assert result.shard_key == "T1_S1_1_20260101"
            assert result is log

    @pytest.mark.asyncio
    async def test_create_cash_in_out_log_duplicate_replaces(self):
        repo = self._make_repo()
        log = _cash_log()
        with (
            patch.object(
                repo, "create_async", new_callable=AsyncMock,
                side_effect=DuplicateKeyException("dup", "col", None, None),
            ),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_replace,
        ):
            result = await repo.create_cash_in_out_log(log)
            assert result is log
            call_filter = mock_replace.call_args[0][0]
            assert call_filter["tenant_id"] == "T1"
            assert call_filter["store_code"] == "S1"
            assert call_filter["terminal_no"] == 1
            assert call_filter["generate_date_time"] == "2026-01-01T10:00:00"

    @pytest.mark.asyncio
    async def test_create_cash_in_out_log_create_returns_false(self):
        repo = self._make_repo()
        log = _cash_log()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(CannotCreateException):
                await repo.create_cash_in_out_log(log)

    # -- get_cash_in_out_logs -------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_cash_in_out_logs(self):
        repo = self._make_repo()
        paginated = PaginatedResult(
            metadata=Metadata(total=1, page=1, limit=100, sort="", filter={}),
            data=[_cash_log()],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=paginated) as mock_get:
            filt = {"tenant_id": "T1", "store_code": "S1"}
            result = await repo.get_cash_in_out_logs(filt, limit=50, page=2, sort=[("created_at", -1)])
            mock_get.assert_awaited_once_with(filt, 50, 2, [("created_at", -1)])
            assert result.metadata.total == 1

    # -- shard key ------------------------------------------------------------

    def test_shard_key_format(self):
        repo = self._make_repo()
        log = _cash_log(tenant_id="T1", store_code="S1", terminal_no=1, business_date="20260101")
        key = repo._CashInOutLogRepository__get_shard_key(log)
        assert key == "T1_S1_1_20260101"


# ===========================================================================
# OpenCloseLogRepository
# ===========================================================================

class TestOpenCloseLogRepository:
    """Tests for OpenCloseLogRepository."""

    def _make_repo(self, tenant_id="T1"):
        from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
        return OpenCloseLogRepository(_mock_db(), tenant_id)

    # -- create_open_close_log ------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_open_close_log_success(self):
        repo = self._make_repo()
        log = _open_close_log()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_open_close_log(log)
            assert result.shard_key == "T1_S1_1_20260101"
            assert result is log

    @pytest.mark.asyncio
    async def test_create_open_close_log_duplicate_replaces(self):
        repo = self._make_repo()
        log = _open_close_log()
        with (
            patch.object(
                repo, "create_async", new_callable=AsyncMock,
                side_effect=DuplicateKeyException("dup", "col", None, None),
            ),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_replace,
        ):
            result = await repo.create_open_close_log(log)
            assert result is log
            call_filter = mock_replace.call_args[0][0]
            assert call_filter["tenant_id"] == "T1"
            assert call_filter["store_code"] == "S1"
            assert call_filter["terminal_no"] == 1
            assert call_filter["business_date"] == "20260101"
            assert call_filter["open_counter"] == 1
            assert call_filter["operation"] == "open"

    @pytest.mark.asyncio
    async def test_create_open_close_log_create_returns_false(self):
        repo = self._make_repo()
        log = _open_close_log()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(CannotCreateException):
                await repo.create_open_close_log(log)

    # -- shard key ------------------------------------------------------------

    def test_shard_key_format(self):
        repo = self._make_repo()
        log = _open_close_log(tenant_id="T1", store_code="S1", terminal_no=1, business_date="20260101")
        key = repo._OpenCloseLogRepository__get_shard_key(log)
        assert key == "T1_S1_1_20260101"


# ===========================================================================
# TerminallogDeliveryStatusRepository
# ===========================================================================

class TestTerminallogDeliveryStatusRepository:
    """Tests for TerminallogDeliveryStatusRepository."""

    def _make_terminal_info(self, **overrides):
        from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument as CommonTerminalInfoDoc
        defaults = dict(
            tenant_id="T1",
            store_code="S1",
            terminal_no=1,
            business_date="20260101",
            open_counter=5,
        )
        defaults.update(overrides)
        return CommonTerminalInfoDoc(**defaults)

    def _make_repo(self, terminal_info=None):
        from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
        if terminal_info is None:
            terminal_info = self._make_terminal_info()
        return TerminallogDeliveryStatusRepository(_mock_db(), terminal_info)

    # -- create_status_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_status_success(self):
        repo = self._make_repo()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            result = await repo.create_status_async(
                event_id="evt-001",
                payload={"type": "tranlog"},
                services=[{"service_name": "report", "status": "pending"}],
            )
            assert result is True
            created_doc = mock_create.call_args[0][0]
            assert created_doc.event_id == "evt-001"
            assert created_doc.tenant_id == "T1"
            assert created_doc.store_code == "S1"
            assert created_doc.terminal_no == 1
            assert created_doc.business_date == "20260101"
            assert created_doc.open_counter == 5
            assert created_doc.status == "published"
            assert len(created_doc.services) == 1
            assert created_doc.services[0].service_name == "report"

    @pytest.mark.asyncio
    async def test_create_status_with_custom_terminal_info(self):
        repo = self._make_repo()
        custom_info = self._make_terminal_info(tenant_id="T2", store_code="S2", terminal_no=3)
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            await repo.create_status_async(
                event_id="evt-002",
                payload={},
                terminal_info=custom_info,
            )
            created_doc = mock_create.call_args[0][0]
            assert created_doc.tenant_id == "T2"
            assert created_doc.store_code == "S2"
            assert created_doc.terminal_no == 3

    @pytest.mark.asyncio
    async def test_create_status_no_services(self):
        repo = self._make_repo()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            await repo.create_status_async(event_id="evt-003", payload={"x": 1})
            created_doc = mock_create.call_args[0][0]
            assert created_doc.services == []

    # -- find_by_event_id -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_event_id(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=MagicMock()) as mock_get:
            await repo.find_by_event_id("evt-001")
            mock_get.assert_awaited_once_with({"event_id": "evt-001"})

    # -- find_by_terminal_info ------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_terminal_info(self):
        repo = self._make_repo()
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.find_by_terminal_info("T1", "S1", 1)
            mock_get.assert_awaited_once_with({"tenant_id": "T1", "store_code": "S1", "terminal_no": 1})

    # -- find_by_business_date ------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_business_date(self):
        repo = self._make_repo()
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.find_by_business_date("T1", "S1", "20260101")
            mock_get.assert_awaited_once_with({"tenant_id": "T1", "store_code": "S1", "business_date": "20260101"})

    # -- find_pending_deliveries ----------------------------------------------

    @pytest.mark.asyncio
    async def test_find_pending_deliveries(self):
        repo = self._make_repo()
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.find_pending_deliveries(hours_ago=12)
            call_filter = mock_get.call_args[0][0]
            assert "$gte" in call_filter["published_at"]
            assert call_filter["status"] == {"$nin": ["delivered"]}

    # -- update_service_status ------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_service_status_success(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        repo.dbcollection = mock_collection

        result = await repo.update_service_status("evt-001", "report", "received", message="ok")
        assert result is True
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"event_id": "evt-001"}
        update_set = call_args[0][1]["$set"]
        assert update_set["services.$[elem].status"] == "received"
        assert update_set["services.$[elem].message"] == "ok"
        assert call_args[1]["array_filters"] == [{"elem.service_name": "report"}]

    @pytest.mark.asyncio
    async def test_update_service_status_not_modified(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        repo.dbcollection = mock_collection

        result = await repo.update_service_status("evt-999", "report", "received")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_service_status_exception_returns_false(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.update_one = AsyncMock(side_effect=Exception("db error"))
        repo.dbcollection = mock_collection

        result = await repo.update_service_status("evt-001", "report", "received")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_service_status_without_message(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        repo.dbcollection = mock_collection

        await repo.update_service_status("evt-001", "report", "received")
        call_args = mock_collection.update_one.call_args
        update_set = call_args[0][1]["$set"]
        assert "services.$[elem].message" not in update_set

    @pytest.mark.asyncio
    async def test_update_service_status_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            # After initialize, set the collection
            async def set_collection():
                repo.dbcollection = mock_collection
            mock_init.side_effect = set_collection
            result = await repo.update_service_status("evt-001", "report", "received")
            mock_init.assert_awaited_once()
            assert result is True

    # -- update_delivery_status -----------------------------------------------

    @pytest.mark.asyncio
    async def test_update_delivery_status(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update:
            result = await repo.update_delivery_status("evt-001", "delivered")
            assert result is True
            call_args = mock_update.call_args
            assert call_args[0][0] == {"event_id": "evt-001"}
            assert call_args[0][1]["status"] == "delivered"
            assert "last_updated_at" in call_args[0][1]
