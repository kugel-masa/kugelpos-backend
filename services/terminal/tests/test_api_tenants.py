"""
Unit tests for tenant API endpoints.

Tests the request/response flow through the tenant router using
httpx.AsyncClient + ASGITransport with mocked service layer.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, HTTPException, status

from app.api.v1.tenant import router
from app.dependencies.get_tenant_service import (
    get_tenant_id_with_token_wrapper,
    get_tenant_id_with_security_by_query_optional_wrapper,
    parse_sort_stores as parse_sort,
)
from kugel_common.security import oauth2_scheme
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo


TENANT_ID = "T001"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def _make_store_info(**overrides) -> StoreInfo:
    defaults = dict(
        store_code="S001",
        store_name="Main Store",
        status="Active",
        business_date="20250101",
        tags=["retail"],
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return StoreInfo(**defaults)


def _make_tenant_doc(**overrides) -> TenantInfoDocument:
    defaults = dict(
        tenant_id=TENANT_ID,
        tenant_name="Test Tenant",
        stores=[_make_store_info()],
        tags=["test"],
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return TenantInfoDocument(**defaults)


def make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    # Override auth dependencies
    app.dependency_overrides[get_tenant_id_with_token_wrapper] = lambda: TENANT_ID
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional_wrapper] = lambda: TENANT_ID
    app.dependency_overrides[oauth2_scheme] = lambda: "fake-token"
    app.dependency_overrides[parse_sort] = lambda: [("store_code", 1)]
    return app


# ---------------------------------------------------------------------------
# POST /tenants  (create)
# ---------------------------------------------------------------------------
class TestCreateTenant:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.create_tenant_async.return_value = _make_tenant_doc(stores=[])

        with (
            patch("app.api.v1.tenant.database_setup") as mock_db_setup,
            patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service),
            patch("app.api.v1.tenant.httpx.AsyncClient") as mock_httpx,
        ):
            mock_db_setup.execute = AsyncMock()
            # Mock httpx.AsyncClient context manager
            mock_client_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/tenants",
                    json={"tenant_id": TENANT_ID, "tenant_name": "Test Tenant", "tags": ["test"]},
                )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["tenantId"] == TENANT_ID

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants",
                json={"tenant_id": "WRONG", "tenant_name": "Test", "tags": []},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /tenants/{tenant_id}
# ---------------------------------------------------------------------------
class TestGetTenant:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_tenant_async.return_value = _make_tenant_doc()

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/tenants/{TENANT_ID}")
        assert resp.status_code == 200
        assert resp.json()["data"]["tenantId"] == TENANT_ID

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/tenants/WRONG")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_tenant_async.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/tenants/{TENANT_ID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /tenants/{tenant_id}
# ---------------------------------------------------------------------------
class TestUpdateTenant:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_tenant_async.return_value = _make_tenant_doc(tenant_name="Updated")

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/v1/tenants/{TENANT_ID}",
                    json={"tenant_name": "Updated", "tags": ["test"]},
                )
        assert resp.status_code == 200
        assert resp.json()["data"]["tenantName"] == "Updated"

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/tenants/WRONG",
                json={"tenant_name": "Updated", "tags": []},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /tenants/{tenant_id}
# ---------------------------------------------------------------------------
class TestDeleteTenant:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.delete_tenant_async.return_value = None

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}")
        assert resp.status_code == 200
        assert resp.json()["data"]["tenantId"] == TENANT_ID

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/v1/tenants/WRONG")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.delete_tenant_async.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /tenants/{tenant_id}/stores  (add store)
# ---------------------------------------------------------------------------
class TestAddStore:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.add_store_async.return_value = _make_tenant_doc()

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/tenants/{TENANT_ID}/stores",
                    json={"store_code": "S001", "store_name": "Main Store"},
                )
        assert resp.status_code == 201
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/WRONG/stores",
                json={"store_code": "S001", "store_name": "Main Store"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.add_store_async.side_effect = HTTPException(
            status_code=400, detail="Duplicate store"
        )

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/tenants/{TENANT_ID}/stores",
                    json={"store_code": "S001", "store_name": "Main Store"},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /tenants/{tenant_id}/stores  (list stores)
# ---------------------------------------------------------------------------
class TestGetStores:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_stores_async.return_value = [_make_store_info()]

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/stores")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/tenants/WRONG/stores")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /tenants/{tenant_id}/stores/{store_code}  (get store)
# ---------------------------------------------------------------------------
class TestGetStore:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_store_async.return_value = _make_store_info()

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/stores/S001")
        assert resp.status_code == 200
        assert resp.json()["data"]["storeCode"] == "S001"

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/tenants/WRONG/stores/S001")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_store_async.side_effect = HTTPException(
            status_code=404, detail="Store not found"
        )

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/stores/S999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /tenants/{tenant_id}/stores/{store_code}  (update store)
# ---------------------------------------------------------------------------
class TestUpdateStore:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_store_async.return_value = _make_store_info(store_name="Updated Store")

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/v1/tenants/{TENANT_ID}/stores/S001",
                    json={"store_name": "Updated Store"},
                )
        assert resp.status_code == 200
        assert resp.json()["data"]["storeName"] == "Updated Store"

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/tenants/WRONG/stores/S001",
                json={"store_name": "Updated Store"},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /tenants/{tenant_id}/stores/{store_code}  (delete store)
# ---------------------------------------------------------------------------
class TestDeleteStore:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.delete_store_async.return_value = None

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/stores/S001")
        assert resp.status_code == 200
        assert resp.json()["data"]["storeCode"] == "S001"

    @pytest.mark.asyncio
    async def test_tenant_id_mismatch(self):
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/v1/tenants/WRONG/stores/S001")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.delete_store_async.side_effect = HTTPException(
            status_code=404, detail="Store not found"
        )

        with patch("app.api.v1.tenant.get_tenant_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/stores/S001")
        assert resp.status_code == 404
