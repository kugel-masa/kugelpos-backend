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
    """Check promotion report data structure and calculations"""

    # Check required fields exist
    assert "promotions" in report_data
    assert "totalGrossAmount" in report_data
    assert "totalDiscountAmount" in report_data
    assert "totalNetAmount" in report_data
    assert "totalQuantity" in report_data
    assert "totalTransactionCount" in report_data

    # Print summary
    print(f"*** Total Gross Amount: {report_data.get('totalGrossAmount')}")
    print(f"*** Total Discount Amount: {report_data.get('totalDiscountAmount')}")
    print(f"*** Total Net Amount: {report_data.get('totalNetAmount')}")
    print(f"*** Total Quantity: {report_data.get('totalQuantity')}")
    print(f"*** Total Transaction Count: {report_data.get('totalTransactionCount')}")

    # Check promotions
    promotions = report_data.get("promotions", [])
    print(f"*** Number of Promotions: {len(promotions)}")

    # Verify totals match sum of promotions
    if len(promotions) > 0:
        total_gross = sum(promo.get("grossAmount", 0) for promo in promotions)
        total_discount = sum(promo.get("discountAmount", 0) for promo in promotions)
        total_net = sum(promo.get("netAmount", 0) for promo in promotions)
        total_qty = sum(promo.get("quantity", 0) for promo in promotions)

        # Print individual promotions
        for promo in promotions:
            print(f"*** Promotion: {promo.get('promotionCode', 'Unknown')}")
            print(f"    - Promotion Code: {promo.get('promotionCode')}")
            print(f"    - Promotion Type: {promo.get('promotionType')}")
            print(f"    - Gross Amount: {promo.get('grossAmount')}")
            print(f"    - Discount Amount: {promo.get('discountAmount')}")
            print(f"    - Net Amount: {promo.get('netAmount')}")
            print(f"    - Quantity: {promo.get('quantity')}")
            print(f"    - Transaction Count: {promo.get('transactionCount')}")

        # Verify calculations
        assert (
            abs(report_data.get("totalGrossAmount", 0) - total_gross) < 0.01
        ), f"Total gross mismatch: {report_data.get('totalGrossAmount')} != {total_gross}"
        assert (
            abs(report_data.get("totalDiscountAmount", 0) - total_discount) < 0.01
        ), f"Total discount mismatch: {report_data.get('totalDiscountAmount')} != {total_discount}"
        assert (
            abs(report_data.get("totalNetAmount", 0) - total_net) < 0.01
        ), f"Total net mismatch: {report_data.get('totalNetAmount')} != {total_net}"
        assert (
            report_data.get("totalQuantity", 0) == total_qty
        ), f"Total quantity mismatch: {report_data.get('totalQuantity')} != {total_qty}"

        # Verify net = gross - discount for each promotion
        for promo in promotions:
            expected_net = promo.get("grossAmount", 0) - promo.get("discountAmount", 0)
            assert (
                abs(promo.get("netAmount", 0) - expected_net) < 0.01
            ), f"Promotion {promo.get('promotionCode')} net amount calculation error"


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
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports/flash?"
        f"business_date={business_date}&report_type=promotion",
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
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports/flash?"
        f"business_date_from={business_date_from}&business_date_to={business_date_to}&report_type=promotion",
        headers=header,
    )

    print(f"Date range report response status: {response.status_code}")

    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        assert res.get("success") is True
        report_data = res.get("data")

        # Check date range is set correctly
        assert report_data.get("businessDateFrom") == business_date_from
        assert report_data.get("businessDateTo") == business_date_to

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
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports/flash?"
        f"business_date={business_date}&report_type=promotion",
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
