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
import asyncio
from fastapi import status
from httpx import AsyncClient
from datetime import datetime


def check_category_report_data(report_data: dict):
    """Check category report data structure and calculations"""
    
    # Check required fields exist
    assert "categories" in report_data
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
    
    # Check categories
    categories = report_data.get("categories", [])
    print(f"*** Number of Categories: {len(categories)}")
    
    # Verify totals match sum of categories
    if len(categories) > 0:
        total_gross = sum(cat.get("grossAmount", 0) for cat in categories)
        total_discount = sum(cat.get("discountAmount", 0) for cat in categories)
        total_net = sum(cat.get("netAmount", 0) for cat in categories)
        total_qty = sum(cat.get("quantity", 0) for cat in categories)
        
        # Print individual categories
        for cat in categories:
            print(f"*** Category: {cat.get('categoryName', cat.get('categoryCode', 'Unknown'))}")
            print(f"    - Category Code: {cat.get('categoryCode')}")
            print(f"    - Category Name: {cat.get('categoryName')}")
            print(f"    - Gross Amount: {cat.get('grossAmount')}")
            print(f"    - Discount Amount: {cat.get('discountAmount')}")
            print(f"    - Net Amount: {cat.get('netAmount')}")
            print(f"    - Quantity: {cat.get('quantity')}")
            print(f"    - Discount Quantity: {cat.get('discountQuantity', 0)}")
            print(f"    - Raw category data: {cat}")
        
        # Verify calculations
        assert abs(report_data.get("totalGrossAmount", 0) - total_gross) < 0.01, \
            f"Total gross mismatch: {report_data.get('totalGrossAmount')} != {total_gross}"
        assert abs(report_data.get("totalDiscountAmount", 0) - total_discount) < 0.01, \
            f"Total discount mismatch: {report_data.get('totalDiscountAmount')} != {total_discount}"
        assert abs(report_data.get("totalNetAmount", 0) - total_net) < 0.01, \
            f"Total net mismatch: {report_data.get('totalNetAmount')} != {total_net}"
        assert report_data.get("totalQuantity", 0) == total_qty, \
            f"Total quantity mismatch: {report_data.get('totalQuantity')} != {total_qty}"
        
        # Verify net = gross - discount for each category
        for cat in categories:
            expected_net = cat.get("grossAmount", 0) - cat.get("discountAmount", 0)
            assert abs(cat.get("netAmount", 0) - expected_net) < 0.01, \
                f"Category {cat.get('categoryCode')} net amount calculation error"


