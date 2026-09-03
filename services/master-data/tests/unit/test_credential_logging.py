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

from app.api.v1 import schemas_transformer
from app.models.documents.staff_master_document import StaffMasterDocument
from app.models.repositories.abstract_repository import AbstractRepository
from app.services import staff_master_service

PIN = "PIN-IN-THIS-TEST-9f2c"


def _staff() -> StaffMasterDocument:
    # created_at is set because the response transformer formats it; the
    # masking under test is indifferent to it.
    return StaffMasterDocument(id="S001", name="Ann", pin=PIN, created_at=datetime(2026, 9, 3))


class _Repo(AbstractRepository[StaffMasterDocument]):
    """The abstract repository with a collection that answers however we need."""

    def __init__(self, insert_result):
        super().__init__("master_staff", StaffMasterDocument, db=None)
        self.dbcollection = insert_result

    async def create_async(self, document):  # pragma: no cover - inherited
        return await super().create_async(document)


class _Inserted:
    def __init__(self, inserted_id="abc"):
        self.inserted_id = inserted_id

    async def insert_one(self, doc):
        return self


class _Raises:
    async def insert_one(self, doc):
        raise RuntimeError("the database said no")


@pytest.mark.asyncio
class TestTheGenericCreateLog:
    """One log line, over every master - so it prints a staff pin too."""

    async def test_a_successful_create_does_not_report_the_pin(self, caplog):
        # At INFO, not DEBUG, which is the level most deployments keep.
        repo = _Repo(_Inserted())
        with caplog.at_level(logging.INFO):
            await repo.create_async(_staff())

        emitted = "\n".join(r.getMessage() for r in caplog.records)
        assert "created in database" in emitted, "precondition: the line was supposed to be emitted"
        assert PIN not in emitted
        # The record is still identifiable, or the log is not worth keeping.
        assert "S001" in emitted

    async def test_a_refused_create_does_not_report_the_pin(self, caplog):
        # `CannotCreateException` puts the document in its message, and the
        # handlers return that message to the caller in the 400's `data`.
        repo = _Repo(_Inserted(inserted_id=None))
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception) as exc_info:
                await repo.create_async(_staff())

        assert PIN not in str(exc_info.value), "the rejected staff record reports its pin"
        assert PIN not in "\n".join(r.getMessage() for r in caplog.records)

    async def test_a_failed_create_does_not_report_the_pin(self, caplog):
        # The other branch: the driver raised rather than the id being None.
        repo = _Repo(_Raises())
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception) as exc_info:
                await repo.create_async(_staff())

        assert PIN not in str(exc_info.value)
        assert PIN not in "\n".join(r.getMessage() for r in caplog.records)


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
