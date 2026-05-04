"""Unit tests split out from test_repositories.py.

Shared helpers / imports preserved as-is from the original
test_repositories.py — splitting by repository class group keeps
each file under ~700 lines and lets pytest-xdist parallelise faster.
"""
import time
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.user_info_document import UserInfoDocument
from kugel_common.exceptions import (
    NotFoundException,
    LoadDataNoExistException,
    CannotCreateException,
)

from app.enums.cart_status import CartStatus
from app.models.documents.cart_document import CartDocument
from app.models.documents.tax_master_document import TaxMasterDocument
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.documents.item_master_document import ItemMasterDocument
from app.models.documents.transaction_status_document import TransactionStatusDocument
from app.models.documents.tranlog_delivery_status_document import TranlogDeliveryStatus
from app.models.documents.terminal_counter_document import TerminalCounterDocument

from app.models.repositories.cart_repository import CartRepository
from app.models.repositories.transaction_status_repository import TransactionStatusRepository
from app.models.repositories.tranlog_delivery_status_repository import TranlogDeliveryStatusRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.terminal_counter_repository import (
    TerminalCounterRepository,
    make_terminal_id,
)
from app.models.repositories.tax_master_repository import TaxMasterRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_terminal_info(**overrides) -> TerminalInfoDocument:
    """Create a TerminalInfoDocument with sensible defaults."""
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20240601",
        open_counter=1,
        staff=StaffMasterDocument(id="staff01", name="Test Staff"),
    )
    defaults.update(overrides)
    return TerminalInfoDocument(**defaults)


def _make_mock_db():
    """Return a MagicMock that behaves like AsyncIOMotorDatabase."""
    db = MagicMock()
    db.get_collection = MagicMock(return_value=MagicMock())
    db.client = MagicMock()
    return db


# =========================================================================
# CartRepository tests
# =========================================================================

def _make_aiohttp_context_manager(mock_response):
    """Wrap a mock response to behave as an aiohttp async context manager.

    aiohttp session methods (post/get/delete) return an object that supports
    ``async with`` directly (not a coroutine returning a context manager).
    Using MagicMock ensures the return value is synchronous while still
    supporting ``__aenter__``/``__aexit__``.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm



class TestTaxMasterRepository:
    """Tests for TaxMasterRepository cache and lookup logic."""

    def _make_repo(self, db=None, tax_docs=None):
        db = db or _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TaxMasterRepository(db, terminal_info, tax_docs)
        return repo

    @pytest.mark.asyncio
    async def test_load_all_taxes_from_settings(self):
        repo = self._make_repo()

        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [
                {"tax_code": "TAX10", "rate": 0.10, "tax_name": "Sales Tax"},
                {"tax_code": "TAX08", "rate": 0.08, "tax_name": "Reduced Tax"},
            ]
            result = await repo.load_all_taxes()

        assert len(result) == 2
        assert result[0].tax_code == "TAX10"
        assert result[1].tax_code == "TAX08"
        assert repo.tax_master_documents is result

    @pytest.mark.asyncio
    async def test_load_all_taxes_clears_existing(self):
        existing_taxes = [TaxMasterDocument(tax_code="OLD")]
        repo = self._make_repo(tax_docs=existing_taxes)

        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [
                {"tax_code": "NEW", "rate": 0.05},
            ]
            result = await repo.load_all_taxes()

        assert len(result) == 1
        assert result[0].tax_code == "NEW"

    @pytest.mark.asyncio
    async def test_load_all_taxes_with_none_settings(self):
        repo = self._make_repo()

        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = None
            result = await repo.load_all_taxes()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_tax_by_code_found(self):
        taxes = [
            TaxMasterDocument(tax_code="TAX10", rate=0.10),
            TaxMasterDocument(tax_code="TAX08", rate=0.08),
        ]
        repo = self._make_repo(tax_docs=taxes)

        result = await repo.get_tax_by_code("TAX08")

        assert result.tax_code == "TAX08"
        assert result.rate == 0.08

    @pytest.mark.asyncio
    async def test_get_tax_by_code_not_found_raises(self):
        taxes = [TaxMasterDocument(tax_code="TAX10")]
        repo = self._make_repo(tax_docs=taxes)

        with pytest.raises(NotFoundException):
            await repo.get_tax_by_code("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_tax_by_code_raises_when_not_loaded(self):
        repo = self._make_repo(tax_docs=None)

        with pytest.raises(LoadDataNoExistException):
            await repo.get_tax_by_code("TAX10")

    def test_set_tax_master_documents(self):
        repo = self._make_repo()
        taxes = [TaxMasterDocument(tax_code="T1")]
        repo.set_tax_master_documents(taxes)
        assert repo.tax_master_documents == taxes

    def test_shard_key_returns_no_need(self):
        repo = self._make_repo()
        tax = TaxMasterDocument(tax_code="T1")
        key = repo._TaxMasterRepository__get_shard_key(tax)
        assert key == "no_need"


# =========================================================================
# CartRepository Dapr cache + DB fallback tests
# =========================================================================


