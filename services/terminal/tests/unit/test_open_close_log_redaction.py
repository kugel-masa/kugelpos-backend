# Copyright 2026 masa@kugel
"""What an open/close log is allowed to carry (issue #211).

`OpenCloseLog.terminal_info` is a whole `TerminalInfoDocument`, and the log is
not only printed: it is stored in this service's database, published to
journal and report, and stored and printed by both. So whatever it carries,
three databases and three services' logs carry.

The open path already blanked the `api_key` before this issue - the intent was
there. The close path assigned the live terminal straight through, so the key
reached all of it in plain text, and neither path touched the staff's `pin`.
"""

import pytest

from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.services.terminal_service import MASKED_API_KEY, _terminal_info_for_log
from kugel_common.models.documents.staff_master_document import StaffMasterDocument


def _terminal() -> TerminalInfoDocument:
    return TerminalInfoDocument(
        terminal_id="T0001-5678-9",
        tenant_id="T0001",
        store_code="5678",
        terminal_no=9,
        api_key="abcd1234efgh5678",
        staff=StaffMasterDocument(id="S001", name="Ann", pin="1234"),
    )


def test_the_api_key_does_not_survive():
    redacted = _terminal_info_for_log(_terminal())

    assert redacted.api_key == MASKED_API_KEY
    assert "abcd1234efgh5678" not in str(redacted.model_dump())


def test_the_staff_pin_does_not_survive():
    # `model_copy()` is shallow, so the staff object was shared with the live
    # terminal and its pin travelled with the log.
    redacted = _terminal_info_for_log(_terminal())

    assert redacted.staff.pin == "****"
    assert "1234" not in str(redacted.model_dump())


def test_the_live_terminal_is_not_changed():
    # The counterpart of the shallow copy: blanking the pin on a shared staff
    # object would blank it on the terminal the caller is still using, which
    # is then written back to the database.
    terminal = _terminal()

    _terminal_info_for_log(terminal)

    assert terminal.api_key == "abcd1234efgh5678"
    assert terminal.staff.pin == "1234"


def test_everything_else_is_still_there():
    # An open/close record has to stay readable: which terminal, which store,
    # which staff member.
    redacted = _terminal_info_for_log(_terminal())

    assert redacted.terminal_id == "T0001-5678-9"
    assert redacted.store_code == "5678"
    assert redacted.terminal_no == 9
    assert redacted.staff.id == "S001"
    assert redacted.staff.name == "Ann"


def test_a_terminal_with_no_staff_is_handled():
    terminal = _terminal()
    terminal.staff = None

    redacted = _terminal_info_for_log(terminal)

    assert redacted.staff is None
    assert redacted.api_key == MASKED_API_KEY


@pytest.mark.parametrize("operation", ["open", "close"])
def test_both_paths_use_the_same_redaction(operation):
    # The defect was that only one of them did. Read from the source, because
    # exercising sign-in/close needs the whole service.
    import inspect

    from app.services import terminal_service

    source = inspect.getsource(terminal_service)
    assert source.count("open_close_log.terminal_info = _terminal_info_for_log(terminal)") == 2, (
        "the open and close paths do not both redact the terminal they embed"
    )
    assert "open_close_log.terminal_info = terminal\n" not in source
