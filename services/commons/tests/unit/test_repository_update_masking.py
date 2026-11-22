# Copyright 2026 masa@kugel
"""A failed update or lookup must not report the values it was given (issue #316).

`update_one_async` put `new_values` into its exception message unmasked, and
the message is logged at ERROR and returned to the caller in the error
response's data. master-data's staff update passes the request body, PIN
included, as `new_values`; a failed update handed the PIN back.
"""

import logging

import pytest
from pymongo.errors import OperationFailure

from kugel_common.exceptions import CannotDeleteException, RepositoryException
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository

PIN = "PIN-316-7c1e"
API_KEY = "KEY-316-a9b2c3"


class _Repo(AbstractRepository[StaffMasterDocument]):
    def __init__(self, collection):
        super().__init__("master_staff", StaffMasterDocument, db=None)
        self.dbcollection = collection


class _Collection:
    """A collection whose every call raises what the test asks for."""

    def __init__(self, error):
        self.error = error

    async def update_one(self, *args, **kwargs):
        raise self.error

    async def find_one(self, *args, **kwargs):
        raise self.error

    async def delete_one(self, *args, **kwargs):
        raise self.error

    def aggregate(self, *args, **kwargs):
        raise self.error


def _staff_update() -> dict:
    return {"id": "S001", "name": "Ann", "pin": PIN, "roles": ["staff"]}


def _emitted(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("the database said no"),
        OperationFailure("bad update", code=2),
        OperationFailure("write conflict", code=112),
    ],
    ids=["driver error", "operation failure", "write conflict after retries"],
)
async def test_a_failed_update_does_not_report_the_pin(caplog, error):
    repo = _Repo(_Collection(error))

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RepositoryException) as exc_info:
            await repo.update_one_async({"id": "S001"}, _staff_update(), retry_interval=0)

    assert PIN not in str(exc_info.value), "the failed staff update reports its pin"
    assert PIN not in _emitted(caplog)
    # Still identifiable: the record and the shape of the update stay readable
    assert "S001" in str(exc_info.value)
    assert "'pin': '****'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_a_failed_lookup_does_not_report_a_credential_in_its_filter(caplog):
    repo = _Repo(_Collection(RuntimeError("down")))

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RepositoryException) as exc_info:
            await repo.get_one_async({"api_key": API_KEY})

    assert API_KEY not in str(exc_info.value)
    assert API_KEY not in _emitted(caplog)


@pytest.mark.asyncio
async def test_a_failed_delete_does_not_report_a_credential_in_its_filter(caplog):
    repo = _Repo(_Collection(RuntimeError("down")))

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RepositoryException) as exc_info:
            await repo.delete_async({"api_key": API_KEY})

    assert API_KEY not in str(exc_info.value)
    assert API_KEY not in _emitted(caplog)


class _DeletesNothing:
    async def find_one(self, *args, **kwargs):
        return {"id": "S001"}

    async def delete_one(self, *args, **kwargs):
        class _Result:
            deleted_count = 0

        return _Result()


@pytest.mark.asyncio
async def test_a_delete_that_removed_nothing_reaches_the_caller_as_cannot_delete():
    # It used to be caught by the same try and re-wrapped as a generic
    # RepositoryException, losing its status and code (#316)
    repo = _Repo(_DeletesNothing())

    with pytest.raises(CannotDeleteException) as exc_info:
        await repo.delete_async({"id": "S001"})

    assert exc_info.value.status_code == 400
