"""
Unit tests for stock API endpoints.
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
from app.models.documents import StockDocument, StockUpdateDocument, StockSnapshotDocument, StockSnapshotItem
from app.enums.update_type import UpdateType
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.exceptions import register_exception_handlers


# -- helpers --

NOW = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
TENANT = "test_tenant"
STORE = "store01"
ITEM = "ITEM001"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


def _stock_doc(**overrides) -> StockDocument:
    defaults = dict(
        tenant_id=TENANT,
        store_code=STORE,
        item_code=ITEM,
        current_quantity=50.0,
        minimum_quantity=10.0,
        reorder_point=20.0,
        reorder_quantity=100.0,
        last_transaction_id="TRX001",
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return StockDocument(**defaults)


def _update_doc(**overrides) -> StockUpdateDocument:
    defaults = dict(
        tenant_id=TENANT,
        store_code=STORE,
        item_code=ITEM,
        update_type=UpdateType.SALE,
        quantity_change=-5.0,
        before_quantity=50.0,
        after_quantity=45.0,
        reference_id="TRX001",
        timestamp=NOW,
        operator_id="operator1",
        note="test",
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return StockUpdateDocument(**defaults)


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


# ===== get_store_stocks =====

@pytest.mark.asyncio
async def test_get_store_stocks_success(client, mock_stock_service):
    docs = [_stock_doc(), _stock_doc(item_code="ITEM002")]
    mock_stock_service.get_store_stocks_async.return_value = (docs, 2)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock?page=1&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["metadata"]["total"] == 2
    assert len(body["data"]["data"]) == 2


@pytest.mark.asyncio
async def test_get_store_stocks_empty(client, mock_stock_service):
    mock_stock_service.get_store_stocks_async.return_value = ([], 0)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock")
    assert resp.status_code == 200
    assert resp.json()["data"]["metadata"]["total"] == 0
    assert resp.json()["data"]["data"] == []


# ===== get_stock =====

@pytest.mark.asyncio
async def test_get_stock_success(client, mock_stock_service):
    mock_stock_service.get_stock_async.return_value = _stock_doc()

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == ITEM


@pytest.mark.asyncio
async def test_get_stock_not_found(client, mock_stock_service):
    mock_stock_service.get_stock_async.return_value = None

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}")
    assert resp.status_code == 404


# ===== update_stock =====

@pytest.mark.asyncio
async def test_update_stock_success(client, mock_stock_service):
    mock_stock_service.update_stock_async.return_value = _update_doc()

    payload = {
        "quantityChange": -5.0,
        "updateType": "sale",
        "referenceId": "TRX001",
        "operatorId": "operator1",
        "note": "test",
    }
    resp = await client.put(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/update", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["quantityChange"] == -5.0


@pytest.mark.asyncio
async def test_update_stock_uses_terminal_id_when_no_operator(client, mock_stock_service):
    """When operator_id is not provided, terminal_id should be used."""
    mock_stock_service.update_stock_async.return_value = _update_doc(operator_id="term01")

    payload = {
        "quantityChange": 10.0,
        "updateType": "purchase",
    }
    resp = await client.put(
        f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/update?terminal_id=term01",
        json=payload,
    )
    assert resp.status_code == 200


# ===== get_stock_history =====

@pytest.mark.asyncio
async def test_get_stock_history_success(client, mock_stock_service):
    updates = [_update_doc(), _update_doc(quantity_change=10.0, update_type=UpdateType.PURCHASE)]
    mock_stock_service.get_stock_history_async.return_value = (updates, 2)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["metadata"]["total"] == 2


@pytest.mark.asyncio
async def test_get_stock_history_empty(client, mock_stock_service):
    mock_stock_service.get_stock_history_async.return_value = ([], 0)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/history")
    assert resp.status_code == 200
    assert resp.json()["data"]["data"] == []


# ===== get_low_stocks =====

@pytest.mark.asyncio
async def test_get_low_stocks_success(client, mock_stock_service):
    docs = [_stock_doc(current_quantity=5.0)]
    mock_stock_service.get_low_stocks_async.return_value = (docs, 1)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/low")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["metadata"]["total"] == 1


@pytest.mark.asyncio
async def test_get_low_stocks_empty(client, mock_stock_service):
    mock_stock_service.get_low_stocks_async.return_value = ([], 0)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/low")
    assert resp.status_code == 200
    assert resp.json()["data"]["data"] == []


# ===== get_reorder_alerts =====

@pytest.mark.asyncio
async def test_get_reorder_alerts_success(client, mock_stock_service):
    docs = [_stock_doc(current_quantity=15.0, reorder_point=20.0)]
    mock_stock_service.get_reorder_alerts_async.return_value = (docs, 1)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/reorder-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["metadata"]["total"] == 1


@pytest.mark.asyncio
async def test_get_reorder_alerts_empty(client, mock_stock_service):
    mock_stock_service.get_reorder_alerts_async.return_value = ([], 0)

    resp = await client.get(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/reorder-alerts")
    assert resp.status_code == 200
    assert resp.json()["data"]["data"] == []


# ===== set_minimum_quantity =====

@pytest.mark.asyncio
async def test_set_minimum_quantity_success(client, mock_stock_service):
    mock_stock_service.set_minimum_quantity_async.return_value = True

    payload = {"minimumQuantity": 15.0}
    resp = await client.put(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/minimum", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_set_minimum_quantity_not_found(client, mock_stock_service):
    mock_stock_service.set_minimum_quantity_async.return_value = False

    payload = {"minimumQuantity": 15.0}
    resp = await client.put(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/minimum", json=payload)
    assert resp.status_code == 404


# ===== set_reorder_parameters =====

@pytest.mark.asyncio
async def test_set_reorder_parameters_success(client, mock_stock_service):
    mock_stock_service.set_reorder_parameters_async.return_value = True

    payload = {"reorderPoint": 20.0, "reorderQuantity": 100.0}
    resp = await client.put(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/reorder", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_set_reorder_parameters_not_found(client, mock_stock_service):
    mock_stock_service.set_reorder_parameters_async.return_value = False

    payload = {"reorderPoint": 20.0, "reorderQuantity": 100.0}
    resp = await client.put(f"/api/v1/tenants/{TENANT}/stores/{STORE}/stock/{ITEM}/reorder", json=payload)
    assert resp.status_code == 404


# ===== handle_transaction_log =====

@pytest.mark.asyncio
async def test_tranlog_health_check(client):
    """Health check messages should return SUCCESS."""
    payload = {"data": {"test": "health-check"}}
    resp = await client.post("/api/v1/tranlog", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_tranlog_missing_event_id(client):
    """Missing event_id should return DROP with 400."""
    payload = {"data": {"tenant_id": TENANT}}
    resp = await client.post("/api/v1/tranlog", json=payload)
    assert resp.status_code == 400
    assert resp.json()["status"] == "DROP"


@pytest.mark.asyncio
async def test_tranlog_missing_tenant_id(client):
    """Missing tenant_id should return DROP with 400."""
    payload = {"data": {"event_id": "evt_001"}}
    resp = await client.post("/api/v1/tranlog", json=payload)
    assert resp.status_code == 400
    assert resp.json()["status"] == "DROP"


@pytest.mark.asyncio
async def test_tranlog_success(client):
    """Successful transaction processing."""
    payload = {
        "data": {
            "event_id": "evt_001",
            "tenant_id": TENANT,
            "store_code": STORE,
            "terminal_no": "001",
            "transaction_no": "TRX001",
            "items": [{"item_code": "ITEM001", "quantity": 2}],
        }
    }

    mock_stock_svc = AsyncMock()
    mock_state_mgr = MagicMock()
    mock_state_mgr.get_state = AsyncMock(return_value=(None, None))
    mock_state_mgr.save_state = AsyncMock(return_value=(True, None))

    with (
        patch("app.api.v1.stock.state_store_manager", mock_state_mgr),
        patch("app.api.v1.stock.StockService", return_value=mock_stock_svc),
        patch("kugel_common.database.database") as mock_db_helper,
        patch("app.dependencies.get_alert_service.get_alert_service", return_value=None),
        patch("app.api.v1.stock._notify_pubsub_status", new_callable=AsyncMock),
        patch("app.api.v1.stock.asyncio") as mock_asyncio,
    ):
        mock_db_helper.get_db_async = AsyncMock(return_value=MagicMock())
        mock_asyncio.create_task = MagicMock()

        resp = await client.post("/api/v1/tranlog", json=payload)

    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
    mock_stock_svc.process_transaction_async.assert_called_once()


@pytest.mark.asyncio
async def test_tranlog_duplicate_event(client):
    """Duplicate events should return SUCCESS (already processed)."""
    payload = {
        "data": {
            "event_id": "evt_dup",
            "tenant_id": TENANT,
            "store_code": STORE,
            "terminal_no": "001",
            "transaction_no": "TRX002",
            "items": [],
        }
    }

    mock_state_mgr = MagicMock()
    mock_state_mgr.get_state = AsyncMock(return_value=({"event_id": "evt_dup"}, None))

    with (
        patch("app.api.v1.stock.state_store_manager", mock_state_mgr),
        patch("app.api.v1.stock.StockService", return_value=AsyncMock()),
        patch("kugel_common.database.database") as mock_db_helper,
        patch("app.dependencies.get_alert_service.get_alert_service", return_value=None),
        patch("app.api.v1.stock._notify_pubsub_status", new_callable=AsyncMock),
        patch("app.api.v1.stock.asyncio") as mock_asyncio,
    ):
        mock_db_helper.get_db_async = AsyncMock(return_value=MagicMock())
        mock_asyncio.create_task = MagicMock()

        resp = await client.post("/api/v1/tranlog", json=payload)

    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
