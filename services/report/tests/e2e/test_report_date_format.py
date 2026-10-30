"""A malformed business date is refused, not answered with an empty report.

Dates are matched as YYYYMMDD strings, so any other spelling matched nothing
and the report came back as a 200 with no sales in it.
"""
import os

import pytest
from httpx import AsyncClient
from kugel_common.utils.service_auth import create_service_token


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"report_scope": "daily", "business_date": "2024-01-01"},
        {"report_scope": "daily", "business_date_from": "20240101", "business_date_to": "2024/01/07"},
        {"report_scope": "flash", "business_date": "20241301", "open_counter": 1},
    ],
)
async def test_malformed_business_date_is_refused(http_client: AsyncClient, params):
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    headers = {"Authorization": f"Bearer {create_service_token(tenant_id, 'report')}"}

    for url in (
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/1/reports",
    ):
        response = await http_client.get(url, params={"report_type": "sales", **params}, headers=headers)

        assert response.status_code == 400, response.text
        assert response.json()["user_error"]["code"] == "412006"
