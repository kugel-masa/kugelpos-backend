# Copyright 2026 masa@kugel
"""Middleware-level tests for credential masking (issue #211).

`test_log_utils_masking.py` covers what gets masked; this file proves the
wiring - that a credential in a request body reaches neither of the two sinks
the middleware writes to:

- the `RequestLog` document handed to the buffer, and
- `app.log`, through the DEBUG line in `_get_request_body`.

The response side matters just as much: the staff master returns the PIN it
was given, so a plain read would put it in the log even if no request ever
carried it.
"""

import inspect
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kugel_common.middleware import log_requests as log_requests_module
from kugel_common.middleware.log_requests import log_requests
from kugel_common.models.repositories import staff_master_web_repository


class _CapturingBuffer:
    """Stands in for RequestLogBuffer; keeps the documents in memory."""

    def __init__(self):
        self.logs = []

    async def add(self, request_log):
        self.logs.append(request_log)


@pytest.fixture
def captured(monkeypatch):
    buffer = _CapturingBuffer()
    monkeypatch.setattr(log_requests_module, "get_request_log_buffer", lambda: buffer)
    return buffer


def _build_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(log_requests("test-service"))

    @app.post("/staff")
    async def create_staff(body: dict):
        # The staff master answers with the record it stored, PIN included.
        return {"success": True, "data": {"id": body.get("id"), "name": body.get("name"), "pin": body.get("pin")}}

    @app.post("/register")
    async def register(body: dict):
        return {"success": True, "data": {"username": body.get("username"), "password": "*****"}}

    return app


class TestTheRequestLogDocument:
    def test_a_staff_pin_is_not_in_the_stored_body(self, captured):
        client = TestClient(_build_app())
        client.post("/staff", json={"id": "S001", "name": "Ann", "pin": "1234"})

        body = captured.logs[0].request_info.body
        assert body == {"id": "S001", "name": "Ann", "pin": "****"}

    def test_a_plaintext_password_is_not_in_the_stored_body(self, captured):
        client = TestClient(_build_app())
        client.post("/register", json={"username": "cashier01", "password": "hunter2"})

        assert "hunter2" not in str(captured.logs[0].model_dump())

    def test_a_pin_echoed_by_the_response_is_not_stored_either(self, captured):
        client = TestClient(_build_app())
        response = client.post("/staff", json={"id": "S001", "name": "Ann", "pin": "1234"})

        # The caller still gets the real response...
        assert response.json()["data"]["pin"] == "1234"
        # ...while the log has neither copy of it.
        assert captured.logs[0].response_info.body["data"]["pin"] == "****"
        assert "1234" not in str(captured.logs[0].model_dump())

    def test_a_request_rejected_before_validation_is_masked_too(self, captured):
        # The body is recorded in the middleware, ahead of FastAPI parsing
        # anything, so a request answered with a 422 is logged in full - a
        # value that never passed a schema included.
        client = TestClient(_build_app())
        response = client.post("/staff", content=b'[{"pin": "1234"}]', headers={"content-type": "application/json"})

        assert response.status_code == 422
        assert "1234" not in str(captured.logs[0].model_dump())

    def test_the_rest_of_the_body_is_still_readable(self, captured):
        # A log that masks everything is not an audit trail.
        client = TestClient(_build_app())
        client.post("/staff", json={"id": "S001", "name": "Ann", "pin": "1234", "roles": ["cashier"]})

        body = captured.logs[0].request_info.body
        assert body["id"] == "S001"
        assert body["name"] == "Ann"
        assert body["roles"] == ["cashier"]


class TestTheApplicationLog:
    def test_the_debug_line_does_not_carry_the_secret(self, captured, caplog):
        # `logger.debug(f"request body: {json_body}")` had no filter of any
        # kind in front of it, so DEBUG on any service put every password and
        # PIN into app.log.
        client = TestClient(_build_app())
        with caplog.at_level(logging.DEBUG, logger="kugel_common.middleware.log_requests"):
            client.post("/register", json={"username": "cashier01", "password": "hunter2"})

        emitted = "\n".join(record.getMessage() for record in caplog.records)
        assert "request body:" in emitted, "precondition: the DEBUG line was supposed to be emitted"
        assert "hunter2" not in emitted


