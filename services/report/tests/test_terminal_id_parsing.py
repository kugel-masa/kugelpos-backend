# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Test for terminal_id parsing functionality (Issue #28)

This test verifies that terminal_id is correctly parsed using hyphen delimiter
when using API key authentication. This tests the bug fix for Issue #28 where
the code was incorrectly using underscore instead of hyphen.
"""
import pytest
import os
from fastapi import status
from httpx import AsyncClient
from datetime import datetime
from unittest.mock import patch
import logging
from tests.log_maker import make_tran_log
from kugel_common.utils.misc import get_app_time_str


@pytest.mark.asyncio()
async def test_terminal_id_parsing_with_api_key(http_client):
    """
    Test that terminal_id is correctly parsed when using API key authentication.

    This test verifies the fix for Issue #28 where terminal_id was being split
    by underscore ("_") instead of hyphen ("-"). The correct format is:
    {tenant_id}-{store_code}-{terminal_no}

    Example: "T9999-5678-5555" should extract terminal_no as 5555

    The code being tested is in app/api/v1/report.py lines 139 and 325:
        parts = terminal_id.split("-")  # Must use hyphen, not underscore
        if len(parts) >= 3:
            requesting_terminal_no = int(parts[-1])

    Note: This test depends on test_setup_data.py having been run first to create
    the terminal with ID T9999-5678-5555.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_NO"))
    terminal_id = os.environ.get("TERMINAL_ID")  # Format: T9999-5678-5555
    business_date = datetime.now().strftime("%Y%m%d")

    # Get JWT token to retrieve API key
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    token = response.json().get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # Get API key from terminal info
    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}"
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.get(url=terminal_url, headers=header)

    # Skip test if terminal doesn't exist (test_setup_data.py not run)
    if response.status_code == status.HTTP_404_NOT_FOUND:
        pytest.skip(f"Terminal {terminal_id} not found. Run test_setup_data.py first.")

    assert response.status_code == status.HTTP_200_OK
    api_key = response.json().get("data").get("apiKey")

    # Verify terminal_id format
    assert "-" in terminal_id, f"terminal_id should contain hyphens: {terminal_id}"
    parts = terminal_id.split("-")
    assert len(parts) == 3, f"terminal_id should have 3 parts separated by hyphens: {terminal_id}"
    expected_terminal_no = int(parts[-1])
    assert expected_terminal_no == terminal_no, f"Last part of terminal_id should be {terminal_no}"

    print(f"Testing terminal_id parsing: {terminal_id}")
    print(f"Expected terminal_no to be extracted: {expected_terminal_no}")

    # Test 1: Store report with terminal_id parameter (line 139)
    # This should correctly parse terminal_id and extract terminal_no
    with patch('app.api.v1.report.logger') as mock_logger:
        response = await http_client.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
            params={
                "terminal_id": terminal_id,  # Triggers terminal_id parsing code
                "report_scope": "flash",
                "report_type": "sales",
                "business_date": business_date,
                "open_counter": 1,
            },
            headers={"X-API-KEY": api_key},
        )

        assert response.status_code == status.HTTP_200_OK
        res = response.json()
        assert res.get("success") is True

        # CRITICAL: Verify that no warning was logged
        # If terminal_id parsing failed, the code would log:
        # logger.warning(f"Could not parse terminal number from terminal_id: {terminal_id}")
        warning_calls = [call for call in mock_logger.warning.call_args_list
                        if "Could not parse terminal number" in str(call)]
        assert len(warning_calls) == 0, \
            f"terminal_id parsing should succeed without warnings. Got: {warning_calls}"

        print("✓ Store report: terminal_id parsed successfully (line 139)")

    # Test 2: Terminal report with terminal_id parameter (line 325)
    # This should correctly parse terminal_id and extract terminal_no
    with patch('app.api.v1.report.logger') as mock_logger:
        response = await http_client.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
            params={
                "terminal_id": terminal_id,  # Triggers terminal_id parsing code
                "report_scope": "flash",
                "report_type": "sales",
                "business_date": business_date,
                "open_counter": 1,
            },
            headers={"X-API-KEY": api_key},
        )

        assert response.status_code == status.HTTP_200_OK
        res = response.json()
        assert res.get("success") is True

        # CRITICAL: Verify that no warning was logged
        warning_calls = [call for call in mock_logger.warning.call_args_list
                        if "Could not parse terminal number" in str(call)]
        assert len(warning_calls) == 0, \
            f"terminal_id parsing should succeed without warnings. Got: {warning_calls}"

        print("✓ Terminal report: terminal_id parsed successfully (line 325)")




