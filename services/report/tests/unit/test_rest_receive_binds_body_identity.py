# Copyright 2026 masa@kugel
"""report files a posted sale under the store and terminal of its URL (issue #134).

The URL's tenant was checked against the credential, but the body's own
tenant_id / store_code / terminal_no were stored as given, so a caller could
count a sale under another store's or terminal's name.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from tests.unit.test_api_tran import RECEIVE_TRAN_URL, make_app

TRAN = {
    "tenant_id": "test-tenant",
    "store_code": "STORE01",
    "terminal_no": 1,
    "transaction_no": 100,
    "business_date": "20260101",
    "open_counter": 1,
    "transaction_type": 1,
}


async def _post(service, body):
    app = make_app(mock_log_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(RECEIVE_TRAN_URL, json=body)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("tenant_id", "T-OTHER"), ("store_code", "S-OTHER"), ("terminal_no", 9)])
async def test_a_sale_naming_another_tenant_store_or_terminal_is_refused(field, value):
    service = AsyncMock()

    response = await _post(service, {**TRAN, field: value})

    assert response.status_code == 400
    service.receive_tranlog_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_sale_that_leaves_them_out_is_filed_under_the_urls():
    service = AsyncMock()
    body = {k: v for k, v in TRAN.items() if k not in ("tenant_id", "store_code", "terminal_no")}

    response = await _post(service, body)

    assert response.status_code == 201
    stored = service.receive_tranlog_async.await_args.args[0]
    assert (stored.tenant_id, stored.store_code, stored.terminal_no) == ("test-tenant", "STORE01", 1)
