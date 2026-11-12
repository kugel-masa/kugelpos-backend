"""insert_if_absent stores a log once and leaves a redelivery's input untouched."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import DuplicateKeyError

from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.repositories.insert_if_absent import insert_if_absent, natural_key_id

KEY = {"tenant_id": "T1", "store_code": "S1", "terminal_no": 1, "generate_date_time": "2026-11-12T09:00:00.000001"}


def _repo(*, upserted_id=None, error=None, session=None):
    repo = MagicMock()
    repo.session = session
    repo.dbcollection.update_one = AsyncMock(
        return_value=MagicMock(upserted_id=upserted_id), side_effect=error
    )
    return repo


def _log():
    return CashInOutLog(tenant_id="T1", store_code="S1", terminal_no=1, generate_date_time=KEY["generate_date_time"])


def test_the_id_is_derived_from_the_natural_key():
    assert natural_key_id(dict(KEY)) == natural_key_id(dict(reversed(list(KEY.items()))))
    assert natural_key_id(KEY) != natural_key_id({**KEY, "terminal_no": 2})


@pytest.mark.asyncio
async def test_an_insert_stores_the_document_under_the_derived_id():
    repo, log = _repo(upserted_id="x"), _log()

    assert await insert_if_absent(repo, KEY, log) is True

    key, update = repo.dbcollection.update_one.await_args.args
    assert key == KEY
    assert update["$setOnInsert"]["_id"] == natural_key_id(KEY)
    assert log.created_at is not None


@pytest.mark.asyncio
async def test_a_redelivery_returns_false_and_leaves_the_input_untouched():
    repo, log = _repo(upserted_id=None), _log()

    assert await insert_if_absent(repo, KEY, log) is False
    assert log.created_at is None


@pytest.mark.asyncio
async def test_a_concurrent_insert_of_the_same_key_reads_as_already_stored():
    # Two deliveries both found nothing; the second one's insert hits _id.
    repo, log = _repo(error=DuplicateKeyError("E11000 duplicate key error ... _id_")), _log()

    assert await insert_if_absent(repo, KEY, log) is False
    assert log.created_at is None


@pytest.mark.asyncio
async def test_inside_a_transaction_the_conflict_is_raised_for_the_caller_to_retry():
    # MongoDB has already aborted the transaction on E11000 (issue #230).
    repo = _repo(error=DuplicateKeyError("E11000"), session=object())

    with pytest.raises(DuplicateKeyError):
        await insert_if_absent(repo, KEY, _log())
