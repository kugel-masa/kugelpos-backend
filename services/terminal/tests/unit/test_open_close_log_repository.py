# Copyright 2026 masa@kugel
"""Unit tests for TestOpenCloseLogRepository (split from
test_repositories.py by class group)."""
from unittest.mock import AsyncMock, patch

import pytest

from kugel_common.exceptions import (
    CannotCreateException,
    DuplicateKeyException,
)

from ._helpers import _mock_db, _open_close_log


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
