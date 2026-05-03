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



class TestTerminalCounterRepository:
    """Tests for TerminalCounterRepository."""

    def test_make_terminal_id(self):
        tid = make_terminal_id("T001", "S001", 1)
        assert tid == "T001-S001-1"

    def test_make_terminal_id_different_values(self):
        tid = make_terminal_id("TENX", "STRY", 99)
        assert tid == "TENX-STRY-99"

    @pytest.mark.asyncio
    async def test_numbering_count_success(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(
            return_value={"count_dic": {"receipt": 42}}
        )
        repo.dbcollection = mock_collection

        result = await repo.numbering_count("receipt")

        assert result == 42
        # Verify the filter used correct terminal_id
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[1]["filter"] == {"terminal_id": "T001-S001-1"}
        assert call_args[1]["upsert"] is True

    @pytest.mark.asyncio
    async def test_numbering_count_raises_on_none_result(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(return_value=None)
        repo.dbcollection = mock_collection

        from app.exceptions import UpdateNotWorkException

        with pytest.raises(UpdateNotWorkException):
            await repo.numbering_count("receipt")

    @pytest.mark.asyncio
    async def test_numbering_count_raises_when_count_type_missing(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(
            return_value={"count_dic": {"other_type": 5}}
        )
        repo.dbcollection = mock_collection

        from app.exceptions import UpdateNotWorkException

        with pytest.raises(UpdateNotWorkException):
            await repo.numbering_count("receipt")

    @pytest.mark.asyncio
    async def test_numbering_count_custom_start_and_end(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(
            return_value={"count_dic": {"transaction": 10}}
        )
        repo.dbcollection = mock_collection

        result = await repo.numbering_count("transaction", start_value=10, end_value=9999)

        assert result == 10
        # Verify the pipeline was passed (list of dicts = aggregation pipeline)
        call_args = mock_collection.find_one_and_update.call_args
        update = call_args[1]["update"]
        assert isinstance(update, list)  # aggregation pipeline
        assert len(update) == 2


# =========================================================================
# TaxMasterRepository tests
# =========================================================================


