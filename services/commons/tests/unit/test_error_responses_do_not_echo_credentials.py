# Copyright 2026 masa@kugel
"""An error response must not hand back the value it rejected (issue #211).

An error is the one place a service deliberately quotes its input back. Both
handler modules do it: the 422 formats `exc.errors()`, whose every entry
carries the raw `input`, and the AppException path formats `str(exc)`, which
for a repository failure carries the document that failed to be created. Both
reach the ERROR log AND the response.

There are two of these modules. `exceptions/exception_handlers.py` is the one
every service registers; `utils/api_exception_handler.py` is a second
implementation of the same handlers that nothing imports but its own tests.
It is covered here anyway - it does not echo the input today, and this is what
notices if someone makes it match its twin without carrying the masking over.
"""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from kugel_common.exceptions import register_exception_handlers
from kugel_common.exceptions.repository_exceptions import CannotCreateException
from kugel_common.models.documents.staff_master_document import StaffMasterDocument

PIN = "PIN-IN-THIS-TEST-6b1d"
API_KEY = "APIKEY-IN-THIS-TEST-3b7e"


class _Staff(BaseModel):
    pin: str = Field(min_length=32)
    note: str = "x"


def _app_with(handlers) -> FastAPI:
    app = FastAPI()
    handlers(app)

    @app.post("/staff")
    async def create(body: _Staff):  # pragma: no cover - never reached
        return {"ok": True}

    @app.post("/fail")
    async def fail():
        raise CannotCreateException(
            "inserted_id is None", "master_staff", StaffMasterDocument(id="S001", name="Ann", pin=PIN)
        )

    return app


def _register_via_utils(app: FastAPI) -> None:
    """Wire up the other module, whose handlers are factories rather than a setup call."""
    from fastapi.exceptions import RequestValidationError

    from kugel_common.exceptions.base_exceptions import AppException
    from kugel_common.utils.api_exception_handler import (
        create_app_exception_handler,
        create_request_validation_exception_handler,
    )

    app.add_exception_handler(RequestValidationError, create_request_validation_exception_handler())
    app.add_exception_handler(AppException, create_app_exception_handler())


HANDLERS = {
    "registered by every service": register_exception_handlers,
    "the unused twin": _register_via_utils,
}


@pytest.mark.parametrize("label", sorted(HANDLERS))
class TestWhatAnErrorSaysBack:
    def test_a_rejected_pin_is_not_returned_or_logged(self, label, caplog):
        client = TestClient(_app_with(HANDLERS[label]), raise_server_exceptions=False)

        with caplog.at_level(logging.ERROR):
            response = client.post("/staff", json={"pin": PIN})

        assert response.status_code == 422
        assert PIN not in response.text, f"{label}: the rejected pin came back to the caller"
        assert PIN not in "\n".join(r.getMessage() for r in caplog.records), f"{label}: and into the log"

    def test_the_caller_still_learns_what_was_wrong(self, label):
        client = TestClient(_app_with(HANDLERS[label]), raise_server_exceptions=False)

        response = client.post("/staff", json={"pin": PIN})

        # Which field, and why. An error that says neither is not worth returning.
        assert "pin" in response.text
        assert "least 32" in response.text or "min_length" in response.text

    def test_a_document_that_could_not_be_created_is_not_returned_or_logged(self, label, caplog):
        client = TestClient(_app_with(HANDLERS[label]), raise_server_exceptions=False)

        with caplog.at_level(logging.ERROR):
            response = client.post("/fail")

        assert PIN not in response.text, f"{label}: the document came back to the caller"
        assert PIN not in "\n".join(r.getMessage() for r in caplog.records), f"{label}: and into the log"
        # Still identifiable: which collection, which record.
        assert "master_staff" in response.text or "S001" in response.text


def test_a_terminal_that_could_not_be_created_keeps_its_api_key():
    # The other document that a failed create reports. The key is generated
    # moments before the failure, so it has never been anywhere else.
    from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument

    exc = CannotCreateException(
        "Cannot create terminal info", "info_terminal", TerminalInfoDocument(terminal_id="T-1", api_key=API_KEY)
    )

    assert API_KEY not in str(exc)
    assert "T-1" in str(exc)
