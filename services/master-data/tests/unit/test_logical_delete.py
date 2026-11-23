"""The shared logical-delete helpers (issue #324)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.repositories.logical_delete import NOT_DELETED, alive, hard_delete_async, restore_async, soft_delete_async


def test_not_deleted_counts_a_missing_field_as_alive():
    assert NOT_DELETED == {"is_deleted": {"$ne": True}}


def test_alive_adds_the_condition_to_a_copy():
    key = {"tenant_id": "T1", "item_code": "A"}

    filtered = alive(key, include_deleted=False)

    assert filtered == {"tenant_id": "T1", "item_code": "A", "is_deleted": {"$ne": True}}
    assert key == {"tenant_id": "T1", "item_code": "A"}, "the caller's filter must not change"


def test_alive_leaves_the_filter_alone_when_deleted_records_are_wanted():
    key = {"tenant_id": "T1"}

    filtered = alive(key, include_deleted=True)

    assert filtered == key
    assert filtered is not key


@pytest.mark.asyncio
@pytest.mark.parametrize("matched", [True, False])
async def test_soft_delete_marks_only_a_live_record(matched):
    repo = MagicMock()
    repo.update_one_async = AsyncMock(return_value=matched)

    result = await soft_delete_async(repo, {"tenant_id": "T1", "item_code": "A"})

    assert result is matched
    repo.update_one_async.assert_awaited_once_with(
        {"tenant_id": "T1", "item_code": "A", "is_deleted": {"$ne": True}}, {"is_deleted": True}
    )


def _repo_with_collection():
    repo = MagicMock()
    repo.dbcollection = MagicMock()
    repo.session = None
    repo.collection_name = "master_test"
    return repo


@pytest.mark.asyncio
@pytest.mark.parametrize("matched", [1, 0])
async def test_restore_replaces_only_a_deleted_record_without_stamping_updated_at(matched):
    repo = _repo_with_collection()
    repo.dbcollection.replace_one = AsyncMock(return_value=MagicMock(matched_count=matched))
    document = MagicMock()
    document.model_dump.return_value = {"item_code": "A"}

    result = await restore_async(repo, {"tenant_id": "T1", "item_code": "A"}, document)

    assert result is bool(matched)
    assert document.updated_at is None, "a restored record must look like a new one"
    repo.dbcollection.replace_one.assert_awaited_once_with(
        {"tenant_id": "T1", "item_code": "A", "is_deleted": True}, {"item_code": "A"}, session=None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("deleted", [1, 0])
async def test_a_physical_delete_is_one_write_on_the_key(deleted):
    repo = _repo_with_collection()
    repo.dbcollection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=deleted))

    result = await hard_delete_async(repo, {"tenant_id": "T1", "item_code": "A"})

    assert result is bool(deleted)
    repo.dbcollection.delete_one.assert_awaited_once_with({"tenant_id": "T1", "item_code": "A"}, session=None)
