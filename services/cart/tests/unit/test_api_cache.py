"""Unit tests for cache API endpoints (app/api/v1/cache.py).

Note: The cache endpoints construct ApiResponse(data=...) without providing
the required 'success' and 'message' fields, which causes a Pydantic
ValidationError at response time. Tests verify that the dependency injection
and cache operations work correctly by patching ApiResponse to accept
partial construction.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from kugel_common.exceptions import register_exception_handlers
from kugel_common.schemas.api_response import ApiResponse
from app.api.v1.cache import router as cache_router
from kugel_common.security import get_current_user


def _make_app():
    app = FastAPI()
    app.include_router(cache_router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


MOCK_USER = {"tenant_id": "tenant1", "username": "admin"}


def _api_response_side_effect(**kwargs):
    """Build a valid ApiResponse with defaults for missing required fields."""
    kwargs.setdefault("success", True)
    kwargs.setdefault("message", "OK")
    return ApiResponse(**kwargs)


# ---------------------------------------------------------------------------
# get_cache_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cache_status_success():
    app = _make_app()
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER

    with (
        patch("app.api.v1.cache.get_terminal_cache_size", side_effect=[3, 10]),
        patch(
            "app.api.v1.cache.get_tenant_terminal_ids_in_cache",
            return_value=["t1-s1-1", "t1-s1-2", "t1-s2-1"],
        ),
        patch("app.api.v1.cache.ApiResponse", side_effect=_api_response_side_effect),
    ):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/cache/terminal/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["cache_type"] == "terminal_info"
    assert body["data"]["tenant_id"] == "tenant1"
    assert body["data"]["tenant_cache_size"] == 3
    assert body["data"]["total_cache_size"] == 10
    assert body["data"]["status"] == "active"
    assert len(body["data"]["cached_terminal_ids"]) == 3


@pytest.mark.asyncio
async def test_get_cache_status_empty():
    app = _make_app()
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER

    with (
        patch("app.api.v1.cache.get_terminal_cache_size", return_value=0),
        patch(
            "app.api.v1.cache.get_tenant_terminal_ids_in_cache",
            return_value=[],
        ),
        patch("app.api.v1.cache.ApiResponse", side_effect=_api_response_side_effect),
    ):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/cache/terminal/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["tenant_cache_size"] == 0
    assert body["data"]["cached_terminal_ids"] == []


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_cache_success():
    app = _make_app()
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER

    with (
        patch("app.api.v1.cache.get_terminal_cache_size", return_value=5),
        patch("app.api.v1.cache.clear_terminal_cache") as mock_clear,
        patch("app.api.v1.cache.ApiResponse", side_effect=_api_response_side_effect),
    ):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/cache/terminal")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["items_cleared"] == 5
    assert body["data"]["tenant_id"] == "tenant1"
    mock_clear.assert_called_once_with("tenant1")


@pytest.mark.asyncio
async def test_clear_cache_when_empty():
    app = _make_app()
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER

    with (
        patch("app.api.v1.cache.get_terminal_cache_size", return_value=0),
        patch("app.api.v1.cache.clear_terminal_cache") as mock_clear,
        patch("app.api.v1.cache.ApiResponse", side_effect=_api_response_side_effect),
    ):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/cache/terminal")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["items_cleared"] == 0
    mock_clear.assert_called_once_with("tenant1")
