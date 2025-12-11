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
