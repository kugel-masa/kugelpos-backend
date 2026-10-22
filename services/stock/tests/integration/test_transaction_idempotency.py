"""Stock movements from a transaction, against a real MongoDB (issue #137).

The unique index on stock_update is keyed on (cart_id, item_code,
update_type), so these cannot be shown with mocks: the failures below were
the index rejecting a write the service believed it needed.
"""

import uuid

import pytest

from kugel_common.database import database as db_helper

from app.config.settings import settings
from app.services.stock_service import StockService


async def _service(tenant_id: str) -> StockService:
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return StockService(db)


def _sale(tenant_id: str, store_code: str, items: list[tuple[str, int]]) -> dict:
    return {
        "tenant_id": tenant_id,
        "store_code": store_code,
        "terminal_no": 1,
        "transaction_no": 1,
        "cart_id": f"cart-{uuid.uuid4()}",
        "transaction_type": 101,
        "sales": {"is_cancelled": False},
        "line_items": [
            {"item_code": item_code, "quantity": quantity, "is_cancelled": False} for item_code, quantity in items
        ],
    }


async def _quantity(service: StockService, tenant_id: str, store_code: str, item_code: str) -> float:
    stock = await service.get_stock_async(tenant_id, store_code, item_code)
    return stock.current_quantity if stock else 0


@pytest.mark.asyncio
async def test_the_same_item_scanned_twice_is_decremented_by_both(test_tenant_id, test_store_code):
    """The cart adds a line per scan. The second line of an item used to hit
    the unique index, have its $inc rolled back, and never reach stock."""
    service = await _service(test_tenant_id)
    item = f"DUP-{uuid.uuid4().hex[:8]}"

    await service.process_transaction_async(_sale(test_tenant_id, test_store_code, [(item, 1), (item, 2)]))

    assert await _quantity(service, test_tenant_id, test_store_code, item) == -3


@pytest.mark.asyncio
async def test_a_redelivery_applies_what_the_failed_delivery_did_not(test_tenant_id, test_store_code):
    """The first delivery applies one item and fails on the next. Dapr
    redelivers: the remaining items are applied, the first is not applied
    again, and a third delivery changes nothing."""
    service = await _service(test_tenant_id)
    first, second, third = (f"RED-{n}-{uuid.uuid4().hex[:8]}" for n in range(3))
    sale = _sale(test_tenant_id, test_store_code, [(first, 1), (second, 2), (third, 3)])

    original = service.update_stock_async
    calls = 0

    async def fail_on_the_second_item(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("database went away")
        return await original(**kwargs)

    service.update_stock_async = fail_on_the_second_item
    with pytest.raises(RuntimeError):
        await service.process_transaction_async(sale)
    service.update_stock_async = original

    assert [await _quantity(service, test_tenant_id, test_store_code, i) for i in (first, second, third)] == [-1, 0, 0]

    await service.process_transaction_async(sale)
    assert [await _quantity(service, test_tenant_id, test_store_code, i) for i in (first, second, third)] == [-1, -2, -3]

    await service.process_transaction_async(sale)
    assert [await _quantity(service, test_tenant_id, test_store_code, i) for i in (first, second, third)] == [-1, -2, -3]
