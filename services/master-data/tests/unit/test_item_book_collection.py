"""
Item books are written to master_item_book, the collection the tenant setup
builds with a unique index on item_book_id, and a create that loses the race
for an id takes the next free one instead of failing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kugel_common.exceptions import DuplicateKeyException
from app.models.repositories.item_book_master_repository import ItemBookMasterRepository
from app.services.item_book_master_service import ItemBookMasterService


def test_repository_writes_to_master_item_book():
    db = MagicMock()

    repo = ItemBookMasterRepository(db, "T0001")

    assert repo.collection_name == "master_item_book"


def _service(book_repo):
    return ItemBookMasterService(
        item_book_master_repo=book_repo,
        item_common_master_repo=AsyncMock(),
        item_store_master_repo=AsyncMock(),
    )


def _duplicate():
    return DuplicateKeyException("duplicate", "master_item_book", {"item_book_id": "x"})


@pytest.mark.asyncio
async def test_create_takes_the_next_id_when_the_first_was_taken_meanwhile():
    taken = set()
    book_repo = AsyncMock()
    book_repo.get_item_book_async.side_effect = lambda item_book_id: object() if item_book_id in taken else None

    async def create(doc):
        if not taken:
            # Another request stored the same id between the check and the insert.
            taken.add(doc.item_book_id)
            raise _duplicate()
        return doc

    book_repo.create_item_book_async.side_effect = create

    created = await _service(book_repo).create_item_book_async(title="Book", categories=[])

    first_id = next(iter(taken))
    assert created.item_book_id != first_id
    assert created.item_book_id.endswith("-0002")
    assert book_repo.create_item_book_async.await_count == 2


@pytest.mark.asyncio
async def test_create_gives_up_after_the_attempt_limit():
    book_repo = AsyncMock()
    book_repo.get_item_book_async.return_value = None
    book_repo.create_item_book_async.side_effect = _duplicate()

    with pytest.raises(DuplicateKeyException):
        await _service(book_repo).create_item_book_async(title="Book", categories=[])

    assert book_repo.create_item_book_async.await_count == ItemBookMasterService.ITEM_BOOK_ID_ATTEMPTS
