# Copyright 2026 masa@kugel
"""journal files a posted journal or sale under the store and terminal of its URL (issue #134).

The URL's tenant was checked against the credential, but the body's own
tenant_id / store_code / terminal_no were stored as given, so a caller could
file entries under another store's or terminal's name.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.tran import get_log_service
from app.dependencies.get_journal_service import get_journal_service
from tests.unit.test_api_journal import _sample_journal_doc
from tests.unit.test_api_journal import make_app as make_journal_app
from tests.unit.test_api_tran import _mock_log_service
from tests.unit.test_api_tran import make_app as make_tran_app

JOURNAL = {
    "tenant_id": "T001",
    "store_code": "S001",
    "terminal_no": 1,
    "transaction_type": 101,
    "business_date": "20260101",
    "open_counter": 1,
    "business_counter": 1,
    "generate_date_time": "20260101T120000",
    "journal_text": "journal text",
    "receipt_text": "receipt text",
}
TRAN = {
    "event_id": "evt-001",
    "tenant_id": "T001",
    "store_code": "S001",
    "terminal_no": 1,
    "transaction_no": 100,
    "transaction_type": 101,
    "business_date": "20260101",
    "open_counter": 1,
    "business_counter": 1,
    "generate_date_time": "20260101T120000",
    "receipt_no": 1,
    "sales": {"total_amount_with_tax": 100.0, "total_quantity": 1},
    "staff": {"id": "S001", "name": "Staff One"},
    "user": {"id": "u1"},
}

ANOTHER = [("tenant_id", "T-OTHER"), ("store_code", "S-OTHER"), ("terminal_no", 9)]


def _journal_app(service):
    app = make_journal_app()
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
    app.dependency_overrides[get_journal_service] = lambda: service
    return app


def _tran_app(service):
    app = make_tran_app()
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
    app.dependency_overrides[get_log_service] = lambda: service
    return app


async def _post(app, url, body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(url, json=body)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", ANOTHER)
async def test_a_journal_naming_another_tenant_store_or_terminal_is_refused(field, value):
    service = AsyncMock()
    response = await _post(
        _journal_app(service), "/api/v1/tenants/T001/stores/S001/terminals/1/journals", {**JOURNAL, field: value}
    )

    assert response.status_code == 400
    service.receive_journal_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", ANOTHER)
async def test_a_sale_naming_another_tenant_store_or_terminal_is_refused(field, value):
    service = _mock_log_service()
    response = await _post(
        _tran_app(service), "/api/v1/tenants/T001/stores/S001/terminals/1/transactions", {**TRAN, field: value}
    )

    assert response.status_code == 400
    service.receive_tranlog_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_sale_that_leaves_them_out_is_filed_under_the_urls():
    service = _mock_log_service()
    body = {k: v for k, v in TRAN.items() if k not in ("tenant_id", "store_code", "terminal_no")}

    response = await _post(_tran_app(service), "/api/v1/tenants/T001/stores/S001/terminals/1/transactions", body)

    assert response.status_code == 201
    stored = service.receive_tranlog_async.await_args.args[0]
    assert (stored.tenant_id, stored.store_code, stored.terminal_no) == ("T001", "S001", 1)


@pytest.mark.asyncio
async def test_a_journal_naming_the_urls_is_stored():
    service = AsyncMock()
    service.receive_journal_async.return_value = _sample_journal_doc()

    response = await _post(_journal_app(service), "/api/v1/tenants/T001/stores/S001/terminals/1/journals", JOURNAL)

    assert response.status_code == 201
    service.receive_journal_async.assert_awaited_once()