class TestTheTruncationPreview:
    def test_an_oversized_body_is_previewed_from_the_masked_form(self, captured, monkeypatch):
        # The size backstop keeps the first few hundred characters of an
        # oversized body. Taken from the bytes as received - which is what they
        # are, before masking - that preview would hand the secret straight
        # back to the sink the masking exists to keep it out of.
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_MAX_BODY_BYTES", 256)
        client = TestClient(_build_app())
        client.post("/register", json={"password": "hunter2", "filler": "x" * 4096})

        body = captured.logs[0].request_info.body
        assert body["_truncated"] is True
        assert "hunter2" not in body["_preview"]


class TestTheSizeBudgetSurvivesMasking:
    """Masking runs before the budget, and unlike stripping it can GROW a body."""

    def test_a_body_that_masking_pushes_over_the_budget_is_truncated(self, captured, monkeypatch):
        # The budget's shortcut reads the bytes as received to decide a body is
        # small enough to store as-is. That held while the only step was
        # stripping, which can only shrink. `"pin": ""` is two bytes of value
        # and `"pin": "****"` is six, so a body inside the budget on the wire
        # can be outside it once stored.
        raw = json.dumps({f"entry{i}": {"pin": ""} for i in range(50)}, separators=(",", ":")).encode()
        # The budget is exactly what arrived, so the shortcut is taken: the
        # body IS within it as received. Only the stored form is not.
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_MAX_BODY_BYTES", len(raw))
        client = TestClient(_build_app())
        client.post("/staff", content=raw, headers={"content-type": "application/json"})

        stored = captured.logs[0].request_info.body
        assert stored.get("_truncated") is True, (
            f"a masked body of {len(json.dumps(stored).encode())} bytes was stored "
            f"under a {len(raw)} byte budget"
        )

    def test_a_body_with_no_secrets_still_takes_the_shortcut(self, captured, monkeypatch):
        # The shortcut is why the budget costs nothing on the requests that
        # carry no credential, which is nearly all of them. Withholding the raw
        # bytes for every request would put a second serialization of every body
        # on every service.
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_MAX_BODY_BYTES", 900)
        client = TestClient(_build_app())
        client.post("/staff", json={"id": "S001", "name": "Ann"})

        assert captured.logs[0].request_info.body == {"id": "S001", "name": "Ann"}


class TestTheHeaderLogsOutsideTheHttpClient:
    """A caller that logs its own headers is the same sink one level up."""

    def test_the_staff_repository_does_not_print_its_credential(self):
        # `get_service_client` is what HttpClientHelper masks; this repository
        # builds the headers itself and logs them before handing them over, so
        # masking the client alone left the credential in app.log.
        source = inspect.getsource(staff_master_web_repository)
        assert "headers: {headers}" not in source, (
            "the staff repository logs its Authorization / X-API-KEY header verbatim"
        )
        assert "mask_sensitive_data(headers)" in source


class TestThe422HandedBackToTheCaller:
    """`register_exception_handlers` puts `str(exc.errors())` in `data`."""

    def test_the_rejected_value_is_not_echoed_back(self, caplog):
        # Each validation error carries the raw `input` that failed, and the
        # handler writes that string to the ERROR log AND returns it in the
        # response - so a PIN that fails a length rule comes back to whoever
        # sent it, and is on disk either way.
        from pydantic import BaseModel, Field

        from kugel_common.exceptions import register_exception_handlers

        class Staff(BaseModel):
            pin: str = Field(min_length=6)

        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/staff")
        async def create_staff(body: Staff):  # pragma: no cover - never reached
            return {"ok": True}

        with caplog.at_level(logging.ERROR):
            response = TestClient(app).post("/staff", json={"pin": "1234"})

        assert response.status_code == 422
        assert "1234" not in response.text, "the rejected PIN was handed back to the caller"
        assert "1234" not in "\n".join(record.getMessage() for record in caplog.records)
        # The caller still learns which field was wrong and why.
        assert "pin" in response.json()["message"]

    def test_a_field_that_is_not_secret_still_reports_what_it_received(self, caplog):
        from pydantic import BaseModel

        from kugel_common.exceptions import register_exception_handlers

        class Line(BaseModel):
            quantity: int

        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/lines")
        async def add_line(body: Line):  # pragma: no cover - never reached
            return {"ok": True}

        response = TestClient(app).post("/lines", json={"quantity": "abc"})

        assert response.status_code == 422
        assert "abc" in response.text, "a 422 that does not say what it rejected is not diagnosable"
