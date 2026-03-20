"""Unit tests for report API endpoints (app/api/v1/report.py)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.api.v1.report import router
from app.dependencies.get_report_service import get_report_service
from app.dependencies.get_staff_info import get_requesting_staff_id
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.exceptions import ServiceException
from app.exceptions.report_exceptions import TerminalNotClosedException
from app.models.documents.sales_report_document import (
    SalesReportDocument,
    SalesReportTemplate as DocSalesTemplate,
    TaxReportTemplate as DocTaxTemplate,
    PaymentReportTemplate as DocPaymentTemplate,
    CashReportTemplate as DocCashTemplate,
    CashInOutReportTemplate as DocCashInOutTemplate,
)


def make_app(
    mock_report_service=None,
    mock_tenant_id="test-tenant",
    mock_staff_id=None,
):
    """Create a FastAPI app with overridden dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    if mock_report_service is None:
        mock_report_service = AsyncMock()

    app.dependency_overrides[get_report_service] = lambda: mock_report_service
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: mock_tenant_id
    app.dependency_overrides[get_requesting_staff_id] = lambda: mock_staff_id
    return app


def make_sales_report_doc(**overrides):
    """Create a minimal SalesReportDocument for testing."""
    zero_sales = DocSalesTemplate(amount=0.0, quantity=0, count=0)
    zero_cash_io = DocCashInOutTemplate(amount=0.0, count=0)
    defaults = dict(
        tenant_id="test-tenant",
        store_code="STORE01",
        store_name="Test Store",
        terminal_no=1,
        business_date="20260101",
        open_counter=1,
        business_counter=1,
        report_scope="daily",
        report_type="sales",
        sales_gross=zero_sales,
        sales_net=zero_sales,
        discount_for_lineitems=zero_sales,
        discount_for_subtotal=zero_sales,
        returns=zero_sales,
        taxes=[],
        payments=[],
        cash=DocCashTemplate(
            logical_amount=0.0,
            physical_amount=0.0,
            difference_amount=0.0,
            cash_in=zero_cash_io,
            cash_out=zero_cash_io,
        ),
        generate_date_time="20260101120000",
    )
    defaults.update(overrides)
    return SalesReportDocument(**defaults)


STORE_REPORT_URL = "/api/v1/tenants/test-tenant/stores/STORE01/reports"
TERMINAL_REPORT_URL = "/api/v1/tenants/test-tenant/stores/STORE01/terminals/1/reports"


# ---------------------------------------------------------------------------
# get_report_for_store
# ---------------------------------------------------------------------------
class TestGetReportForStore:
    @pytest.mark.asyncio
    async def test_success_sales_report(self):
        """Happy path: returns a sales report for the store."""
        mock_service = AsyncMock()
        mock_service.get_report_for_store_async.return_value = make_sales_report_doc()
        app = make_app(mock_report_service=mock_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                STORE_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales", "business_date": "20260101"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["tenantId"] == "test-tenant"

    @pytest.mark.asyncio
    async def test_missing_date_params_returns_400(self):
        """Neither business_date nor date range provided -> 400."""
        app = make_app()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                STORE_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_flash_with_date_range_returns_400(self):
        """Flash scope does not support date ranges -> 400."""
        app = make_app()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                STORE_REPORT_URL,
                params={
                    "report_scope": "flash",
                    "report_type": "sales",
                    "business_date_from": "20260101",
                    "business_date_to": "20260102",
                },
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_exception_returns_error(self):
        """ServiceException from service layer -> HTTP error."""
        mock_service = AsyncMock()
        mock_service.get_report_for_store_async.side_effect = ServiceException(
            message="bad",
            error_code="500101",
            user_message="Something went wrong",
            status_code=500,
        )
        app = make_app(mock_report_service=mock_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                STORE_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales", "business_date": "20260101"},
            )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_terminal_not_closed_exception(self):
        """TerminalNotClosedException -> HTTP 403."""
        mock_service = AsyncMock()
        mock_service.get_report_for_store_async.side_effect = TerminalNotClosedException(
            message="Terminal 1 not closed"
        )
        app = make_app(mock_report_service=mock_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                STORE_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales", "business_date": "20260101"},
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_generic_exception_returns_500(self):
        """Unhandled exception -> 500."""
        mock_service = AsyncMock()
        mock_service.get_report_for_store_async.side_effect = RuntimeError("unexpected")
        app = make_app(mock_report_service=mock_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                STORE_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales", "business_date": "20260101"},
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# get_report_for_terminal
# ---------------------------------------------------------------------------
class TestGetReportForTerminal:
    @pytest.mark.asyncio
    async def test_success_sales_report(self):
        """Happy path: returns a sales report for a terminal."""
        mock_service = AsyncMock()
        mock_service.get_report_for_terminal_async.return_value = make_sales_report_doc()
        app = make_app(mock_report_service=mock_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                TERMINAL_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales", "business_date": "20260101"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_missing_date_params_returns_400(self):
        """Neither business_date nor date range -> 400."""
        app = make_app()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                TERMINAL_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_service_exception_returns_error(self):
        """ServiceException from service layer -> HTTP error."""
        mock_service = AsyncMock()
        mock_service.get_report_for_terminal_async.side_effect = ServiceException(
            message="bad",
            error_code="500101",
            user_message="Something went wrong",
            status_code=500,
        )
        app = make_app(mock_report_service=mock_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                TERMINAL_REPORT_URL,
                params={"report_scope": "daily", "report_type": "sales", "business_date": "20260101"},
            )
        assert resp.status_code == 500
