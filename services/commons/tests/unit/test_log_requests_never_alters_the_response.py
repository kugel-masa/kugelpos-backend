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
        assert logged.response_info.body == {"_assembly_failed": True}

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

    def test_the_fallback_keeps_the_tenant_it_had_already_resolved(self, captured, monkeypatch):
        """Dropping the tenant is not a cosmetic loss.

        The buffer routes by it, so a record without one never reaches the
        tenant's own database — and a row with no tenant reads as an
        unauthenticated request, which is a different thing entirely. It was
        resolved before the field that failed, so there is no reason to lose it.
        """
        buffer, client = captured

        async def resolved(*args, **kwargs):
            return {"tenant_id": "T6216", "username": "admin", "is_superuser": True, "is_service_account": False}

        async def boom(*args, **kwargs):
            raise RuntimeError("the response body will not re-read")

        monkeypatch.setattr(log_requests_module, "_get_current_user", resolved)
        monkeypatch.setattr(log_requests_module, "_make_response_info", boom)

        client.get("/api/v1/ok")

        assert buffer.logs[-1].tenant_id == "T6216", "the fallback discarded a tenant it already had"

    def test_a_request_with_no_client_address_is_recorded(self, captured, monkeypatch):
        # An ASGI scope does not always carry a client, and the guard for that is
        # inside _make_client_info rather than around it.
        buffer, client = captured
        real = log_requests_module.RequestLog

        class _NoClient:
            client = None
            method = "GET"
            url = "http://testserver/api/v1/ok"
            headers = {}
            scope = {}

        info = pytest.importorskip("asyncio").run(log_requests_module._make_client_info(_NoClient()))

        assert info.ip_address == "", "a scope without a client raised instead of recording"
        assert isinstance(info, real.ClientInfo)


class TestTheLoggerCannotBecomeTheFailure:
    def test_a_log_handler_that_raises_does_not_reach_the_caller(self, captured, monkeypatch):
        """`logger.error` is not free of risk on these paths.

        A handler that raises — a full disk, a custom handler — propagates, and
        these calls sit inside guards whose whole purpose is that nothing on
        them reaches the caller. A report that becomes the failure it was
        reporting is the same defect one level down.
        """
        import logging

        buffer, client = captured

        async def boom(*args, **kwargs):
            raise RuntimeError("the buffer is unavailable")

        monkeypatch.setattr(log_requests_module, "get_request_log_buffer", lambda: type("B", (), {"add": boom})())

        class _FailingHandler(logging.Handler):
            def emit(self, record):
                raise OSError("no space left on device")

        handler = _FailingHandler()
        log_requests_module.logger.addHandler(handler)
        try:
            response = client.get("/api/v1/ok")
        finally:
            log_requests_module.logger.removeHandler(handler)

        assert response.status_code == 200, "reporting the failure became the failure"


class TestTheRecordSaysWhichServiceAnsweredIt:
    def test_the_service_name_is_kept(self, captured):
        # Every service writes to the same commons collection. The middleware has
        # always passed this and the model never declared it, so Pydantic dropped
        # it and a reader could not tell cart from journal.
        buffer, client = captured

        client.get("/api/v1/ok")

        assert buffer.logs[-1].service_name == "test-service"
        assert "service_name" in buffer.logs[-1].model_dump(), "it is not persisted"

    def test_the_fallback_record_says_so_too(self, captured, monkeypatch):
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise RuntimeError("the response body will not re-read")

        monkeypatch.setattr(log_requests_module, "_make_response_info", boom)

        client.get("/api/v1/ok")

        assert buffer.logs[-1].service_name == "test-service"


class TestResolvingTheContextIsPartOfTheAssembly:
    def test_a_failure_resolving_the_terminal_still_leaves_a_record(self, captured, monkeypatch):
        # These used to run before the assembly guard, so an unexpected failure
        # there aborted the whole function - no record at all.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise AttributeError("'NoneType' object has no attribute 'headers'")

        monkeypatch.setattr(log_requests_module, "_get_terminal_info", boom)

        response = client.get("/api/v1/ok")

        assert response.status_code == 200
        assert len(buffer.logs) == 1, "a failure resolving the terminal cost the whole record"
        assert buffer.logs[-1].request_info.url.endswith("/api/v1/ok")

    def test_a_failure_writing_the_file_log_still_reaches_the_database(self, captured, monkeypatch):
        # The file copy is local and the database copy is the one that is
        # queried; a disk problem should not cost the second.
        buffer, client = captured

        async def boom(*args, **kwargs):
            raise OSError("no space left on device")

        monkeypatch.setattr(log_requests_module, "_output_request_log_to_file", boom)

        response = client.get("/api/v1/ok")

        assert response.status_code == 200
        assert len(buffer.logs) == 1, "a file-log failure cost the database record"
