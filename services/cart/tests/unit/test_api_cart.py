"""Unit tests for cart API endpoints (app/api/v1/cart.py)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from kugel_common.exceptions import register_exception_handlers
from app.api.v1.cart import router as cart_router
from app.dependencies.get_cart_service import (
    get_cart_service_async,
    get_cart_service_with_cart_id_async,
)


def _make_app():
    app = FastAPI()
    app.include_router(cart_router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


def _make_cart_service_mock(cart_id="test-cart-id-123"):
    """Create a mock CartService with terminal_info and cart_id."""
    svc = AsyncMock()
    svc.cart_id = cart_id
    terminal_info = MagicMock()
    terminal_info.terminal_id = "tenant1-store1-1"
    terminal_info.tenant_id = "tenant1"
    terminal_info.store_code = "store1"
    terminal_info.terminal_no = 1
    svc.terminal_info = terminal_info
    return svc


def _make_cart_doc_mock():
    """Create a minimal mock cart document that SchemasTransformerV1 can transform."""
    doc = MagicMock()
    doc.cart_id = "test-cart-id-123"
    doc.cart_status = "idle"
    doc.tenant_id = "tenant1"
    doc.store_code = "store1"
    doc.store_name = "Test Store"
    doc.terminal_no = 1
    doc.total_amount = 1000.0
    doc.total_amount_with_tax = 1100.0
    doc.total_quantity = 2
    doc.total_discount_amount = 0.0
    doc.deposit_amount = 0.0
    doc.change_amount = 0.0
    doc.stamp_duty_amount = 0.0
    doc.receipt_no = 1
    doc.transaction_no = 1
    doc.transaction_type = 1
    doc.business_date = "20260320"
    doc.generate_date_time = "2026-03-20T10:00:00"
    doc.subtotal_amount = 1000.0
    doc.balance_amount = 1100.0
    doc.line_items = []
    doc.payments = []
    doc.taxes = []
    doc.subtotal_discounts = []
    doc.receipt_text = None
    doc.journal_text = None
    doc.staff = None
    doc.status = None
    return doc


CART_SCHEMA_DICT = {
    "cart_id": "test-cart-id-123",
    "cart_status": "idle",
    "tenant_id": "tenant1",
    "store_code": "store1",
    "store_name": "Test Store",
    "terminal_no": 1,
    "total_amount": 1000.0,
    "total_amount_with_tax": 1100.0,
    "total_quantity": 2,
    "total_discount_amount": 0.0,
    "deposit_amount": 0.0,
    "change_amount": 0.0,
    "stamp_duty_amount": 0.0,
    "receipt_no": 1,
    "transaction_no": 1,
    "transaction_type": 1,
    "business_date": "20260320",
    "generate_date_time": "2026-03-20T10:00:00",
    "subtotal_amount": 1000.0,
    "balance_amount": 1100.0,
    "line_items": [],
    "payments": [],
    "taxes": [],
    "subtotal_discounts": [],
    "receipt_text": None,
    "journal_text": None,
    "staff": None,
    "status": None,
}


def _patch_transformer():
    """Patch SchemasTransformerV1.transform_cart to return a predictable Cart-like object."""
    cart_mock = MagicMock()
    cart_mock.model_dump.return_value = CART_SCHEMA_DICT
    return patch(
        "app.api.v1.cart.SchemasTransformerV1.transform_cart",
        return_value=cart_mock,
    )


# ---------------------------------------------------------------------------
# create_cart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_cart_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.create_cart_async.return_value = "new-cart-id-456"

    app.dependency_overrides[get_cart_service_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/carts",
            json={"transaction_type": 1, "user_id": "u1", "user_name": "User1"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["cartId"] == "new-cart-id-456"


@pytest.mark.asyncio
async def test_create_cart_service_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.create_cart_async.side_effect = Exception("DB error")

    app.dependency_overrides[get_cart_service_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/carts",
            json={"transaction_type": 1},
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# get_cart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cart_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.get_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/carts/test-cart-id-123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_get_cart_service_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.get_cart_async.side_effect = Exception("Not found")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/carts/test-cart-id-123")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# cancel_transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_transaction_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.cancel_transaction_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/carts/test-cart-id-123/cancel")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_cancel_transaction_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.cancel_transaction_async.side_effect = Exception("Cannot cancel")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/carts/test-cart-id-123/cancel")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# add_items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_items_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_item_to_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/carts/test-cart-id-123/lineItems",
                json=[{"item_code": "ITEM001", "quantity": 2, "unit_price": 500.0}],
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_add_items_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_item_to_cart_async.side_effect = Exception("Item not found")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/carts/test-cart-id-123/lineItems",
            json=[{"item_code": "ITEM001", "quantity": 2}],
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# cancel_line_item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_line_item_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.cancel_line_item_from_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/carts/test-cart-id-123/lineItems/1/cancel")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_cancel_line_item_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.cancel_line_item_from_cart_async.side_effect = Exception("Line not found")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/carts/test-cart-id-123/lineItems/1/cancel")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# update_item_unit_price
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_unit_price_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.update_line_item_unit_price_in_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/carts/test-cart-id-123/lineItems/1/unitPrice",
                json={"unit_price": 750.0},
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_update_unit_price_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.update_line_item_unit_price_in_cart_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            "/api/v1/carts/test-cart-id-123/lineItems/1/unitPrice",
            json={"unit_price": 750.0},
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# update_item_quantity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_quantity_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.update_line_item_quantity_in_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/carts/test-cart-id-123/lineItems/1/quantity",
                json={"quantity": 5},
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_update_quantity_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.update_line_item_quantity_in_cart_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            "/api/v1/carts/test-cart-id-123/lineItems/1/quantity",
            json={"quantity": 5},
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# add_discount_to_line_item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_discount_to_line_item_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_discount_to_line_item_in_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/carts/test-cart-id-123/lineItems/1/discounts",
                json=[{"discount_type": "rate", "discount_value": 10.0}],
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_add_discount_to_line_item_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_discount_to_line_item_in_cart_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/carts/test-cart-id-123/lineItems/1/discounts",
            json=[{"discount_type": "rate", "discount_value": 10.0}],
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# subtotal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subtotal_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.subtotal_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/carts/test-cart-id-123/subtotal")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_subtotal_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.subtotal_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/carts/test-cart-id-123/subtotal")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# discount_to_cart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discount_to_cart_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_discount_to_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/carts/test-cart-id-123/discounts",
                json=[{"discount_type": "amount", "discount_value": 100.0}],
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_discount_to_cart_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_discount_to_cart_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/carts/test-cart-id-123/discounts",
            json=[{"discount_type": "amount", "discount_value": 100.0}],
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payments_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_payment_to_cart_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/carts/test-cart-id-123/payments",
                json=[{"payment_code": "CASH", "amount": 1100}],
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_payments_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.add_payment_to_cart_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/carts/test-cart-id-123/payments",
            json=[{"payment_code": "CASH", "amount": 1100}],
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# bill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bill_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.bill_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/carts/test-cart-id-123/bill")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_bill_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.bill_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/carts/test-cart-id-123/bill")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# resume_item_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_item_entry_success():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.resume_item_entry_async.return_value = _make_cart_doc_mock()

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    with _patch_transformer():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/carts/test-cart-id-123/resume-item-entry")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_resume_item_entry_error():
    app = _make_app()
    svc = _make_cart_service_mock()
    svc.resume_item_entry_async.side_effect = Exception("err")

    app.dependency_overrides[get_cart_service_with_cart_id_async] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/carts/test-cart-id-123/resume-item-entry")
    assert resp.status_code == 500
