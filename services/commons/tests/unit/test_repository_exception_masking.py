# Copyright 2026 masa@kugel
"""A failed create must not report what it was given (issue #211).

`CannotCreateException` puts the whole document into its message, and that
message travels further than a log line: the exception handlers return
`str(exc)` to the caller in the 400's `data`. So a staff record that fails to
be created hands its plaintext `pin` back to whoever sent it, and a terminal
that fails to be created hands back the `api_key` just generated for it.

Masked in the exception rather than at each `raise` - there are more than
twenty call sites across the services, and they are the kind of line nobody
re-reads.
"""

from kugel_common.exceptions.repository_exceptions import CannotCreateException
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument


def test_a_staff_record_does_not_carry_its_pin_into_the_message():
    document = StaffMasterDocument(id="S001", name="Ann", pin="1234")

    exc = CannotCreateException("inserted_id is None", "staff_master", document)

    assert "1234" not in str(exc), "the rejected staff record reports its pin"
    # The rest of the record stays readable, or the 400 says nothing useful.
    assert "S001" in str(exc)
    assert "'pin': '****'" in str(exc)


def test_a_terminal_does_not_carry_its_api_key_into_the_message():
    document = TerminalInfoDocument(terminal_id="T-1", api_key="abcd1234efgh5678")

    exc = CannotCreateException("Cannot create terminal info", "terminal_info", document)

    assert "abcd1234efgh5678" not in str(exc), "the rejected terminal reports its api_key"
    assert "T-1" in str(exc)


def test_a_document_that_is_not_a_model_still_reports_itself():
    # Several call sites pass a plain identifier rather than a document, and a
    # 400 that names nothing is not worth raising.
    exc = CannotCreateException("Cannot create cart", "cart", "cart-0001")

    assert "cart-0001" in str(exc)


def test_the_original_document_is_not_modified():
    # This runs while the caller still holds the object it tried to store.
    document = StaffMasterDocument(id="S001", name="Ann", pin="1234")

    CannotCreateException("inserted_id is None", "staff_master", document)

    assert document.pin == "1234"
