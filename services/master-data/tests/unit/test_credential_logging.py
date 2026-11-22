# Copyright 2026 masa@kugel
"""Credentials must not reach `app.log` through this service (issue #211).

The request-log middleware masks the bodies this service receives and returns.
These are a different path: a staff record read from the database and then
printed whole, whose `pin` is plain text.

The repository checks read the log that was actually emitted rather than the
source that emits it. A source check passes on a call that masks one value and
leaves another beside it, and fails on a rename that changed nothing - it
asserts about the spelling, and the spelling is not the property.
"""

import inspect
import logging
from datetime import datetime

import pytest

from pymongo.errors import DuplicateKeyError

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.api.v1 import schemas_transformer
from app.models.documents.staff_master_document import StaffMasterDocument
from app.services import staff_master_service

PIN = "PIN-IN-THIS-TEST-9f2c"


def _staff() -> StaffMasterDocument:
    # created_at is set because the response transformer formats it; the
    # masking under test is indifferent to it.
    return StaffMasterDocument(id="S001", name="Ann", pin=PIN, created_at=datetime(2026, 9, 3))


class _Repo(AbstractRepository[StaffMasterDocument]):
    """The repository every master-data repository inherits (kugel_common's), with a
    collection that answers however a test needs. master-data used to test a stale
    copy of this class that no repository inherited (#312)."""

    def __init__(self, collection):
        super().__init__("master_staff", StaffMasterDocument, db=None)
        self.dbcollection = collection


class _Inserted:
    def __init__(self, inserted_id="abc"):
        self.inserted_id = inserted_id

    async def insert_one(self, doc, **kwargs):
        return self


class _Duplicate:
    async def insert_one(self, doc, **kwargs):
        raise DuplicateKeyError(
            "E11000 duplicate key", code=11000, details={"key": {"id": "S001"}, "keyValue": {"id": "S001"}}
        )


class _Raises:
    async def insert_one(self, doc, **kwargs):
        raise RuntimeError("the database said no")


def _emitted(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
class TestTheGenericCreatePath:
    """The create path every master shares - so it handles a staff pin too.

    The duplicate and failure cases put the document into a message, so they are
    what catches a mask that stops working. kugel_common logs nothing on a
    successful or unacknowledged insert today; those two cases guard against a
    log line that is added there later without the mask.
    """

    async def test_a_successful_create_does_not_report_the_pin(self, caplog):
        with caplog.at_level(logging.DEBUG):
            assert await _Repo(_Inserted()).create_async(_staff()) is True

        assert PIN not in _emitted(caplog)

    async def test_an_unacknowledged_create_does_not_report_the_pin(self, caplog):
        with caplog.at_level(logging.DEBUG):
            assert await _Repo(_Inserted(inserted_id=None)).create_async(_staff()) is False

        assert PIN not in _emitted(caplog)

    async def test_a_duplicate_does_not_report_the_pin(self, caplog):
        # The exception's message goes back to the caller in the 400's data.
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception) as exc_info:
                await _Repo(_Duplicate()).create_async(_staff())

        assert PIN not in str(exc_info.value), "the duplicate staff record reports its pin"
        assert PIN not in _emitted(caplog)
        # The record is still identifiable, or the message is not worth keeping.
        assert "S001" in str(exc_info.value)

    async def test_a_failed_create_does_not_report_the_pin(self, caplog):
        # The other branch: the driver raised something else.
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception) as exc_info:
                await _Repo(_Raises()).create_async(_staff())

        assert PIN not in str(exc_info.value)
        assert PIN not in _emitted(caplog)
        assert "S001" in str(exc_info.value)


class TestTheStaffTransformer:
    def test_transforming_a_staff_record_does_not_report_its_pin(self, caplog):
        with caplog.at_level(logging.DEBUG):
            schemas_transformer.SchemasTransformerV1().transform_staff(_staff())

        emitted = "\n".join(r.getMessage() for r in caplog.records)
        assert "Transforming staff document" in emitted, "precondition: the line was emitted"
        assert PIN not in emitted
        assert "S001" in emitted


class TestTheDeletePath:
    def test_the_delete_path_does_not_print_the_staff_record(self):
        # Source-checked: the service reads the record from MongoDB before
        # removing it, so calling it means standing up a database. The
        # end-to-end sentinel scan walks this path for real.
        source = inspect.getsource(staff_master_service)
        assert 'logger.debug(f"staff: {staff}")' not in source, "the staff record is logged raw on delete"
        assert "mask_loggable(staff)" in source
