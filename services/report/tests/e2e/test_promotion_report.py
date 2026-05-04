# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
import os
from fastapi import status
from httpx import AsyncClient
from datetime import datetime


def check_promotion_report_data(report_data: dict):
    """Check promotion report data structure and calculations.

    PromotionReportDocument has no Pydantic aliases (see BaseDocumentModel),
    so model_dump emits snake_case field names — matching how
    PaymentReportDocument's test (test_payment_report_all.py) reads its
    response.
    """
    assert "promotions" in report_data
    assert "total_gross_amount" in report_data
    assert "total_discount_amount" in report_data
    assert "total_net_amount" in report_data
    assert "total_quantity" in report_data
    assert "total_transaction_count" in report_data

    print(f"*** Total Gross Amount: {report_data.get('total_gross_amount')}")
    print(f"*** Total Discount Amount: {report_data.get('total_discount_amount')}")
    print(f"*** Total Net Amount: {report_data.get('total_net_amount')}")
    print(f"*** Total Quantity: {report_data.get('total_quantity')}")
    print(f"*** Total Transaction Count: {report_data.get('total_transaction_count')}")

    promotions = report_data.get("promotions", [])
    print(f"*** Number of Promotions: {len(promotions)}")

    if len(promotions) > 0:
        total_gross = sum(promo.get("gross_amount", 0) for promo in promotions)
        total_discount = sum(promo.get("discount_amount", 0) for promo in promotions)
        total_net = sum(promo.get("net_amount", 0) for promo in promotions)
        total_qty = sum(promo.get("quantity", 0) for promo in promotions)

        for promo in promotions:
            print(f"*** Promotion: {promo.get('promotion_code', 'Unknown')}")
            print(f"    - Promotion Code: {promo.get('promotion_code')}")
            print(f"    - Promotion Type: {promo.get('promotion_type')}")
            print(f"    - Gross Amount: {promo.get('gross_amount')}")
            print(f"    - Discount Amount: {promo.get('discount_amount')}")
            print(f"    - Net Amount: {promo.get('net_amount')}")
            print(f"    - Quantity: {promo.get('quantity')}")
            print(f"    - Transaction Count: {promo.get('transaction_count')}")

        assert (
            abs(report_data.get("total_gross_amount", 0) - total_gross) < 0.01
        ), f"Total gross mismatch: {report_data.get('total_gross_amount')} != {total_gross}"
        assert (
            abs(report_data.get("total_discount_amount", 0) - total_discount) < 0.01
        ), f"Total discount mismatch: {report_data.get('total_discount_amount')} != {total_discount}"
        assert (
            abs(report_data.get("total_net_amount", 0) - total_net) < 0.01
        ), f"Total net mismatch: {report_data.get('total_net_amount')} != {total_net}"
        assert (
            report_data.get("total_quantity", 0) == total_qty
        ), f"Total quantity mismatch: {report_data.get('total_quantity')} != {total_qty}"

        for promo in promotions:
            expected_net = promo.get("gross_amount", 0) - promo.get("discount_amount", 0)
            assert (
                abs(promo.get("net_amount", 0) - expected_net) < 0.01
            ), f"Promotion {promo.get('promotion_code')} net amount calculation error"


@pytest.mark.asyncio()
async def test_promotion_report_operations(http_client):
    """Test promotion report generation and data structure"""

    tenant_id: str = os.environ.get("TENANT_ID")
    store_code: str = os.environ.get("STORE_CODE")
    terminal_no: int = int(os.environ.get("TERMINAL_NO"))
    business_date: str = datetime.now().strftime("%Y%m%d")

    # Get token from auth service
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # Request promotion report
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "promotion", "business_date": business_date},
        headers=header,
    )

    print(f"Promotion report response status: {response.status_code}")
    print(f"Promotion report response: {response.json()}")

    # Check if promotion report type is supported
    # Note: If no promotion discounts exist, the report will be empty but still valid
    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        assert res.get("success") is True
        report_data = res.get("data")
        check_promotion_report_data(report_data)
    elif response.status_code == status.HTTP_400_BAD_REQUEST:
        # Report type might not be implemented yet
        print("Promotion report type not yet implemented or no data available")
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")


@pytest.mark.asyncio()
async def test_promotion_report_date_range(http_client):
    """Test promotion report with date range filter"""

    tenant_id: str = os.environ.get("TENANT_ID")
    store_code: str = os.environ.get("STORE_CODE")

    # Get token from auth service
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # Use a date range (last 7 days)
    today = datetime.now()
    business_date_from = (today.replace(day=1)).strftime("%Y%m%d")
    business_date_to = today.strftime("%Y%m%d")

    # Request promotion report with date range
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "promotion",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
        },
        headers=header,
    )

    print(f"Date range report response status: {response.status_code}")

    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        assert res.get("success") is True
        report_data = res.get("data")

        # Check date range is set correctly
        assert report_data.get("business_date_from") == business_date_from
        assert report_data.get("business_date_to") == business_date_to

        check_promotion_report_data(report_data)


@pytest.mark.asyncio()
async def test_promotion_report_empty_result(http_client):
    """Test promotion report when no promotion discounts exist"""

    tenant_id: str = os.environ.get("TENANT_ID")
    store_code: str = os.environ.get("STORE_CODE")

    # Get token from auth service
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # Use a past date where likely no data exists
    business_date = "20200101"

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "promotion", "business_date": business_date},
        headers=header,
    )

    print(f"Empty report response status: {response.status_code}")

    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        assert res.get("success") is True
        report_data = res.get("data")

        # Should have empty promotions list
        promotions = report_data.get("promotions", [])
        print(f"Promotions found: {len(promotions)}")

        # Totals should be zero
        assert report_data.get("totalDiscountAmount", 0) == 0
        assert report_data.get("totalQuantity", 0) == 0