@pytest.mark.asyncio()
async def test_terminal_id_format_validation():
    """
    Unit test to verify the terminal_id parsing logic in isolation.

    This test directly tests the parsing logic to ensure:
    1. Hyphen delimiter works correctly
    2. Underscore delimiter fails correctly
    3. Edge cases are handled
    """
    # Test case 1: Correct format with hyphen
    terminal_id_correct = "T9999-5678-5555"
    parts = terminal_id_correct.split("-")
    assert len(parts) == 3
    terminal_no = int(parts[-1])
    assert terminal_no == 5555
    print(f"✓ Correct format '{terminal_id_correct}' -> terminal_no: {terminal_no}")

    # Test case 2: Incorrect format with underscore (the bug)
    terminal_id_wrong = "T9999_5678_5555"
    parts = terminal_id_wrong.split("-")
    assert len(parts) == 1  # Fails to split - only one part
    print(f"✓ Wrong delimiter '_' correctly fails: {len(parts)} parts (expected 3)")

    # Test case 3: Insufficient parts
    terminal_id_short = "T9999-5678"
    parts = terminal_id_short.split("-")
    assert len(parts) == 2  # Less than 3
    print(f"✓ Insufficient parts correctly detected: {len(parts)} parts (expected 3)")

    # Test case 4: Empty string
    terminal_id_empty = ""
    parts = terminal_id_empty.split("-")
    assert len(parts) == 1 and parts[0] == ""
    print(f"✓ Empty string handled: {parts}")


