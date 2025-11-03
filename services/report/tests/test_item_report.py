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


def check_item_report_data(report_data: dict):
    """Check item report data structure and calculations"""
    
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
    
    # Check categories with items
    categories = report_data.get("categories", [])
    print(f"*** Number of Categories: {len(categories)}")
    
    # Verify totals match sum of categories
    if len(categories) > 0:
        total_gross = 0
        total_discount = 0
        total_net = 0
        total_qty = 0
        total_trans_count = 0
        
        # Process each category
        for cat in categories:
            print(f"*** Category: {cat.get('categoryName', cat.get('categoryCode', 'Unknown'))}")
            print(f"    - Category Total Gross: {cat.get('categoryTotalGrossAmount')}")
            print(f"    - Category Total Discount: {cat.get('categoryTotalDiscountAmount')}")
            print(f"    - Category Total Net: {cat.get('categoryTotalNetAmount')}")
            print(f"    - Category Total Quantity: {cat.get('categoryTotalQuantity')}")
            
            # Check items in category
            items = cat.get("items", [])
            print(f"    - Number of Items: {len(items)}")
            
            # Sum up items in category
            cat_item_gross = 0
            cat_item_discount = 0
            cat_item_net = 0
            cat_item_qty = 0
            cat_item_trans = 0
            
            for item in items:
                print(f"      * Item: {item.get('itemName', item.get('itemCode', 'Unknown'))}")
                print(f"        - Gross: {item.get('grossAmount')}, Discount: {item.get('discountAmount')}, Net: {item.get('netAmount')}")
                print(f"        - Quantity: {item.get('quantity')}, Transactions: {item.get('transactionCount')}")
                
                # Verify item-level calculations
                expected_net = item.get("grossAmount", 0) - item.get("discountAmount", 0)
                assert abs(item.get("netAmount", 0) - expected_net) < 0.01, \
                    f"Item {item.get('itemCode')} net amount calculation error"
                
                # Add to category totals
                cat_item_gross += item.get("grossAmount", 0)
                cat_item_discount += item.get("discountAmount", 0)
                cat_item_net += item.get("netAmount", 0)
                cat_item_qty += item.get("quantity", 0)
                cat_item_trans += item.get("transactionCount", 0)
            
            # Verify category totals match sum of items
            assert abs(cat.get("categoryTotalGrossAmount", 0) - cat_item_gross) < 0.01, \
                f"Category {cat.get('categoryCode')} gross total mismatch"
            assert abs(cat.get("categoryTotalDiscountAmount", 0) - cat_item_discount) < 0.01, \
                f"Category {cat.get('categoryCode')} discount total mismatch"
            assert abs(cat.get("categoryTotalNetAmount", 0) - cat_item_net) < 0.01, \
                f"Category {cat.get('categoryCode')} net total mismatch"
            assert cat.get("categoryTotalQuantity", 0) == cat_item_qty, \
                f"Category {cat.get('categoryCode')} quantity total mismatch"
            
            # Add to overall totals
            total_gross += cat.get("categoryTotalGrossAmount", 0)
            total_discount += cat.get("categoryTotalDiscountAmount", 0)
            total_net += cat.get("categoryTotalNetAmount", 0)
            total_qty += cat.get("categoryTotalQuantity", 0)
            total_trans_count += cat.get("categoryTotalTransactionCount", 0)
        
        # Verify overall totals
        assert abs(report_data.get("totalGrossAmount", 0) - total_gross) < 0.01, \
            f"Total gross mismatch: {report_data.get('totalGrossAmount')} != {total_gross}"
        assert abs(report_data.get("totalDiscountAmount", 0) - total_discount) < 0.01, \
            f"Total discount mismatch: {report_data.get('totalDiscountAmount')} != {total_discount}"
        assert abs(report_data.get("totalNetAmount", 0) - total_net) < 0.01, \
            f"Total net mismatch: {report_data.get('totalNetAmount')} != {total_net}"
        assert report_data.get("totalQuantity", 0) == total_qty, \
            f"Total quantity mismatch: {report_data.get('totalQuantity')} != {total_qty}"


@pytest.mark.asyncio()
async def test_item_report_operations(http_client):
    
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
    
    # get item flash report for store
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "item", "business_date": business_date, "open_counter": 1},
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
    
    check_item_report_data(res.get("data"))
    print(f"item flash report for store receipt : \n {res.get('data').get('receiptText')}")
    print(f"item flash report for store journal : \n {res.get('data').get('journalText')}")
    
    # Check receipt format contains expected elements
    receipt_text = res.get("data").get("receiptText")
    assert "商品別売上" in receipt_text  # Should contain item report title
    assert "速報" in receipt_text  # Should contain flash indicator
    assert "営業日付" in receipt_text
    # Note: "小計" only appears when there are categories with items
    assert "合計" in receipt_text  # Should have grand total
    
    # get item daily report for store
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "daily", "report_type": "item", "business_date": business_date, "open_counter": 1},
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
    
    check_item_report_data(res.get("data"))
    print(f"item daily report for store receipt : \n {res.get('data').get('receiptText')}")
    print(f"item daily report for store journal : \n {res.get('data').get('journalText')}")
    
    # Check receipt format for daily report
    receipt_text = res.get("data").get("receiptText")
    assert "商品別売上" in receipt_text
    assert "日報" in receipt_text  # Should contain daily indicator
    
    # get item flash report for terminal
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={"report_scope": "flash", "report_type": "item", "business_date": business_date, "open_counter": 1},
        headers=header,
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    check_item_report_data(res.get("data"))
    print(f"item flash report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"item flash report for terminal journal : \n {res.get('data').get('journalText')}")
    
    # get item daily report for terminal with JWT token
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "report_scope": "daily",
            "report_type": "item",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers=header,
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Daily report for terminal response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None
    
    check_item_report_data(res.get("data"))
    print(f"item daily report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"item daily report for terminal journal : \n {res.get('data').get('journalText')}")
    
    # Check receipt format for terminal daily report
    receipt_text = res.get("data").get("receiptText")
    assert "商品別売上" in receipt_text
    assert "日報" in receipt_text  # Should contain daily indicator
    assert "レジNo." in receipt_text  # Should have terminal number


@pytest.mark.asyncio
async def test_item_report_with_date_range(http_client):
    """Test item report generation with date range."""
    from kugel_common.utils.service_auth import create_service_token
    
    token = create_service_token("sample01", "report")
    headers = {"authorization": f"Bearer {token}"}

    response = await http_client.get(
        "/api/v1/tenants/sample01/stores/store001/reports",
        params={
            "report_scope": "daily",
            "report_type": "item",
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
    
    # Should have categories with items
    assert "categories" in report_data
    assert isinstance(report_data["categories"], list)