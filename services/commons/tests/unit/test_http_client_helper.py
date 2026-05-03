# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.http_client_helper.

Uses respx to mock the HTTP layer so no real network traffic happens.
"""
from unittest.mock import patch

import httpx
import pytest
import respx

from kugel_common.utils.http_client_helper import (
    HttpClientError,
    HttpClientHelper,
    _get_service_url,
    close_all_clients,
    create_service_client,
    get_pooled_client,
    get_service_client,
)


# ---------------------------------------------------------------------------
# HttpClientError
# ---------------------------------------------------------------------------

class TestHttpClientError:
    def test_basic_construction(self):
        err = HttpClientError("boom")
        assert str(err) == "boom"
        assert err.status_code is None
        assert err.response is None

    def test_with_status_and_response(self):
        err = HttpClientError("404", status_code=404, response="not found")
        assert err.status_code == 404
        assert err.response == "not found"


# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------

class TestBuildUrl:
    @pytest.mark.asyncio
    async def test_with_base_url_and_relative(self):
        async with HttpClientHelper(base_url="http://api.example.com") as h:
            assert h._build_url("/users") == "http://api.example.com/users"

    @pytest.mark.asyncio
    async def test_with_base_url_no_leading_slash(self):
        async with HttpClientHelper(base_url="http://api.example.com") as h:
            assert h._build_url("users") == "http://api.example.com/users"

    @pytest.mark.asyncio
    async def test_full_url_passthrough(self):
        async with HttpClientHelper(base_url="http://api.example.com") as h:
            assert h._build_url("https://other.com/x") == "https://other.com/x"

    @pytest.mark.asyncio
    async def test_no_base_url(self):
        async with HttpClientHelper() as h:
            assert h._build_url("/users") == "users"

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_stripped(self):
        async with HttpClientHelper(base_url="http://api.example.com/") as h:
            assert h.base_url == "http://api.example.com"


# ---------------------------------------------------------------------------
# request methods (with respx mocking)
# ---------------------------------------------------------------------------

class TestHttpRequests:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_returns_json(self):
        respx.get("http://test.example.com/users").mock(
            return_value=httpx.Response(200, json={"users": [{"id": 1}]})
        )
        async with HttpClientHelper(base_url="http://test.example.com") as h:
            data = await h.get("/users")
        assert data == {"users": [{"id": 1}]}

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_with_json(self):
        respx.post("http://test.example.com/users").mock(
            return_value=httpx.Response(201, json={"id": 42})
        )
        async with HttpClientHelper(base_url="http://test.example.com") as h:
            data = await h.post("/users", json={"name": "alice"})
        assert data == {"id": 42}

    @pytest.mark.asyncio
    @respx.mock
    async def test_4xx_raises_http_client_error(self):
        respx.get("http://test.example.com/missing").mock(
            return_value=httpx.Response(404, json={"detail": "not found"})
        )
        async with HttpClientHelper(
            base_url="http://test.example.com",
            max_retries=1,
        ) as h:
            with pytest.raises(HttpClientError) as exc:
                await h.get("/missing")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_5xx_raises_http_client_error(self):
        respx.get("http://test.example.com/oops").mock(
            return_value=httpx.Response(500, json={"detail": "server error"})
        )
        async with HttpClientHelper(
            base_url="http://test.example.com",
            max_retries=1,
        ) as h:
            with pytest.raises(HttpClientError) as exc:
                await h.get("/oops")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_retries_and_raises(self):
        # Simulate timeout repeatedly
        respx.get("http://test.example.com/slow").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        async with HttpClientHelper(
            base_url="http://test.example.com",
            max_retries=2,
            retry_delay=0,
        ) as h:
            with pytest.raises(HttpClientError) as exc:
                await h.get("/slow")
        # message includes "timeout"
        assert "timeout" in exc.value.message.lower() or "Request timeout" in exc.value.message

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error_retries_and_raises(self):
        respx.get("http://test.example.com/conn").mock(
            side_effect=httpx.ConnectError("conn failed")
        )
        async with HttpClientHelper(
            base_url="http://test.example.com",
            max_retries=2,
            retry_delay=0,
        ) as h:
            with pytest.raises(HttpClientError):
                await h.get("/conn")

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_json_response_returned_as_text(self):
        respx.get("http://test.example.com/text").mock(
            return_value=httpx.Response(
                200,
                content=b"plain text response",
                headers={"content-type": "text/plain"},
            )
        )
        async with HttpClientHelper(base_url="http://test.example.com") as h:
            data, status = await h.request("GET", "/text")
        assert data == {"text": "plain text response"}
        assert status == 200

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_with_params(self):
        route = respx.get("http://test.example.com/items").mock(
            return_value=httpx.Response(200, json=[])
        )
        async with HttpClientHelper(base_url="http://test.example.com") as h:
            await h.get("/items", params={"page": 2, "size": 10})
        assert route.called
        # Confirm query string
        assert b"page=2" in route.calls[0].request.url.query
        assert b"size=10" in route.calls[0].request.url.query

    @pytest.mark.asyncio
    @respx.mock
    async def test_custom_headers_merge_with_defaults(self):
        route = respx.get("http://test.example.com/x").mock(
            return_value=httpx.Response(200, json={})
        )
        async with HttpClientHelper(base_url="http://test.example.com") as h:
            await h.get("/x", headers={"Authorization": "Bearer xyz"})
        assert route.called
        sent = route.calls[0].request.headers
        assert sent["Authorization"] == "Bearer xyz"
        assert sent["Content-Type"] == "application/json"  # default preserved


# ---------------------------------------------------------------------------
# Service client / pool
# ---------------------------------------------------------------------------

class TestServiceClient:
    def test_get_service_url_dash_uppercased(self):
        with patch(
            "kugel_common.utils.http_client_helper.settings",
            new=type(
                "S",
                (),
                {"BASE_URL_MASTER_DATA": "http://master:8002", "OTHER": "x"},
            )(),
        ):
            assert _get_service_url("master-data") == "http://master:8002"

    def test_get_service_url_unknown_returns_none(self):
        # No BASE_URL_* attrs that match
        with patch(
            "kugel_common.utils.http_client_helper.settings",
            new=type("S", (), {"BASE_URL_KNOWN": "x"})(),
        ):
            assert _get_service_url("unknown-service") is None

    @pytest.mark.asyncio
    async def test_create_service_client_uses_lookup(self):
        with patch(
            "kugel_common.utils.http_client_helper.settings",
            new=type("S", (), {"BASE_URL_TERMINAL": "http://terminal:8001"})(),
        ):
            client = create_service_client("terminal")
            assert client.base_url == "http://terminal:8001"
            await client.close()

    @pytest.mark.asyncio
    async def test_get_pooled_client_returns_same_instance(self):
        # Pooled clients are global; clear pool first
        await close_all_clients()
        with patch(
            "kugel_common.utils.http_client_helper.settings",
            new=type("S", (), {"BASE_URL_REPORT": "http://report:8004"})(),
        ):
            c1 = await get_pooled_client("report")
            c2 = await get_pooled_client("report")
            assert c1 is c2
        await close_all_clients()

    @pytest.mark.asyncio
    async def test_close_all_clients_clears_pool(self):
        await close_all_clients()
        with patch(
            "kugel_common.utils.http_client_helper.settings",
            new=type("S", (), {"BASE_URL_X": "http://x"})(),
        ):
            await get_pooled_client("x")
            await close_all_clients()
            # After close_all, a fresh pool entry is created
            new_client = await get_pooled_client("x")
            assert new_client is not None
        await close_all_clients()

    @pytest.mark.asyncio
    async def test_get_service_client_context_manager(self):
        with patch(
            "kugel_common.utils.http_client_helper.settings",
            new=type("S", (), {"BASE_URL_JOURNAL": "http://journal:8005"})(),
        ):
            async with get_service_client("journal") as client:
                assert client.base_url == "http://journal:8005"
            # Client is closed after exiting the context
            assert client._closed is True