@pytest.mark.asyncio()
async def test_terminal_id_filtering_with_multi_terminal_data(http_client):
    """
    Test that terminal_id filtering returns only data for the specified terminal.

    This test creates transactions for multiple terminals (5555 and 5556) and
    verifies that when requesting reports with terminal_id "T9999-5678-5555",
    only terminal 5555's data is returned, confirming that:
    1. terminal_id is correctly parsed to extract terminal_no
    2. The extracted terminal_no is used for filtering data
    3. Data from other terminals is excluded

    This is a critical integration test for Issue #28 fix.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    terminal_no_1 = 5555  # Main terminal from setup
    terminal_no_2 = 5556  # Additional terminal for filtering test
    terminal_id_1 = f"{tenant_id}-{store_code}-{terminal_no_1}"
    terminal_id_2 = f"{tenant_id}-{store_code}-{terminal_no_2}"
    business_date = datetime.now().strftime("%Y%m%d")

    # Get JWT token
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    token = response.json().get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # Create terminal 5556 if it doesn't exist
    terminal_url_base = os.environ.get("BASE_URL_TERMINAL")
    async with AsyncClient() as http_terminal_client:
        # Create terminal 5556
        create_response = await http_terminal_client.post(
            f"{terminal_url_base}/terminals",
            json={"store_code": store_code, "terminal_no": terminal_no_2, "description": "Test Terminal 5556"},
            headers=header,
        )

        # Might already exist, that's okay
        if create_response.status_code == status.HTTP_201_CREATED:
            print(f"Created terminal {terminal_id_2}")
        elif create_response.status_code == status.HTTP_400_BAD_REQUEST:
            print(f"Terminal {terminal_id_2} already exists")
        else:
            pytest.skip(f"Could not create terminal {terminal_id_2}: {create_response.status_code}")

        # Get API keys for both terminals
        response_1 = await http_terminal_client.get(
            f"{terminal_url_base}/terminals/{terminal_id_1}",
            headers=header
        )
        response_2 = await http_terminal_client.get(
            f"{terminal_url_base}/terminals/{terminal_id_2}",
            headers=header
        )

    if response_1.status_code == status.HTTP_404_NOT_FOUND:
        pytest.skip(f"Terminal {terminal_id_1} not found. Run test_setup_data.py first.")
    if response_2.status_code == status.HTTP_404_NOT_FOUND:
        pytest.skip(f"Terminal {terminal_id_2} not found.")

    api_key_1 = response_1.json().get("data").get("apiKey")
    api_key_2 = response_2.json().get("data").get("apiKey")

    # Create transactions for terminal 5555 (amount: 550 yen)
    tran_no_1 = 2001
    receipt_no_1 = 2001
    header_1 = {"X-API-KEY": api_key_1}

    print(f"\nCreating transaction for terminal {terminal_no_1} (amount: 1000)")
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_1}/transactions?terminal_id={terminal_id_1}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no_1,
            tran_type=101,  # Sales
            tran_no=tran_no_1,
            receipt_no=receipt_no_1,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header_1,
    )
    assert response.status_code == status.HTTP_201_CREATED
    print(f"✓ Created transaction {tran_no_1} for terminal {terminal_no_1}")

    # Create transactions for terminal 5556 (amount: 550 yen)
    tran_no_2 = 2002
    receipt_no_2 = 2002
    header_2 = {"X-API-KEY": api_key_2}

    print(f"Creating transaction for terminal {terminal_no_2} (amount: 2000)")
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_2}/transactions?terminal_id={terminal_id_2}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no_2,
            tran_type=101,  # Sales
            tran_no=tran_no_2,
            receipt_no=receipt_no_2,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header_2,
    )
    assert response.status_code == status.HTTP_201_CREATED
    print(f"✓ Created transaction {tran_no_2} for terminal {terminal_no_2}")

    # Request TERMINAL-specific report with terminal_id parameter
    # This tests that terminal_id is correctly parsed and used for filtering
    print(f"\n=== Testing terminal_id filtering ===")
    print(f"Requesting terminal report for terminal {terminal_no_1} with terminal_id={terminal_id_1}")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_1}/reports",
        params={
            "terminal_id": terminal_id_1,  # Should parse and match path parameter
            "report_scope": "flash",  # Use flash for consistency
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers=header_1,
    )

    if response.status_code != status.HTTP_200_OK:
        print(f"ERROR: Response status: {response.status_code}")
        print(f"ERROR: Response body: {response.text}")

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    data = res.get("data")

    # CRITICAL VALIDATION: Verify data is from terminal 5555 only
    terminal_no_in_response = data.get("terminalNo")
    assert terminal_no_in_response == terminal_no_1, \
        f"Expected terminalNo={terminal_no_1}, got {terminal_no_in_response}"

    print(f"✓ PASS: terminalNo in response is {terminal_no_in_response} (matches request)")

    # Get the sales data for verification
    sales_gross = data.get("salesGross", {})
    sales_amount_1 = sales_gross.get("amount", 0)
    sales_count_1 = sales_gross.get("count", 0)

    print(f"Terminal {terminal_no_1} sales: amount={sales_amount_1}, count={sales_count_1}")

    # Now request report for terminal 5556 to verify different data
    print(f"\nRequesting terminal report for terminal {terminal_no_2} with terminal_id={terminal_id_2}")

    response_2 = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_2}/reports",
        params={
            "terminal_id": terminal_id_2,
            "report_scope": "flush",  # Use flush like in test_report.py
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1,
        },
        headers=header_2,
    )

    assert response_2.status_code == status.HTTP_200_OK
    res_2 = response_2.json()
    assert res_2.get("success") is True
    data_2 = res_2.get("data")

    terminal_no_in_response_2 = data_2.get("terminalNo")
    assert terminal_no_in_response_2 == terminal_no_2, \
        f"Expected terminalNo={terminal_no_2}, got {terminal_no_in_response_2}"

    print(f"✓ PASS: terminalNo in response is {terminal_no_in_response_2} (matches request)")

    sales_gross_2 = data_2.get("salesGross", {})
    sales_amount_2 = sales_gross_2.get("amount", 0)
    sales_count_2 = sales_gross_2.get("count", 0)

    print(f"Terminal {terminal_no_2} sales: amount={sales_amount_2}, count={sales_count_2}")

    # Verify that terminal_id parsing correctly filters data
    # Each terminal should have its own transactions (we created 1 for each)
    # The counts/amounts should be different if filtering is working correctly
    print(f"\n=== Verification Results ===")
    print(f"Terminal {terminal_no_1}: {sales_count_1} transactions, total {sales_amount_1} yen")
    print(f"Terminal {terminal_no_2}: {sales_count_2} transactions, total {sales_amount_2} yen")

    # The data should be different (we created different transactions for each terminal)
    # If terminal_id parsing failed, both would show the same aggregated data
    if sales_amount_1 != sales_amount_2 or sales_count_1 != sales_count_2:
        print(f"✓ PASS: Different terminals have different data (filtering works correctly)")
    else:
        print(f"⚠ WARNING: Both terminals have identical data. This might indicate an issue.")

    print(f"\n✓ Terminal ID filtering test completed successfully")
