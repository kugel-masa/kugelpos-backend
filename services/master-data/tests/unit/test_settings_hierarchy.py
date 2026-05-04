# Copyright 2026 masa@kugel
"""Unit tests for the settings hierarchical fallback resolution.

`SettingsMasterService.get_settings_value_by_name_async` walks a
4-level priority list to resolve a single value:
  1. terminal-specific (store_code + terminal_no match)
  2. store-specific   (store_code match, terminal_no IS NULL)
  3. global           (both NULL)
  4. default_value    (the doc's fallback)

Cart and other services rely on this for things like
RECEIPT_NO_START_VALUE / INVOICE_REGISTRATION_NUMBER. Bugs in priority
order produce wrong receipts and invoices. Integration testing all
combinations would need ~16 setup variations per test — directed unit
tests are the right level.
"""
from unittest.mock import AsyncMock

import pytest

from app.models.documents.settings_master_document import (
    SettingsMasterDocument,
    SettingsValue,
)
from app.services.settings_master_service import SettingsMasterService
from kugel_common.exceptions import DocumentNotFoundException


def _doc(default_value="DEFAULT", values=None) -> SettingsMasterDocument:
    return SettingsMasterDocument(
        name="MY_SETTING",
        default_value=default_value,
        values=values or [],
    )


def _val(value, store_code=None, terminal_no=None) -> SettingsValue:
    return SettingsValue(value=value, store_code=store_code, terminal_no=terminal_no)


def _make_service(doc):
    """Build a SettingsMasterService with a mock repo that yields `doc`
    for any name lookup."""
    repo = AsyncMock()
    repo.get_settings_by_name_async = AsyncMock(return_value=doc)
    return SettingsMasterService(repo)


# ---------------------------------------------------------------------------
# Hierarchy levels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminal_specific_wins_over_store_and_global():
    """Most-specific scope (store + terminal) takes precedence over
    less-specific scopes."""
    doc = _doc(values=[
        _val("TERMINAL_LEVEL", store_code="S1", terminal_no=9),
        _val("STORE_LEVEL", store_code="S1", terminal_no=None),
        _val("GLOBAL_LEVEL", store_code=None, terminal_no=None),
    ])
    svc = _make_service(doc)
    result = await svc.get_settings_value_by_name_async("MY_SETTING", "S1", 9)
    assert result == "TERMINAL_LEVEL"


@pytest.mark.asyncio
async def test_store_specific_wins_when_no_terminal_match():
    """If no terminal-level value exists, fall back to store-level."""
    doc = _doc(values=[
        _val("STORE_LEVEL", store_code="S1", terminal_no=None),
        _val("GLOBAL_LEVEL", store_code=None, terminal_no=None),
    ])
    svc = _make_service(doc)
    result = await svc.get_settings_value_by_name_async("MY_SETTING", "S1", 9)
    assert result == "STORE_LEVEL"


@pytest.mark.asyncio
async def test_global_used_when_no_store_match():
    """No matching store/terminal → global value."""
    doc = _doc(values=[
        _val("GLOBAL_LEVEL", store_code=None, terminal_no=None),
    ])
    svc = _make_service(doc)
    result = await svc.get_settings_value_by_name_async("MY_SETTING", "S1", 9)
    assert result == "GLOBAL_LEVEL"


@pytest.mark.asyncio
async def test_default_value_used_when_no_match_at_any_level():
    """Empty values list (or no scope match) → fall through to default_value."""
    doc = _doc(default_value="FALLBACK", values=[])
    svc = _make_service(doc)
    result = await svc.get_settings_value_by_name_async("MY_SETTING", "S1", 9)
    assert result == "FALLBACK"


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_setting_raises_document_not_found():
    """Setting name that doesn't exist → DocumentNotFoundException."""
    repo = AsyncMock()
    repo.get_settings_by_name_async = AsyncMock(return_value=None)
    svc = SettingsMasterService(repo)
    with pytest.raises(DocumentNotFoundException):
        await svc.get_settings_value_by_name_async("UNKNOWN", "S1", 9)


# ---------------------------------------------------------------------------
# Cross-store / cross-terminal isolation — most likely to regress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_store_terminal_value_does_not_leak():
    """A terminal-specific value scoped to store S2 must NOT be returned
    when querying for store S1. Bug here = customers see other store's
    config (e.g., another store's invoice number)."""
    doc = _doc(values=[
        # Different store entirely
        _val("OTHER_STORE_TERMINAL", store_code="S2", terminal_no=9),
        # Global is the only one matching for S1
        _val("GLOBAL_LEVEL", store_code=None, terminal_no=None),
    ])
    svc = _make_service(doc)
    result = await svc.get_settings_value_by_name_async("MY_SETTING", "S1", 9)
    assert result == "GLOBAL_LEVEL", (
        f"S2's terminal value leaked into S1 query (got {result!r})"
    )


@pytest.mark.asyncio
async def test_other_terminal_in_same_store_does_not_leak():
    """A value scoped to terminal=8 must NOT match a query for terminal=9."""
    doc = _doc(values=[
        _val("OTHER_TERMINAL", store_code="S1", terminal_no=8),
        _val("STORE_LEVEL", store_code="S1", terminal_no=None),
    ])
    svc = _make_service(doc)
    # Query for terminal 9 should not pick up terminal 8's value
    result = await svc.get_settings_value_by_name_async("MY_SETTING", "S1", 9)
    assert result == "STORE_LEVEL"
