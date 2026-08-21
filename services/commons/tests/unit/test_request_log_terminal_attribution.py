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
        # Not evidence for this fix - `_make_tenant_id` falls back to the decoded
        # user, so this passes with the fix reverted. Kept as a guard that the
        # new path does not break the tenant, which is what the log is
        # partitioned by.
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


class TestATerminalThatHasNotBeenOpened:
    """A token is issued before the terminal is ever opened."""

    def test_a_token_without_the_open_claims_does_not_break_the_request(self, captured):
        # `create_terminal_token` omits the claims for state the terminal does
        # not have yet, so `open_counter` arrives as None - and
        # RequestLog.TerminalInfo declares it `int`. The ValidationError escapes
        # the middleware's `finally`, so the route's 200 becomes a 500 and the
        # log is dropped: the defect class of issue #161, reachable here as soon
        # as this field is filled in from a token at all.
        buffer, client = captured
        never_opened = TerminalInfoDocument(
            tenant_id="T6216", store_code="5678", terminal_no=9, terminal_id="T6216-5678-9", status="Idle"
        )
        assert never_opened.open_counter is None, "precondition: the claim is genuinely absent"

        response = client.get("/api/v1/probe", headers=_bearer(never_opened))

        assert response.status_code == 200, "the log middleware hijacked the route's response"
        assert len(buffer.logs) == 1, "the request was not logged at all"
        info = buffer.logs[-1].terminal_info
        assert (info.store_code, info.terminal_no) == ("5678", 9)
        assert (info.business_date, info.open_counter) == ("", 0)


class TestWhenBothCredentialsArePresent:
    def test_the_token_wins_over_the_api_key(self, captured, monkeypatch):
        # The routes resolve the token first (`get_terminal_info_with_jwt_or_apikey`:
        # "Priority 1: Try terminal JWT"), so a request carrying both executes as
        # the token's terminal. Attributing it to the API key's would name a
        # terminal that did not make the request.
        buffer, client = captured
        other = _terminal(store_code="9999", terminal_no=1, terminal_id="T6216-9999-1")

        async def api_key_terminal(*args, **kwargs):
            return other

        monkeypatch.setattr(log_requests_module, "get_terminal_info", api_key_terminal)

        client.get(
            "/api/v1/probe?terminal_id=T6216-9999-1",
            headers={**_bearer(_terminal()), "X-API-Key": "an-api-key"},
        )

        info = buffer.logs[-1].terminal_info
        assert (info.store_code, info.terminal_no) == ("5678", 9), "the API key overrode the token"

    def test_the_api_key_still_works_on_its_own(self, captured, monkeypatch):
        buffer, client = captured

        async def api_key_terminal(*args, **kwargs):
            return _terminal(store_code="9999", terminal_no=1)

        monkeypatch.setattr(log_requests_module, "get_terminal_info", api_key_terminal)

        client.get("/api/v1/probe?terminal_id=T6216-9999-1", headers={"X-API-Key": "an-api-key"})

        info = buffer.logs[-1].terminal_info
        assert (info.store_code, info.terminal_no) == ("9999", 1)


class TestATokenWhoseClaimsAreTheWrongShape:
    """A signature proves the claims were issued unmodified, not that they are sane.

    Anything holding the signing key can mint a token whose claims are the wrong
    type, and this runs in the middleware's `finally` - where a ValidationError
    does not merely lose the attribution, it replaces the route's response.
    """

    @staticmethod
    def _signed(claims):
        import jwt

        from kugel_common.security import ALGORITHM, SECRET_KEY

        base = {
            "sub": "terminal:T6216-5678-9",
            "tenant_id": "T6216",
            "token_type": "terminal",
            "iss": "terminal-service",
        }
        base.update(claims)
        return {"Authorization": f"Bearer {jwt.encode(base, SECRET_KEY, algorithm=ALGORITHM)}"}

    @pytest.mark.parametrize(
        "claims",
        [
            pytest.param({"terminal_no": "nine"}, id="terminal_no is a word"),
            pytest.param({"store_code": ["5678"]}, id="store_code is a list"),
            pytest.param({"open_counter": {"n": 1}}, id="open_counter is an object"),
            pytest.param({"business_date": 20260821}, id="business_date is a number"),
            pytest.param({"staff_id": 1, "staff_name": None}, id="staff_id is a number"),
            pytest.param({"terminal_no": None, "store_code": None}, id="explicit nulls"),
        ],
    )
    def test_the_route_still_answers_and_the_request_is_still_logged(self, captured, claims):
        buffer, client = captured

        response = client.get("/api/v1/probe", headers=self._signed(claims))

        assert response.status_code == 200, f"{claims} hijacked the route's response"
        assert len(buffer.logs) == 1, f"{claims} cost the request log"
