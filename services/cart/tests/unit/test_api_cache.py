"""Unit tests for cache API endpoints (app/api/v1/cache.py).

Covers the master-data cache invalidation endpoint:
- superuser / service account may bump a namespace generation
- a regular authenticated user is forbidden (403)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_current_user
from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend
from app.api.v1.cache import router as cache_router


def _make_app(backend) -> FastAPI:
    app = FastAPI()
    app.include_router(cache_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.state.master_cache_backend = backend
    return app


SUPERUSER = {"tenant_id": "tenant1", "username": "admin", "is_superuser": True, "is_service_account": False}
SERVICE = {"tenant_id": "tenant1", "username": "svc", "is_superuser": False, "is_service_account": True}
REGULAR = {"tenant_id": "tenant1", "username": "term", "is_superuser": False, "is_service_account": False}


@pytest.mark.asyncio
async def test_invalidate_master_data_cache_superuser_bumps_generation():
    backend = InMemoryCacheBackend()
    app = _make_app(backend)
    app.dependency_overrides[get_current_user] = lambda: SUPERUSER

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            "/api/v1/cache/master-data",
            params={"namespace": "promotion_master", "store_code": "S1"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["cache_type"] == "master_data"
    assert body["data"]["namespace"] == "promotion_master"
    assert body["data"]["store_code"] == "S1"
    assert body["data"]["new_generation"] == 1


@pytest.mark.asyncio
async def test_invalidate_master_data_cache_service_account_allowed():
    backend = InMemoryCacheBackend()
    app = _make_app(backend)
    app.dependency_overrides[get_current_user] = lambda: SERVICE

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            "/api/v1/cache/master-data",
            params={"namespace": "item_master"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["new_generation"] == 1


@pytest.mark.asyncio
async def test_invalidate_master_data_cache_regular_user_forbidden():
    backend = InMemoryCacheBackend()
    app = _make_app(backend)
    app.dependency_overrides[get_current_user] = lambda: REGULAR

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            "/api/v1/cache/master-data",
            params={"namespace": "promotion_master"},
        )

    assert resp.status_code == 403