@pytest.mark.asyncio()
async def test_category_report_operations(http_client):
    
    tenant_id: str = os.environ.get("TENANT_ID")
    store_code: str = os.environ.get("STORE_CODE")
    terminal_no: int = int(os.environ.get("TERMINAL_NO"))
    business_date: str = datetime.now().strftime("%Y%m%d")
    
    # get token from auth service
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
    
    # get category flash report for store
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "category", "business_date": business_date, "open_counter": 1},
        headers=header,
    )
    
    if response.status_code != status.HTTP_200_OK:
        print(f"Error response: {response.status_code} - {response.text}")
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    print(f"\n=== CATEGORY FLASH REPORT DATA (STORE) ===")
    print(f"Full data response: {res.get('data')}")
    print(f"Categories in response: {res.get('data', {}).get('categories', [])}")
    print(f"===================================\n")
    
    check_category_report_data(res.get("data"))
    print(f"category flash report for store receipt : \n {res.get('data').get('receiptText')}")
    print(f"category flash report for store journal : \n {res.get('data').get('journalText')}")
    
    # Check receipt format contains expected elements
    receipt_text = res.get("data").get("receiptText")
    assert "分類別売上" in receipt_text  # Should contain category report title
    assert "速報" in receipt_text  # Should contain flash indicator (part of "【分類別売上レポート( 速報 )】")
    assert "営業日付" in receipt_text
    
    # get category daily report for store
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "daily", "report_type": "category", "business_date": business_date, "open_counter": 1},
        headers=header,
    )
    
    if response.status_code != status.HTTP_200_OK:
        print(f"Daily report error response: {response.status_code} - {response.text}")
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    check_category_report_data(res.get("data"))
    print(f"category daily report for store receipt : \n {res.get('data').get('receiptText')}")
    print(f"category daily report for store journal : \n {res.get('data').get('journalText')}")
    
    # Check receipt format for daily report
    receipt_text = res.get("data").get("receiptText")
    assert "分類別売上" in receipt_text
    assert "日報" in receipt_text  # Should contain daily indicator (part of "【分類別売上レポート( 日報 )】")
    
    # get category flash report for terminal
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={"report_scope": "flash", "report_type": "category", "business_date": business_date, "open_counter": 1},
        headers=header,
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    check_category_report_data(res.get("data"))
    print(f"category flash report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"category flash report for terminal journal : \n {res.get('data').get('journalText')}")
    
    # get api key from terminal info
    terminal_id = os.environ.get("TERMINAL_ID", f"{tenant_id}-{store_code}-{terminal_no}")
    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}?include_api_key=true"
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.get(url=terminal_url, headers=header)
    res = response.json()
    print(f"get terminal response: {res}")
    if response.status_code == 200:
        api_key = res.get("data").get("apiKey")
        print(f"terminal_id: {terminal_id}, api_key: {api_key}")
    else:
        # If terminal not found, skip API key tests
        print(f"Terminal {terminal_id} not found, skipping API key tests")
        return
    
    # get category flash report for terminal with api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "flash",
            "report_type": "category",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    
    check_category_report_data(res.get("data"))
    print(f"category flash report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"category flash report for terminal journal : \n {res.get('data').get('journalText')}")
    
    # get category daily report for terminal with api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "daily",
            "report_type": "category",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    
    check_category_report_data(res.get("data"))
    
    # get category daily report for store with api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "daily",
            "report_type": "category",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    
    check_category_report_data(res.get("data"))
    
    # Test new "flash" report scope (should work the same as "flush")
    # get category flash report for store with "flash" scope
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "category", "business_date": business_date, "open_counter": 1},
        headers=header,
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response for flash scope: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    check_category_report_data(res.get("data"))
    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text  # Should contain flash indicator
    print(f"category flash report for store receipt : \n {receipt_text}")
    
    # get category flash report for terminal with "flash" scope and api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "flash",
            "report_type": "category",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response for flash scope with API key: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    check_category_report_data(res.get("data"))
    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text  # Should contain flash indicator
    print(f"category flash report for terminal receipt : \n {receipt_text}")


@pytest.mark.asyncio
async def test_category_report_format_verification(http_client):
    """
    Test that category report format matches expected layout with discount information
    """
    tenant_id = os.getenv("TENANT_ID")
    store_code = os.getenv("STORE_CODE")
    business_date = os.getenv("BUSINESS_DATE", datetime.now().strftime("%Y%m%d"))
    
    # Get token for authenticated requests
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
    
    # Get category report
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "category", "business_date": business_date, "open_counter": 1},
        headers=header,
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    receipt_text = res.get("data").get("receiptText")
    
    # Verify receipt format
    journal_text = res.get("data").get("journalText")
    lines = journal_text.split("\n")
    
    # Check header format
    assert any("分類別売上" in line for line in lines), "Should contain category report title"
    assert any("速報" in line for line in lines), "Should contain report scope indicator"
    
    # Check if categories with discounts have proper 2-line format (only check individual category discount lines)
    for i, line in enumerate(lines):
        if "  値引" in line and i > 0:  # Look for indented discount lines only
            # This should be a discount line, check it's indented
            assert line.startswith("  "), f"Discount line should be indented: {line}"
            # Check format includes quantity and amount
            assert "点" in line, f"Discount line should include quantity: {line}"
            assert "円" in line, f"Discount line should include amount: {line}"
    
    # Check footer format
    assert any("レシートNo." in line and "------" in line for line in lines), \
        "Footer should contain 'レシートNo. ------'"
    
    print("Category report format verification passed")


@pytest.mark.asyncio
async def test_category_report_with_date_range(http_client):
    """Test category report generation with date range."""
    from kugel_common.utils.service_auth import create_service_token
    
    token = create_service_token("sample01", "report")
    headers = {"authorization": f"Bearer {token}"}

    response = await http_client.get(
        "/api/v1/tenants/sample01/stores/store001/reports",
        params={
            "report_scope": "daily",
            "report_type": "category",
            "business_date_from": "20240101",
            "business_date_to": "20240107",
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    # Check that date range fields are present
    report_data = data["data"]
    assert "businessDateFrom" in report_data
    assert "businessDateTo" in report_data
    assert report_data.get("businessDate") in [None, ""]
    
    # Should have category data
    assert "categories" in report_data
    assert isinstance(report_data["categories"], list)