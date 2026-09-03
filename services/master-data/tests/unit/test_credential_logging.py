# Copyright 2026 masa@kugel
"""Credentials must not reach `app.log` through this service (issue #211).

The request-log middleware masks the bodies this service receives and returns.
These are a different path: values this service reads from the database or
fetches from elsewhere and then prints whole. A staff record carries a
plaintext `pin`; a terminal document carries its `api_key` and that same `pin`
one level down.

Each check reads the source rather than the log, because the defect is the
shape of the call - an object interpolated raw - and that is what must not
come back.
"""

import inspect

from app.api.v1 import schemas_transformer
from app.models.repositories import abstract_repository
from app.services import staff_master_service


def test_the_staff_document_is_not_printed_whole():
    source = inspect.getsource(schemas_transformer)
    assert "staff document: {staff_doc}" not in source, "the staff document is logged raw, pin included"
    assert "mask_loggable(staff_doc)" in source


def test_the_delete_path_does_not_print_the_staff_record():
    # The record is read before it is removed, and printed on the way.
    source = inspect.getsource(staff_master_service)
    assert 'logger.debug(f"staff: {staff}")' not in source, "the staff record is logged raw on delete"
    assert "mask_loggable(staff)" in source


def test_no_path_through_the_repository_prints_the_document_whole():
    # The create log is generic over every master, so it prints a staff
    # record's pin too - and at INFO. The failure messages beside it reach
    # further still: the exception handlers return `str(exc)` to the caller.
    source = inspect.getsource(abstract_repository)
    assert "created in database: {document}" not in source
    assert "save document to database: {document}" not in source
    assert "document->{document}" not in source, "the replace failure reports the document raw"
    assert source.count("mask_loggable(document)") == 3
