# Copyright 2026 masa@kugel
"""Shared builders / mock helpers for terminal repository unit tests.

Kept under a non-`test_` filename so pytest does not collect it.
"""
from unittest.mock import MagicMock

from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.tenant_info_document import StoreInfo, TenantInfoDocument
from app.models.documents.terminal_info_document import TerminalInfoDocument


def _mock_db():
    """Return a MagicMock that stands in for AsyncIOMotorDatabase."""
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
    defaults = dict(
        store_code="S1",
        store_name="Store One",
        status="Active",
        business_date="20260101",
        tags=None,
    )
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
