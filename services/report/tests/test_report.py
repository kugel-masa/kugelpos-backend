# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest, os, asyncio
from fastapi import status
from httpx import AsyncClient
from datetime import datetime

from tests.check_report_data import check_report_data


@pytest.mark.asyncio()
async def test_report_operations(http_client):

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

    # get sales flash report for store
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flush", "report_type": "sales", "business_date": business_date, "open_counter": 1},
        headers=header,
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None

    check_report_data(res.get("data"))
    print(f"sales daily report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"sales daily report for terminal journal : \n {res.get('data').get('journalText')}")

    # get sales daily report for store
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "daily", "report_type": "sales", "business_date": business_date, "open_counter": 1},
        headers=header,
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None

    check_report_data(res.get("data"))
    print(f"sales daily report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"sales daily report for terminal journal : \n {res.get('data').get('journalText')}")

    # get sales flash report for terminal
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={"report_scope": "flush", "report_type": "sales", "business_date": business_date, "open_counter": 1},
        headers=header,
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None

    check_report_data(res.get("data"))
    print(f"sales daily report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"sales daily report for terminal journal : \n {res.get('data').get('journalText')}")

    # get api key from terminal info
    terminal_id = os.environ.get("TERMINAL_ID")
    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}"
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.get(url=terminal_url, headers=header)
    res = response.json()
    print(f"get terminal response: {res}")
    api_key = res.get("data").get("apiKey")
    print(f"terminal_id: {terminal_id}, api_key: {api_key}")

    # get sales flash report for terminal with api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "flush",
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")

    check_report_data(res.get("data"))
    print(f"sales daily report for terminal receipt : \n {res.get('data').get('receiptText')}")
    print(f"sales daily report for terminal journal : \n {res.get('data').get('journalText')}")

    # get sales daily report for terminal with api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "daily",
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")

    check_report_data(res.get("data"))

    # get sales daily report for store with api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "daily",
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")

    check_report_data(res.get("data"))

    # Test new "flash" report scope (should work the same as "flush")
    # get sales flash report for store with "flash" scope
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "sales", "business_date": business_date, "open_counter": 1},
        headers=header,
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response for flash scope: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data") is not None

    check_report_data(res.get("data"))
    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text  # Should contain "速報" (preliminary report)
    print(f"sales flash report for store receipt : \n {receipt_text}")

    # get sales flash report for terminal with "flash" scope and api key
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "flash",
            "report_type": "sales",
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

    check_report_data(res.get("data"))
    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text  # Should contain "速報" (preliminary report)
    print(f"sales flash report for terminal receipt : \n {receipt_text}")


@pytest.mark.asyncio
async def test_flush_backward_compatibility(http_client):
    """
    Test that 'flush' report scope still works for backward compatibility.
    This ensures existing clients using 'flush' continue to function correctly.
    """
    tenant_id = os.getenv("TENANT_ID")
    store_code = os.getenv("STORE_CODE")
    terminal_no = int(os.getenv("TERMINAL_NO"))
    terminal_id = os.getenv("TERMINAL_ID")
    business_date = os.getenv("BUSINESS_DATE")

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

    # Get API key for the terminal
    async with AsyncClient() as http_terminal_client:
        terminal_response = await http_terminal_client.get(
            f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}", headers=header
        )
    assert terminal_response.status_code == status.HTTP_200_OK
    api_key = terminal_response.json()["data"]["apiKey"]

    # Test 1: Get report using deprecated "flush" - should still work
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flush", "report_type": "sales", "business_date": business_date, "open_counter": 1},
        headers=header,
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data") is not None

    # Verify the report contains the correct title
    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text  # Should contain "速報" (preliminary report)
    print("Backward compatibility test - 'flush' still works and shows 速報")

    # Test 2: Compare results between "flush" and "flash" - they should be identical
    # Get report using "flash"
    flash_response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={"report_scope": "flash", "report_type": "sales", "business_date": business_date, "open_counter": 1},
        headers=header,
    )

    assert flash_response.status_code == status.HTTP_200_OK
    flash_res = flash_response.json()

    # Compare key fields (excluding receiptText which contains timestamps)
    flush_data = res.get("data")
    flash_data = flash_res.get("data")

    # Compare sales data
    assert flush_data["salesGross"] == flash_data["salesGross"]
    assert flush_data["salesNet"] == flash_data["salesNet"]
    assert flush_data["returns"] == flash_data["returns"]
    assert flush_data["taxes"] == flash_data["taxes"]
    assert flush_data["payments"] == flash_data["payments"]
    assert flush_data["cash"] == flash_data["cash"]

    print("Verified: 'flush' and 'flash' produce identical results")

    # Test 3: Test with API key authentication
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "flush",
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers={"X-API-KEY": api_key},
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data") is not None

    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text
    print("API key authentication with 'flush' also works correctly")

    # Test 4: Verify that invalid report_scope values are handled
    # (The API currently doesn't validate report_scope, so any value other than "daily" is treated as flash)
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "invalid_scope",
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers=header,
    )

    assert response.status_code == status.HTTP_200_OK  # Currently no validation
    res = response.json()
    receipt_text = res.get("data").get("receiptText")
    assert "速報" in receipt_text  # Non-daily scopes show preliminary report
    print("Non-standard report_scope values default to preliminary report behavior")
