# Copyright 2026 masa@kugel
"""Sessions start, commit, abort and end as before (#301, FR-006, C-6).

Under the PyMongo async API `start_session()` is not awaited and
`start_transaction()` is. A missing `await` on the latter leaves no transaction
open, and the writes then commit on their own - so "abort leaves nothing" is the
check that catches it, not "commit keeps the write".

Both ways the services use a session are covered: cart commits explicitly;
journal and terminal also run inside `async with await repo.start_transaction()`.
"""
import pytest

from ._repository import SampleDocument, make_repository


@pytest.mark.asyncio
async def test_commit_keeps_the_writes(test_db):
    repo = await make_repository(test_db)
    await repo.start_transaction()
    assert await repo.create_async(SampleDocument(key="kept"))
    await repo.commit_transaction()

    assert repo.session is None
    assert await test_db["sample"].count_documents({"key": "kept"}) == 1


@pytest.mark.asyncio
async def test_abort_discards_the_writes(test_db):
    repo = await make_repository(test_db)
    # The collection has to exist before a transaction writes to it on older servers.
    await test_db.create_collection("sample")
    await repo.start_transaction()
    assert repo.session.in_transaction
    assert await repo.create_async(SampleDocument(key="discarded"))
    await repo.abort_transaction()

    assert repo.session is None
    assert await test_db["sample"].count_documents({"key": "discarded"}) == 0


@pytest.mark.asyncio
async def test_writes_are_not_visible_outside_the_transaction_before_commit(test_db):
    repo = await make_repository(test_db)
    await test_db.create_collection("sample")
    await repo.start_transaction()
    assert await repo.create_async(SampleDocument(key="pending"))

    assert await test_db["sample"].count_documents({"key": "pending"}) == 0
    await repo.commit_transaction()
    assert await test_db["sample"].count_documents({"key": "pending"}) == 1


@pytest.mark.asyncio
async def test_a_second_repository_shares_the_session(test_db):
    """journal's pattern: one repository opens the transaction, another joins it."""
    owner = await make_repository(test_db, "owner")
    joiner = await make_repository(test_db, "joiner")
    await test_db.create_collection("owner")
    await test_db.create_collection("joiner")

    session = await owner.start_transaction()
    joiner.set_session(session)
    assert await owner.create_async(SampleDocument(key="o"))
    assert await joiner.create_async(SampleDocument(key="j"))
    await owner.abort_transaction()

    assert await test_db["owner"].count_documents({}) == 0
    assert await test_db["joiner"].count_documents({}) == 0


@pytest.mark.asyncio
async def test_async_with_commit_path(test_db):
    """journal / terminal: commit inside `async with await repo.start_transaction()`."""
    repo = await make_repository(test_db)
    await test_db.create_collection("sample")

    async with await repo.start_transaction() as session:
        assert session.in_transaction
        assert await repo.create_async(SampleDocument(key="in-with"))
        await repo.commit_transaction()

    assert repo.session is None
    assert session.has_ended
    assert await test_db["sample"].count_documents({"key": "in-with"}) == 1


@pytest.mark.asyncio
async def test_async_with_abort_path(test_db):
    """journal / terminal: an exception inside the block aborts, and nothing is kept."""
    repo = await make_repository(test_db)
    await test_db.create_collection("sample")

    with pytest.raises(RuntimeError, match="boom"):
        async with await repo.start_transaction() as session:
            try:
                assert await repo.create_async(SampleDocument(key="rolled-back"))
                raise RuntimeError("boom")
            except Exception:
                await repo.abort_transaction()
                raise

    assert repo.session is None
    assert session.has_ended
    assert await test_db["sample"].count_documents({"key": "rolled-back"}) == 0


@pytest.mark.asyncio
async def test_start_transaction_twice_is_refused(test_db):
    from kugel_common.exceptions import RepositoryException

    repo = await make_repository(test_db)
    await repo.start_transaction()
    try:
        with pytest.raises(RepositoryException):
            await repo.start_transaction()
    finally:
        await repo.abort_transaction()
