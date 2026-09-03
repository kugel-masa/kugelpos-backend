# Copyright 2026 masa@kugel
"""Credentials must not reach `app.log` through this service (issue #211).

The request-log middleware masks the bodies this service receives and returns.
These are a different path: values this service reads from the database or
fetches from elsewhere and then prints whole. A staff record carries a
plaintext `pin`; a terminal document carries its `api_key` and that same `pin`
one level down.

Both checks read the source rather than the log, and that is a compromise
rather than a preference. Reaching either line means building a cart service:
a dependency that resolves a terminal over HTTP and then stands up a dozen
repositories against a database. The equivalent checks in terminal and
master-data ARE behavioural, because those call sites can be reached with a
document and nothing else; these two are covered for real by the end-to-end
sentinel scan, which walks both on every run.

A source check is weaker than it looks: it passes on a call that masks one
value and leaves another beside it, and it fails on a rename that changed
nothing. Read it as a reminder, not as proof.
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
