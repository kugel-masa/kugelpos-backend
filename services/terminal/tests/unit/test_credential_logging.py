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

from app.api.common import schemas_transformer
from app.models.repositories import terminal_info_repository


def test_neither_the_terminal_document_nor_the_response_is_printed_whole():
    # Both directions of the same transformer: the document going in carries
    # `api_key` and the staff's `pin`, and BaseTerminal coming out carries
    # `api_key` and `staff_pin` again.
    source = inspect.getsource(schemas_transformer)
    assert "TerminalInfoDocument: {terminal_info}" not in source
    assert "return_terminal: {return_terminal}" not in source, (
        "the response model is logged raw, api_key and staff_pin included"
    )
    assert source.count("mask_loggable(") >= 2


def test_a_failed_terminal_create_does_not_report_the_new_api_key():
    # `api_key` is generated a few lines above the failure message, and that
    # message is both logged and returned to the caller.
    source = inspect.getsource(terminal_info_repository)
    assert "Cannot create terminal info: {terminal_info}" not in source
    assert "mask_loggable(terminal_info)" in source
