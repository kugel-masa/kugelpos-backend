# Copyright 2026 masa@kugel
"""Terminal attribution on a JWT-authenticated request (issue #181).

The API-key path resolves the terminal from `X-API-Key` plus a `terminal_id`
parameter. A terminal-JWT request carries neither - that is the point of the
migration - so the request log recorded an empty terminal for exactly the
credential the fleet is moving to: no store, no terminal number, no business
date, no open counter, and no staff.

The claims carry all of it, so the fix is to read rather than look up. What these
tests pin is that it is read, that the API key still wins where both are present,
and above all that nothing here can raise: this runs in the logging middleware's
`finally`, where an exception replaces whatever the route was returning - the
defect class of issue #161.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kugel_common.middleware import log_requests as log_requests_module
from kugel_common.middleware.log_requests import log_requests
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.terminal_auth import create_terminal_token


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

    app = FastAPI()
    app.middleware("http")(log_requests("test-service"))

    @app.get("/api/v1/probe")
    async def probe():
        return {"ok": True}

    @app.get("/api/v1/boom")
    async def boom():
        raise ValueError("the route failed on its own terms")

    return buffer, TestClient(app, raise_server_exceptions=False)


def _terminal(signed_in=True, **overrides):
    fields = dict(
        tenant_id="T6216",
        store_code="5678",
        terminal_no=9,
        terminal_id="T6216-5678-9",
        status="Opened",
        business_date="20260821",
        open_counter=3,
        business_counter=41,
    )
    fields.update(overrides)
    terminal = TerminalInfoDocument(**fields)
    if signed_in:
        terminal.staff = StaffMasterDocument(
            tenant_id=fields["tenant_id"], store_code=fields["store_code"], id="S001", name="Staff1"
        )
    return terminal


def _bearer(terminal):
    return {"Authorization": f"Bearer {create_terminal_token(terminal)}"}


class TestWhatTheTokenSays:
    def test_the_store_and_terminal_are_recorded(self, captured):
        buffer, client = captured

        client.get("/api/v1/probe", headers=_bearer(_terminal()))

        info = buffer.logs[-1].terminal_info
        assert info is not None
        assert (info.tenant_id, info.store_code, info.terminal_no) == ("T6216", "5678", 9)

    def test_the_business_date_and_open_counter_are_recorded(self, captured):
        # Without these a rollback or a numbering question cannot be tied to a
        # session, only to a terminal.
        buffer, client = captured

        client.get("/api/v1/probe", headers=_bearer(_terminal()))

        info = buffer.logs[-1].terminal_info
        assert (info.business_date, info.open_counter) == ("20260821", 3)

    def test_the_signed_in_staff_is_recorded(self, captured):
        buffer, client = captured

        client.get("/api/v1/probe", headers=_bearer(_terminal()))

        staff = buffer.logs[-1].staff_info
        assert (staff.id, staff.name) == ("S001", "Staff1")

    def test_a_terminal_that_is_not_signed_in_records_no_staff(self, captured):
        buffer, client = captured

        client.get("/api/v1/probe", headers=_bearer(_terminal(signed_in=False)))

        assert buffer.logs[-1].staff_info.id == ""
        assert buffer.logs[-1].terminal_info.store_code == "5678"

    def test_the_tenant_is_still_recorded(self, captured):
        buffer, client = captured

        client.get("/api/v1/probe", headers=_bearer(_terminal()))

        assert buffer.logs[-1].tenant_id == "T6216"


class TestNothingHereMayRaise:
    """This runs in the middleware's `finally` block."""

    def test_a_request_with_no_token_is_still_logged(self, captured):
        buffer, client = captured

        response = client.get("/api/v1/probe")

        assert response.status_code == 200
        assert buffer.logs[-1].terminal_info.store_code == ""

    def test_a_garbage_token_is_still_logged(self, captured):
        buffer, client = captured

        response = client.get("/api/v1/probe", headers={"Authorization": "Bearer not-a-token"})

        assert response.status_code == 200
        assert len(buffer.logs) == 1
        assert buffer.logs[-1].terminal_info.store_code == ""

    def test_a_token_signed_with_the_wrong_key_is_still_logged(self, captured, monkeypatch):
        buffer, client = captured
        token = create_terminal_token(_terminal())
        monkeypatch.setattr("kugel_common.security.SECRET_KEY", "a-different-secret-entirely")

        response = client.get("/api/v1/probe", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert buffer.logs[-1].terminal_info.store_code == ""

    def test_a_failing_route_still_fails_on_its_own_terms(self, captured):
        # The failure the client sees must be the route's, not one this helper
        # introduced on the way out (issue #161).
        buffer, client = captured

        response = client.get("/api/v1/boom", headers={"Authorization": "Bearer not-a-token"})

        assert response.status_code == 500
        assert len(buffer.logs) == 1


class TestPrecedence:
    def test_a_non_terminal_token_names_no_terminal(self, captured):
        # A user or service-account JWT is not a terminal, and must not be
        # recorded as one.
        from datetime import datetime, timedelta, timezone

        import jwt

        from kugel_common.security import ALGORITHM, SECRET_KEY

        buffer, client = captured
        user_token = jwt.encode(
            {
                "sub": "admin",
                "tenant_id": "T6216",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        client.get("/api/v1/probe", headers={"Authorization": f"Bearer {user_token}"})

        assert buffer.logs[-1].terminal_info.store_code == ""
        assert buffer.logs[-1].user_info.username == "admin"
