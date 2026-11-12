# Copyright 2026 masa@kugel
"""Unit tests for TestOpenCloseLogRepository (split from
test_repositories.py by class group)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kugel_common.exceptions import (
    CannotCreateException,
)

from ._helpers import _mock_db, _open_close_log

# ===========================================================================

class TestOpenCloseLogRepository:
    """Tests for OpenCloseLogRepository."""

    def _make_repo(self, tenant_id="T1"):
        from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
        return OpenCloseLogRepository(_mock_db(), tenant_id)

    # -- create_open_close_log ------------------------------------------------

    def _with_collection(self, repo, *, upserted_id=None, existing=None):
        collection = MagicMock()
        collection.update_one = AsyncMock(return_value=MagicMock(upserted_id=upserted_id))
        collection.find_one = AsyncMock(return_value=existing)
        repo.dbcollection = collection
        return collection

    @pytest.mark.asyncio
    async def test_create_open_close_log_success(self):
        repo = self._make_repo()
        log = _open_close_log(business_counter=5)
        collection = self._with_collection(repo, upserted_id="new-id")

        result = await repo.create_open_close_log(log)

        assert result.shard_key == "T1_S1_1_20260101"
        assert result is log
        key, update = collection.update_one.call_args[0]
        assert key == {"tenant_id": "T1", "store_code": "S1", "terminal_no": 1, "business_counter": 5, "operation": "open"}
        assert "$setOnInsert" in update
        assert collection.update_one.call_args.kwargs["upsert"] is True

    @pytest.mark.asyncio
    async def test_the_same_business_again_overwrites_its_own_log(self):
        repo = self._make_repo()
        log = _open_close_log(business_counter=5)
        self._with_collection(repo, existing={"business_date": "20260101", "open_counter": 1})
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_replace:
            result = await repo.create_open_close_log(log)

        assert result is log
        assert mock_replace.call_args[0][0]["business_counter"] == 5

    @pytest.mark.asyncio
    async def test_a_different_business_with_the_same_counter_is_refused_not_replaced(self):
        repo = self._make_repo()
        log = _open_close_log(business_counter=5)
        self._with_collection(repo, existing={"business_date": "20251231", "open_counter": 3})
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock) as mock_replace:
            with pytest.raises(CannotCreateException):
                await repo.create_open_close_log(log)
        mock_replace.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_open_close_log_write_failure(self):
        repo = self._make_repo()
        log = _open_close_log(business_counter=5)
        collection = self._with_collection(repo)
        collection.update_one.side_effect = RuntimeError("write failed")
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
