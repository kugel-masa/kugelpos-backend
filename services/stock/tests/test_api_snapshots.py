"""
Unit tests for snapshot API endpoints.
Tests use FastAPI dependency overrides with mock services.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request

from app.api.v1.stock import router
from app.dependencies.get_stock_service import get_stock_service, get_snapshot_service
from app.models.documents import StockSnapshotDocument, StockSnapshotItem
from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.exceptions import register_exception_handlers


# -- helpers --

NOW = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
TENANT = "test_tenant"
STORE = "store01"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


def _snapshot_doc(**overrides) -> StockSnapshotDocument:
    defaults = dict(
        tenant_id=TENANT,
        store_code=STORE,
        total_items=2,
        total_quantity=150.0,
        stocks=[
            StockSnapshotItem(
                item_code="ITEM001",
                quantity=100.0,
                minimum_quantity=10.0,
                reorder_point=20.0,
                reorder_quantity=50.0,
            ),
            StockSnapshotItem(
                item_code="ITEM002",
                quantity=50.0,
                minimum_quantity=5.0,
                reorder_point=10.0,
                reorder_quantity=30.0,
            ),
        ],
        created_by="system",
        created_at=NOW,
        updated_at=NOW,
        generate_date_time="2025-01-15T10:00:00Z",
    )
    defaults.update(overrides)
    return StockSnapshotDocument(**defaults)


def _schedule_doc(**overrides) -> SnapshotScheduleDocument:
    defaults = dict(
        tenant_id=TENANT,
        enabled=True,
        schedule_interval="daily",
        schedule_hour=3,
        schedule_minute=0,
        retention_days=30,
        target_stores=["all"],
        created_at=NOW,
        updated_at=NOW,
        created_by="system",
        updated_by="system",
    )
    defaults.update(overrides)
    return SnapshotScheduleDocument(**defaults)


# -- fixtures --

@pytest.fixture
def mock_stock_service():
    return AsyncMock()


@pytest.fixture
def mock_snapshot_service():
    return AsyncMock()


@pytest.fixture
def app(mock_stock_service, mock_snapshot_service):
    app = _make_app()

    async def override_security():
        return TENANT

    async def override_stock_service(request: Request, tenant_id: str):
        return mock_stock_service

    async def override_snapshot_service(request: Request, tenant_id: str):
        return mock_snapshot_service

    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = override_security
    app.dependency_overrides[get_stock_service] = override_stock_service
    app.dependency_overrides[get_snapshot_service] = override_snapshot_service
    return app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ===== create_snapshot =====

@pytest.mark.asyncio
async def test_create_snapshot_success(client, mock_snapshot_service):
    mock_snapshot_service.create_snapshot_async.return_value = _snapshot_doc()

    resp = await client.post(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshot")
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["totalItems"] == 2


@pytest.mark.asyncio
async def test_create_snapshot_with_terminal_id(client, mock_snapshot_service):
    """When terminal_id is provided and created_by is default 'system', terminal_id is used."""
    mock_snapshot_service.create_snapshot_async.return_value = _snapshot_doc(created_by="term01")

    resp = await client.post(
        f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshot?terminal_id=term01"
    )
    assert resp.status_code == 201
    # Verify create_snapshot_async was called with terminal_id as created_by
    mock_snapshot_service.create_snapshot_async.assert_called_once_with(TENANT, STORE, "term01")


# ===== get_snapshots_by_date_range =====

@pytest.mark.asyncio
async def test_get_snapshots_success(client, mock_snapshot_service):
    snapshots = [_snapshot_doc(), _snapshot_doc(generate_date_time="2025-01-14T10:00:00Z")]
    mock_snapshot_service.get_snapshots_by_generate_date_time_async.return_value = (snapshots, 2)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshots")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["metadata"]["total"] == 2
    assert len(body["data"]["data"]) == 2


@pytest.mark.asyncio
async def test_get_snapshots_with_date_filter(client, mock_snapshot_service):
    mock_snapshot_service.get_snapshots_by_generate_date_time_async.return_value = ([_snapshot_doc()], 1)

    resp = await client.get(
        f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshots"
        "?start_date=2025-01-01&end_date=2025-01-31"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["metadata"]["total"] == 1
    assert body["data"]["metadata"]["filter"]["start_date"] == "2025-01-01"


@pytest.mark.asyncio
async def test_get_snapshots_empty(client, mock_snapshot_service):
    mock_snapshot_service.get_snapshots_by_generate_date_time_async.return_value = ([], 0)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshots")
    assert resp.status_code == 200
    assert resp.json()["data"]["data"] == []


# ===== get_snapshot_by_id =====

@pytest.mark.asyncio
async def test_get_snapshot_by_id_success(client, mock_snapshot_service):
    mock_snapshot_service.get_snapshot_by_id_async.return_value = _snapshot_doc()

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshot/snap_001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["totalItems"] == 2


@pytest.mark.asyncio
async def test_get_snapshot_by_id_not_found(client, mock_snapshot_service):
    mock_snapshot_service.get_snapshot_by_id_async.return_value = None

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/snapshot/nonexistent")
    assert resp.status_code == 404


# ===== get_snapshot_schedule =====

@pytest.mark.asyncio
async def test_get_snapshot_schedule_existing(client):
    """When a schedule exists in DB, return it."""
    mock_repo = AsyncMock()
    mock_repo.get_by_tenant_id.return_value = _schedule_doc()

    with (
        patch("kugel_common.database.database") as mock_db,
        patch("app.repositories.snapshot_schedule_repository.SnapshotScheduleRepository", return_value=mock_repo),
        patch("app.config.settings.settings") as mock_settings,
    ):
        mock_settings.DB_NAME_PREFIX = "db_stock"
        mock_db.get_db_async = AsyncMock(return_value=MagicMock())

        resp = await client.get(f"/api/v1/tenants/{TENANT}/stock/snapshot-schedule")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["schedule_interval"] == "daily"


@pytest.mark.asyncio
async def test_get_snapshot_schedule_default(client):
    """When no schedule exists, return default schedule."""
    mock_repo = AsyncMock()
    mock_repo.get_by_tenant_id.return_value = None

    with (
        patch("kugel_common.database.database") as mock_db,
        patch("app.repositories.snapshot_schedule_repository.SnapshotScheduleRepository", return_value=mock_repo),
        patch("app.config.settings.settings") as mock_settings,
    ):
        mock_settings.DB_NAME_PREFIX = "db_stock"
        mock_settings.DEFAULT_SNAPSHOT_ENABLED = True
        mock_settings.DEFAULT_SNAPSHOT_INTERVAL = "daily"
        mock_settings.DEFAULT_SNAPSHOT_HOUR = 3
        mock_settings.DEFAULT_SNAPSHOT_MINUTE = 0
        mock_settings.DEFAULT_SNAPSHOT_RETENTION_DAYS = 30
        mock_db.get_db_async = AsyncMock(return_value=MagicMock())

        resp = await client.get(f"/api/v1/tenants/{TENANT}/stock/snapshot-schedule")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["enabled"] is True


# ===== update_snapshot_schedule =====

@pytest.mark.asyncio
async def test_update_snapshot_schedule_success(client):
    saved = _schedule_doc(schedule_hour=5)
    mock_repo = AsyncMock()
    mock_repo.upsert_schedule.return_value = saved

    mock_scheduler = AsyncMock()

    with (
        patch("kugel_common.database.database") as mock_db,
        patch("app.repositories.snapshot_schedule_repository.SnapshotScheduleRepository", return_value=mock_repo),
        patch("app.config.settings.settings") as mock_settings,
        patch("app.dependencies.get_scheduler.get_scheduler", return_value=mock_scheduler),
    ):
        mock_settings.DB_NAME_PREFIX = "db_stock"
        mock_settings.MIN_SNAPSHOT_RETENTION_DAYS = 1
        mock_settings.MAX_SNAPSHOT_RETENTION_DAYS = 365
        mock_db.get_db_async = AsyncMock(return_value=MagicMock())

        payload = {
            "enabled": True,
            "schedule_interval": "daily",
            "schedule_hour": 5,
            "schedule_minute": 30,
            "retention_days": 30,
            "target_stores": ["all"],
        }
        resp = await client.put(
            f"/api/v1/tenants/{TENANT}/stock/snapshot-schedule",
            json=payload,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_update_snapshot_schedule_weekly_missing_day(client):
    """Weekly schedule without schedule_day_of_week should raise ValueError."""
    with (
        patch("app.config.settings.settings") as mock_settings,
    ):
        mock_settings.DB_NAME_PREFIX = "db_stock"
        mock_settings.MIN_SNAPSHOT_RETENTION_DAYS = 1
        mock_settings.MAX_SNAPSHOT_RETENTION_DAYS = 365

        payload = {
            "enabled": True,
            "schedule_interval": "weekly",
            "schedule_hour": 5,
            "schedule_minute": 0,
            "retention_days": 30,
            "target_stores": ["all"],
        }
        with pytest.raises(ValueError, match="schedule_day_of_week is required"):
            await client.put(
                f"/api/v1/tenants/{TENANT}/stock/snapshot-schedule",
                json=payload,
            )


# ===== delete_snapshot_schedule =====

@pytest.mark.asyncio
async def test_delete_snapshot_schedule_existing(client):
    mock_repo = AsyncMock()
    mock_repo.get_by_tenant_id.return_value = _schedule_doc()
    mock_repo.delete_async.return_value = None

    mock_scheduler = AsyncMock()

    with (
        patch("kugel_common.database.database") as mock_db,
        patch("app.repositories.snapshot_schedule_repository.SnapshotScheduleRepository", return_value=mock_repo),
        patch("app.dependencies.get_scheduler.get_scheduler", return_value=mock_scheduler),
        patch("app.config.settings.settings") as mock_settings,
    ):
        mock_settings.DB_NAME_PREFIX = "db_stock"
        mock_db.get_db_async = AsyncMock(return_value=MagicMock())

        resp = await client.delete(f"/api/v1/tenants/{TENANT}/stock/snapshot-schedule")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["deleted"] is True
    mock_scheduler.remove_tenant_schedule.assert_called_once_with(TENANT)


@pytest.mark.asyncio
async def test_delete_snapshot_schedule_not_existing(client):
    """Deleting a non-existing schedule should still succeed."""
    mock_repo = AsyncMock()
    mock_repo.get_by_tenant_id.return_value = None

    with (
        patch("kugel_common.database.database") as mock_db,
        patch("app.repositories.snapshot_schedule_repository.SnapshotScheduleRepository", return_value=mock_repo),
        patch("app.config.settings.settings") as mock_settings,
    ):
        mock_settings.DB_NAME_PREFIX = "db_stock"
        mock_db.get_db_async = AsyncMock(return_value=MagicMock())

        resp = await client.delete(f"/api/v1/tenants/{TENANT}/stock/snapshot-schedule")

    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True
