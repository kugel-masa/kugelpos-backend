# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.middleware.http_compression."""
import gzip
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kugel_common.middleware.http_compression import (
    GZIP_MINIMUM_SIZE_BYTES,
    add_gzip_response_middleware,
)


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/large")
    async def large():
        return {"data": "x" * (GZIP_MINIMUM_SIZE_BYTES * 4)}

    @app.get("/small")
    async def small():
        return {"data": "x"}

    add_gzip_response_middleware(app)
    return app


class TestAddGzipResponseMiddleware:
    def test_compresses_large_response_when_client_accepts_gzip(self):
        client = TestClient(_build_app())
        response = client.get("/large", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"
        # httpx transparently decompresses; the payload must round-trip intact
        assert response.json()["data"] == "x" * (GZIP_MINIMUM_SIZE_BYTES * 4)

    def test_skips_small_response(self):
        client = TestClient(_build_app())
        response = client.get("/small", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        assert "content-encoding" not in response.headers

    def test_no_compression_without_accept_encoding(self):
        client = TestClient(_build_app())
        response = client.get("/large", headers={"Accept-Encoding": "identity"})
        assert response.status_code == 200
        assert "content-encoding" not in response.headers
        assert response.json()["data"] == "x" * (GZIP_MINIMUM_SIZE_BYTES * 4)

    def test_compressed_body_is_valid_gzip(self):
        # Bypass httpx auto-decompression to verify the raw bytes on the wire
        app = _build_app()
        client = TestClient(app)
        with client.stream("GET", "/large", headers={"Accept-Encoding": "gzip"}) as response:
            raw = b"".join(response.iter_raw())
        body = json.loads(gzip.decompress(raw))
        assert body["data"] == "x" * (GZIP_MINIMUM_SIZE_BYTES * 4)
