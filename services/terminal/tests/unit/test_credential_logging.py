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

from app.api.common import schemas_transformer


def test_the_terminal_document_is_not_printed_whole():
    source = inspect.getsource(schemas_transformer)
    assert "TerminalInfoDocument: {terminal_info}" not in source, (
        "the terminal document is logged raw, api_key and staff pin included"
    )
    assert "mask_sensitive_data(terminal_info.model_dump())" in source
