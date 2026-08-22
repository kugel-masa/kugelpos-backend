# Copyright 2026 masa@kugel
"""The request logger does not get a vote on the response (issue #161).

The middleware assembles its record in a `finally` block, which runs while the
route's own exception is still in flight — so an exception raised there
*replaces* it. `_get_terminal_info` called `security.get_terminal_info`
unguarded, and that maps any `HttpClientError` onto `HTTPException(401)`: a
terminal service that is merely unreachable arrived as an authentication
failure, escaped the block, and turned a request the route had already answered
into a 500 with no request log at all.

Reported from a live stack as a *successful* authentication answered 500, three
seconds late, with a false audit entry and nothing logged.

Two properties are pinned here, and they are not the same one: the caller's
response is never changed by anything in that block, and the request is still
recorded when part of its context could not be resolved.
"""

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from kugel_common.middleware import log_requests as log_requests_module
from kugel_common.middleware.log_requests import log_requests


class _CapturingBuffer:
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

    @app.get("/api/v1/ok")
    async def ok():
        return {"ok": True}

    @app.get("/api/v1/unauthorized")
    async def unauthorized():
        raise HTTPException(status_code=401, detail="Invalid credentials")

    @app.post("/api/v1/echo")
    async def echo(request: Request):
        return {"len": len(await request.body())}

    return buffer, TestClient(app, raise_server_exceptions=False)


def _api_key_request():
    """The shape that reaches the terminal lookup: an API key plus a terminal_id."""
    return {"params": {"terminal_id": "T0001-5678-9"}, "headers": {"X-API-Key": "an-api-key"}}


def _terminal_lookup_raises(monkeypatch, error):
    async def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr(log_requests_module, "get_terminal_info", boom)


class TestTheRouteKeepsItsAnswer:
    def test_a_401_stays_a_401(self, captured, monkeypatch):
        # The defect verbatim: security.get_terminal_info reports an unreachable
        # terminal service as HTTPException(401), and unguarded that replaced the
        # route's own 401 with a 500.
        buffer, client = captured
        _terminal_lookup_raises(monkeypatch, HTTPException(status_code=401, detail="Invalid api_key"))
        req = _api_key_request()

        response = client.get("/api/v1/unauthorized", **req)

        assert response.status_code == 401, "the request logger turned the route's 401 into something else"
        assert response.json()["detail"] == "Invalid credentials", (
            "it answered with the logger's error, not the route's"
        )

    def test_a_success_stays_a_success(self, captured, monkeypatch):
        # Reported from a live stack: a request that authenticated correctly
        # answered 500 because the log's own lookup could not reach the service.
        buffer, client = captured
        _terminal_lookup_raises(monkeypatch, HTTPException(status_code=401, detail="Invalid api_key"))

        response = client.get("/api/v1/ok", **_api_key_request())

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_it_holds_for_any_failure_in_that_block(self, captured, monkeypatch):
        # Not only the terminal lookup. Everything in there is observability, and
        # none of it may reach the caller.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise RuntimeError("the audit buffer is unavailable")

        monkeypatch.setattr(log_requests_module, "get_request_log_buffer", lambda: type("B", (), {"add": boom})())

        response = client.get("/api/v1/ok")

        assert response.status_code == 200


class TestTheRequestIsStillRecorded:
    def test_an_unresolvable_terminal_costs_the_terminal_and_nothing_else(self, captured, monkeypatch):
        buffer, client = captured
        _terminal_lookup_raises(monkeypatch, HTTPException(status_code=401, detail="Invalid api_key"))

        client.get("/api/v1/ok", **_api_key_request())

        assert len(buffer.logs) == 1, "the request was not logged at all"
        logged = buffer.logs[-1]
        assert logged.request_info.url.endswith("terminal_id=T0001-5678-9")
        assert logged.response_info.status_code == 200
        assert logged.terminal_info.store_code == ""

    def test_a_failed_request_is_recorded_with_its_status(self, captured, monkeypatch):
        # A refusal is what an audit trail most needs to hold, and it was exactly
        # the case that recorded nothing.
        buffer, client = captured
        _terminal_lookup_raises(monkeypatch, HTTPException(status_code=401, detail="Invalid api_key"))

        client.get("/api/v1/unauthorized", **_api_key_request())

        assert len(buffer.logs) == 1
        assert buffer.logs[-1].response_info.status_code == 401


class TestWhenTheRequestItselfCouldNotBeRead:
    def test_the_request_is_still_recorded(self, captured, monkeypatch):
        # `_make_request_info` runs before the route. If it raises, the name it
        # was to be bound to does not exist, and the block that follows fails on
        # that instead - losing the log and replacing the response.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise ValueError("the body could not be read")

        monkeypatch.setattr(log_requests_module, "_make_request_info", boom)

        response = client.post("/api/v1/echo", json={"a": 1})

        assert response.status_code == 200, "a failure reading the body changed the response"
        assert len(buffer.logs) == 1, "a failure reading the body cost the whole record"
        assert buffer.logs[-1].request_info.url.endswith("/api/v1/echo")
        assert buffer.logs[-1].request_info.method == "POST"


class TestAPartialRecordIsStillARecord:
    """Every field the record is assembled from can fail on its own."""

    def test_a_response_that_cannot_be_read_still_leaves_a_row(self, captured, monkeypatch):
        # `_make_response_info` re-reads the response body. If that raises, the
        # whole record used to be lost - caught by the outer guard, so the caller
        # was fine and the audit trail simply had nothing.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise RuntimeError("the response body will not re-read")

        monkeypatch.setattr(log_requests_module, "_make_response_info", boom)

        response = client.get("/api/v1/ok")

        assert response.status_code == 200
        assert len(buffer.logs) == 1, "a response that could not be read cost the whole record"
        logged = buffer.logs[-1]
        assert logged.request_info.url.endswith("/api/v1/ok"), "the request it recorded is not identifiable"
        assert logged.response_info.body == {"_capture_failed": True}

    def test_a_client_with_no_address_still_leaves_a_row(self, captured, monkeypatch):
        # An ASGI scope does not always carry a client, and reaching into it
        # unguarded is an AttributeError inside the assembly.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise AttributeError("'NoneType' object has no attribute 'host'")

        monkeypatch.setattr(log_requests_module, "_make_client_info", boom)

        response = client.get("/api/v1/ok")

        assert response.status_code == 200
        assert len(buffer.logs) == 1

    def test_a_failed_body_capture_says_so(self, captured, monkeypatch):
        # `body: None` cannot be told apart from a request that had no body, and
        # a reader of the audit trail has only what is written down.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise ValueError("the body could not be read")

        monkeypatch.setattr(log_requests_module, "_make_request_info", boom)

        client.post("/api/v1/echo", json={"a": 1})

        assert buffer.logs[-1].request_info.body == {"_capture_failed": True}
