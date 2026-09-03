# Copyright 2026 masa@kugel
"""Credentials must not reach `app.log` through this service (issue #211).

The request-log middleware masks the bodies this service receives and returns.
These are a different path: values this service reads or receives from
elsewhere and then prints whole. A staff record carries a plaintext `pin` and
a terminal document carries its `api_key` plus that same `pin` one level down,
so printing either object prints a credential.

Each check reads the source rather than the log, because the defect is the
shape of the call - an object interpolated raw - and that is what must not
come back.
"""

import inspect

from app.api.v1 import schemas_transformer
from app.models.repositories import abstract_repository


def test_the_staff_document_is_not_printed_whole():
    source = inspect.getsource(schemas_transformer)
    assert "staff document: {staff_doc}" not in source, "the staff document is logged raw, pin included"
    assert "mask_sensitive_data(staff_doc.model_dump())" in source


def test_the_create_log_does_not_print_the_document_whole():
    # Generic over every master, so it prints a staff record's pin too - and at
    # INFO rather than DEBUG, which is the level most deployments keep.
    source = inspect.getsource(abstract_repository)
    assert "created in database: {document}" not in source, "every created document is logged raw"
    assert "mask_sensitive_data(document.model_dump())" in source
