# Copyright 2026 masa@kugel
"""Credentials must not reach `app.log` through this service (issue #211).

The request-log middleware masks the bodies this service receives and returns.
This is a different path: a terminal document read from the database and then
printed whole - `api_key`, and the staff's plaintext `pin` one level down.

The transformer is checked by reading the log it actually emitted. A source
check asserts about the spelling of the call, and the spelling is not the
property: it passes on a call that masks one value and leaves another beside
it, which is exactly the mistake made here once already - the input document
was masked and `return_terminal`, built from it three lines later, was not.
"""

import inspect
import logging
from datetime import datetime

from app.api.common.schemas_transformer import SchemasTransformer
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.repositories import terminal_info_repository

API_KEY = "APIKEY-IN-THIS-TEST-3b7e"
PIN = "PIN-IN-THIS-TEST-9f2c"


def _terminal() -> TerminalInfoDocument:
    return TerminalInfoDocument(
        terminal_id="T0001-5678-9",
        tenant_id="T0001",
        store_code="5678",
        terminal_no=9,
        description="Lane 9",
        function_mode="Sales",
        status="Opened",
        open_counter=1,
        business_counter=1,
        api_key=API_KEY,
        staff=StaffMasterDocument(id="S001", name="Ann", pin=PIN),
        # BaseTerminal formats its entry_datetime from this.
        created_at=datetime(2026, 9, 3),
    )


class TestTheTerminalTransformer:
    """Both directions: the document going in and the model coming out."""

    def test_neither_the_document_nor_the_response_reports_a_credential(self, caplog):
        with caplog.at_level(logging.DEBUG):
            SchemasTransformer().transform_terminal(_terminal())

        emitted = "\n".join(r.getMessage() for r in caplog.records)
        assert "TerminalInfoDocument" in emitted, "precondition: the input line was emitted"
        assert "return_terminal" in emitted, "precondition: the output line was emitted"
        assert API_KEY not in emitted, "the api_key is readable in the log"
        assert PIN not in emitted, "the staff's pin is readable in the log"

    def test_the_terminal_is_still_identifiable(self, caplog):
        # A log that masks everything is not worth keeping.
        with caplog.at_level(logging.DEBUG):
            SchemasTransformer().transform_terminal(_terminal())

        emitted = "\n".join(r.getMessage() for r in caplog.records)
        assert "T0001-5678-9" in emitted
        assert "S001" in emitted

    def test_the_caller_still_receives_the_api_key_when_it_asks(self, caplog):
        # Masking is about the log. The response model is unaffected, and the
        # terminal service does hand the key back on creation.
        result = SchemasTransformer().transform_terminal(_terminal(), include_api_key=True)

        assert result.api_key == API_KEY


class TestTheCreateFailurePath:
    def test_a_failed_terminal_create_does_not_report_the_new_api_key(self):
        # Source-checked: reaching this branch means a repository with a
        # database behind it. The api_key is generated four lines above the
        # message, and the message is both logged and returned to the caller.
        source = inspect.getsource(terminal_info_repository)
        assert "Cannot create terminal info: {terminal_info}" not in source
        assert "mask_loggable(terminal_info)" in source
