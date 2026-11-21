# Copyright 2026 masa@kugel
"""Unit tests for TestTerminalInfoRepository (split from
test_repositories.py by class group)."""
from unittest.mock import AsyncMock, patch

import pytest

from kugel_common.exceptions import (
    AlreadyExistException,
    CannotCreateException,
    NotFoundException,
    UpdateNotWorkException,
    CannotDeleteException,
)
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from kugel_common.utils.terminal_api_key import hash_api_key

from ._helpers import _mock_db, _terminal_info_doc


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
    async def test_create_stores_only_the_digest(self):
        """The key is returned once; the document written holds its digest and
        no plaintext (issue #136)."""
        repo = self._make_repo("T1")
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create,
        ):
            result = await repo.create_terminal_info(store_code="S1", terminal_no=1, description="desc")
        written = mock_create.await_args.args[0]
        assert written.api_key is None
        assert written.api_key_hash == hash_api_key(result.api_key)
        assert repo.terminal_info.api_key is None
        assert "api_key" not in {k for k, v in written.model_dump().items() if v}

    @pytest.mark.asyncio
    async def test_reissue_replaces_the_digest_and_returns_the_new_key_once(self):
        repo = self._make_repo("T1")
        old_hash = hash_api_key("old-key")
        doc = _terminal_info_doc(api_key=None, api_key_hash=old_hash)
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update,
        ):
            result = await repo.reissue_api_key_async("T1-S1-1")
        new_key = result.api_key
        assert new_key and new_key != "old-key"
        update = mock_update.await_args.args[1]
        assert update == {"api_key_hash": hash_api_key(new_key), "api_key": None}
        assert update["api_key_hash"] != old_hash
        assert repo.terminal_info.api_key is None

    @pytest.mark.asyncio
    async def test_reissue_unknown_terminal_raises_not_found(self):
        repo = self._make_repo("T1")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            with pytest.raises(NotFoundException):
                await repo.reissue_api_key_async("T1-S1-999")

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
        doc = _terminal_info_doc(api_key=None, api_key_hash=hash_api_key("key123"), status="Opened")
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update:
            result = await repo.replace_terminal_info_async("T1-S1-1", doc)
        assert result is True
        filter_, values = mock_update.await_args.args
        assert filter_ == {"terminal_id": "T1-S1-1"}
        assert values["status"] == "Opened"
        assert doc.updated_at is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "credential",
        [{"api_key": None, "api_key_hash": "stale-digest"}, {"api_key": "stale-plaintext", "api_key_hash": None}],
    )
    async def test_replace_never_writes_the_credential(self, credential):
        """The document was read before the caller's work; writing its key back
        would undo a reissue that ran in between (issue #136)."""
        repo = self._make_repo()
        doc = _terminal_info_doc(**credential)
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update:
            await repo.replace_terminal_info_async("T1-S1-1", doc)
        values = mock_update.await_args.args[1]
        assert "api_key" not in values
        assert "api_key_hash" not in values

    @pytest.mark.asyncio
    async def test_replace_terminal_info_fails(self):
        repo = self._make_repo()
        doc = _terminal_info_doc()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
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
