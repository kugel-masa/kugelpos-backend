# Copyright 2026 masa@kugel
"""Middleware-level tests for the request-log body budget (issue #155).

Proves the wiring: what the middleware hands to the log file and to the
`request_log` buffer is the sanitized body, on both the request and the
response side.
"""

import json

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from kugel_common.middleware import log_requests as log_requests_module
from kugel_common.middleware.log_requests import log_requests


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

    @app.post("/echo")
    async def echo(body: dict):
        return {"data": {"cartId": "cart-1", "signedSnapshot": _envelope()}}

    return app


def _envelope() -> dict:
    return {
        "schema_version": 1,
        "issued_at": "2026-08-20T10:00:00",
        "kid": "v1",
        "tenant_id": "A1234",
        "store_code": "5678",
        "terminal_no": 9,
        "cart_document": {"cart_id": "cart-1", "line_items": [{"description": "x" * 512}] * 40},
        "signature": "a" * 64,
    }


class TestSnapshotStripping:
    def test_response_snapshot_is_stripped_from_the_log(self, captured):
        client = TestClient(_build_app())
        response = client.post("/echo", json={"quantity": 1})

        assert response.status_code == 200
        # The client still receives the full snapshot...
        assert "cart_document" in response.json()["data"]["signedSnapshot"]
        # ...while the log keeps only its metadata.
        logged = captured.logs[0].response_info.body["data"]["signedSnapshot"]
        assert logged["_stripped"] == "signedSnapshot"
        assert logged["kid"] == "v1"
        assert "cart_document" not in logged

    def test_request_snapshot_is_stripped_from_the_log(self, captured):
        client = TestClient(_build_app())
        client.post("/echo", json={"quantity": 1, "signedSnapshot": _envelope()})

        logged = captured.logs[0].request_info.body["signedSnapshot"]
        assert logged["_stripped"] == "signedSnapshot"
        assert "cart_document" not in logged

    def test_logged_document_stays_small(self, captured):
        client = TestClient(_build_app())
        client.post("/echo", json={"quantity": 1, "signedSnapshot": _envelope()})

        request_log = captured.logs[0]
        logged_bytes = len(json.dumps(request_log.model_dump(), default=str))
        assert logged_bytes < 2048

    def test_ordinary_body_is_logged_verbatim(self, captured):
        client = TestClient(_build_app())
        client.post("/echo", json={"quantity": 2, "itemCode": "49-1"})

        assert captured.logs[0].request_info.body == {"quantity": 2, "itemCode": "49-1"}


class TestTruncationBackstop:
    def test_oversized_body_is_truncated(self, captured, monkeypatch):
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_MAX_BODY_BYTES", 1024)
        client = TestClient(_build_app())
        client.post("/echo", json={"blob": "x" * 50_000})

        body = captured.logs[0].request_info.body
        assert body["_truncated"] is True
        assert body["_encoded_bytes"] > 50_000

    def test_response_body_is_still_delivered_intact(self, captured, monkeypatch):
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_MAX_BODY_BYTES", 16)
        client = TestClient(_build_app())
        response = client.post("/echo", json={"quantity": 1})

        assert response.json()["data"]["cartId"] == "cart-1"
        assert captured.logs[0].response_info.body["_truncated"] is True


class TestSettingsDriven:
    def test_strip_fields_setting_is_honoured(self, captured, monkeypatch):
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_STRIP_FIELDS", "blob")
        client = TestClient(_build_app())
        client.post("/echo", json={"blob": {"big": "x" * 1000}, "signedSnapshot": _envelope()})

        body = captured.logs[0].request_info.body
        assert body["blob"] == {"_stripped": "blob"}
        # No longer configured, so the snapshot is now kept.
        assert "cart_document" in body["signedSnapshot"]

    def test_empty_strip_fields_setting_disables_stripping(self, captured, monkeypatch):
        monkeypatch.setattr(log_requests_module.settings, "REQUEST_LOG_STRIP_FIELDS", "")
        client = TestClient(_build_app())
        client.post("/echo", json={"quantity": 1})

        assert "cart_document" in captured.logs[0].response_info.body["data"]["signedSnapshot"]


class TestOtherRequestShapes:
    def test_body_less_get_is_logged_with_a_null_body(self, captured):
        app = FastAPI()
        app.middleware("http")(log_requests("test-service"))

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        TestClient(app).get("/ping")
        assert captured.logs[0].request_info.body is None
        assert captured.logs[0].response_info.body == {"ok": True}

    def test_non_json_request_body_is_logged_with_a_null_body(self, captured):
        app = FastAPI()
        app.middleware("http")(log_requests("test-service"))

        @app.post("/raw")
        async def raw(request: Request):
            await request.body()
            return {"ok": True}

        TestClient(app).post("/raw", content=b"\x00\x01not-json", headers={"Content-Type": "application/octet-stream"})
        assert captured.logs[0].request_info.body is None

    def test_top_level_list_response_is_stripped_and_stays_a_list(self, captured):
        app = FastAPI()
        app.middleware("http")(log_requests("test-service"))

        @app.get("/carts")
        async def carts():
            return [{"cartId": "c1", "signedSnapshot": _envelope()}]

        TestClient(app).get("/carts")
        logged = captured.logs[0].response_info.body
        assert isinstance(logged, list)
        assert logged[0]["signedSnapshot"]["_stripped"] == "signedSnapshot"

    def test_error_response_body_is_logged(self, captured):
        app = FastAPI()
        app.middleware("http")(log_requests("test-service"))

        @app.get("/boom")
        async def boom():
            raise HTTPException(status_code=404, detail="nope")

        TestClient(app).get("/boom")
        assert captured.logs[0].response_info.status_code == 404
        assert captured.logs[0].response_info.body == {"detail": "nope"}


class TestFileSink:
    def test_the_log_file_receives_the_sanitized_body(self, captured, caplog):
        # The issue names both sinks; the file line must not carry the snapshot.
        with caplog.at_level("INFO", logger="requestLogger"):
            TestClient(_build_app()).post("/echo", json={"quantity": 1})

        line = "\n".join(r.getMessage() for r in caplog.records)
        assert "_stripped" in line
        assert "cart_document" not in line
