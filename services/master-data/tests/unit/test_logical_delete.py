"""The shared logical-delete helpers (issue #324)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.repositories.logical_delete import NOT_DELETED, alive, restore_async, soft_delete_async


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


@pytest.mark.asyncio
@pytest.mark.parametrize("matched", [True, False])
async def test_restore_replaces_only_a_deleted_record(matched):
    repo = MagicMock()
    repo.replace_one_async = AsyncMock(return_value=matched)
    document = MagicMock()

    result = await restore_async(repo, {"tenant_id": "T1", "item_code": "A"}, document)

    assert result is matched
    repo.replace_one_async.assert_awaited_once_with({"tenant_id": "T1", "item_code": "A", "is_deleted": True}, document)
