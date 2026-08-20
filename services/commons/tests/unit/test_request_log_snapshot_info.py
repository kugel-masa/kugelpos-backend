# Copyright 2026 masa@kugel
"""Snapshot marks reach the request log (issue #165).

Middleware that peels a client-carried envelope runs outside the logging one, so
the envelope is gone by the time the request is logged - and the body it would
otherwise be read from is stripped on purpose (issue #155). A service leaves the
scalars on the request scope instead; this is the pickup.
"""

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from kugel_common.middleware import log_requests as log_requests_module
from kugel_common.middleware.log_requests import SNAPSHOT_SCOPE_KEY, log_requests


class _CapturingBuffer:
    def __init__(self):
        self.logs = []

    async def add(self, request_log):
        self.logs.append(request_log)


@pytest.fixture
def captured(monkeypatch):
    buffer = _CapturingBuffer()
    monkeypatch.setattr(log_requests_module, "get_request_log_buffer", lambda: buffer)
    return buffer


def _app(marks):
    """An app whose inner middleware leaves `marks` on the scope, as the peel does."""
    app = FastAPI()
    app.middleware("http")(log_requests("test-service"))

    @app.middleware("http")
    async def _leave_marks(request: Request, call_next):
        if marks is not None:
            request.scope[SNAPSHOT_SCOPE_KEY] = marks
        return await call_next(request)

    @app.post("/carts/1/lineItems")
    async def add_item(body: dict):
        return {"ok": True}

    return app


def _post(app):
    return TestClient(app).post("/carts/1/lineItems", json={"quantity": 1})


class TestRecording:
    def test_the_revision_reaches_the_log(self, captured):
        _post(_app({"cart_id": "cart-165", "revision": 8, "schema_version": 2, "kid": "v1"}))

        info = captured.logs[0].snapshot_info
        assert info.cart_id == "cart-165"
        assert info.revision == 8
        assert info.schema_version == 2
        assert info.kid == "v1"

    def test_a_request_carrying_nothing_records_nothing(self, captured):
        _post(_app(None))

        assert captured.logs[0].snapshot_info is None

    def test_a_version_1_envelope_records_what_it_has(self, captured):
        _post(_app({"cart_id": "cart-165", "revision": None, "schema_version": 1, "kid": "v1"}))

        info = captured.logs[0].snapshot_info
        assert info.revision is None
        assert info.schema_version == 1

    def test_the_marks_are_not_in_the_logged_body(self, captured):
        # They are a field of their own precisely because the body is stripped.
        _post(_app({"cart_id": "cart-165", "revision": 8, "schema_version": 2, "kid": "v1"}))

        body = json.dumps(captured.logs[0].request_info.body or {})
        assert "cart-165" not in body
        assert captured.logs[0].snapshot_info.cart_id == "cart-165"


class TestBadInput:
    def test_a_non_dict_on_the_scope_is_ignored(self, captured):
        _post(_app("not-a-dict"))

        assert captured.logs[0].snapshot_info is None

    def test_an_unusable_value_costs_only_the_marks(self, captured):
        # The request log itself must still be written.
        _post(_app({"cart_id": "cart-165", "revision": {"nested": "value"}}))

        assert captured.logs[0] is not None
        assert captured.logs[0].snapshot_info is None
