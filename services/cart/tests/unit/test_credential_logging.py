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

from app.api.v1 import tran
from app.dependencies import get_cart_service


def test_the_terminal_service_response_is_not_printed_whole():
    # What comes back is turned into a TerminalInfoDocument two lines later.
    source = inspect.getsource(tran)
    assert "Terminal service response: {response_data}" not in source, (
        "the terminal service's answer is logged raw, api_key and staff pin included"
    )
    assert "mask_sensitive_data(response_data)" in source


def test_the_terminal_document_is_not_printed_whole():
    source = inspect.getsource(get_cart_service)
    assert "terminal_info: {terminal_info}" not in source, "the terminal document is logged raw"
    assert "mask_loggable(terminal_info)" in source
