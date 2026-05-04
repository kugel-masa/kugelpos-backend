# Copyright 2026 masa@kugel
"""Unit tests for TestCashInOutLogRepository (split from
test_repositories.py by class group)."""
from unittest.mock import AsyncMock, patch

import pytest

from kugel_common.exceptions import (
    CannotCreateException,
    DuplicateKeyException,
)
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from ._helpers import _mock_db, _cash_log


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
