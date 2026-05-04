# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Register tenant-level master-data settings (INVOICE_REGISTRATION_NUMBER,
RECEIPT_HEADERS, RECEIPT_FOOTERS) used by other cart e2e tests.

Lives in the e2e tier because it talks to a real account service (for the
admin JWT) and a real master-data service (to POST settings). The
integration tier mocks master-data and uses locally-generated JWTs, so
this kind of cross-service registration belongs here, not there.
"""
import os

import pytest
from fastapi import status
from httpx import AsyncClient


async def _register_setting(tenant_id: str, token: str, name: str, default_value, values: list):
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    header = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": name,
        "defaultValue": default_value,
        "values": values,
    }

    async with AsyncClient() as client:
        response = await client.post(
            f"{base_url}/tenants/{tenant_id}/settings", json=payload, headers=header
        )
        return response.json()


@pytest.mark.asyncio
async def test_register_invoice_number(set_env_vars):
    """Register INVOICE_REGISTRATION_NUMBER, RECEIPT_HEADERS, and
    RECEIPT_FOOTERS settings on master-data. Idempotent: a 400 "already
    exists" response is treated as success so the test can be re-run."""
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}

    async with AsyncClient() as http_auth_client:
        response = await http_auth_client.post(url=token_url, data=login_data)
        assert response.status_code == status.HTTP_200_OK
        token = response.json().get("access_token")
        assert token is not None

    store_code = os.environ.get("STORE_CODE")
    terminal_no = 9

    invoice_values = [
        {"storeCode": store_code, "terminalNo": terminal_no, "value": "T1234567890123"},
        {"storeCode": store_code, "value": "T1234567890111"},
    ]
    result = await _register_setting(
        tenant_id, token, "INVOICE_REGISTRATION_NUMBER", "T999999999999", invoice_values
    )
    if result.get("code") == status.HTTP_400_BAD_REQUEST:
        assert "already exists" in result.get("message", "")
    else:
        assert result.get("success") is True
        assert result.get("code") == status.HTTP_201_CREATED
        assert result.get("data").get("name") == "INVOICE_REGISTRATION_NUMBER"
        assert result.get("data").get("defaultValue") == "T999999999999"
        assert result.get("data").get("values")[0].get("storeCode") == store_code
        assert result.get("data").get("values")[0].get("terminalNo") == terminal_no
        assert result.get("data").get("values")[0].get("value") == "T1234567890123"

    header_default = [
        {"text": "header1", "align": "left"},
        {"text": "header2", "align": "center"},
        {"text": "header3", "align": "right"},
    ]
    header_terminal = [
        {"text": "terminal header1", "align": "left"},
        {"text": "terminal header2", "align": "center"},
        {"text": "terminal header3", "align": "right"},
    ]
    header_store = [
        {"text": "store header1", "align": "left"},
        {"text": "store header2", "align": "center"},
        {"text": "store header3", "align": "right"},
    ]
    receipt_header_values = [
        {"storeCode": store_code, "terminalNo": terminal_no, "value": str(header_terminal)},
        {"storeCode": store_code, "value": str(header_store)},
    ]
    result = await _register_setting(
        tenant_id, token, "RECEIPT_HEADERS", str(header_default), receipt_header_values
    )
    if result.get("code") == status.HTTP_400_BAD_REQUEST:
        assert "already exists" in result.get("message", "")
    else:
        assert result.get("success") is True
        assert result.get("code") == status.HTTP_201_CREATED

    footer_default = [
        {"text": "footer1", "align": "left"},
        {"text": "footer2", "align": "center"},
        {"text": "footer3", "align": "right"},
    ]
    footer_terminal = [
        {"text": "terminal footer1", "align": "left"},
        {"text": "terminal footer2", "align": "center"},
        {"text": "terminal footer3", "align": "right"},
    ]
    footer_store = [
        {"text": "store footer1", "align": "left"},
        {"text": "store footer2", "align": "center"},
        {"text": "store footer3", "align": "right"},
    ]
    receipt_footer_values = [
        {"storeCode": store_code, "terminalNo": terminal_no, "value": str(footer_terminal)},
        {"storeCode": store_code, "value": str(footer_store)},
    ]
    result = await _register_setting(
        tenant_id, token, "RECEIPT_FOOTERS", str(footer_default), receipt_footer_values
    )
    if result.get("code") == status.HTTP_400_BAD_REQUEST:
        assert "already exists" in result.get("message", "")
    else:
        assert result.get("success") is True
        assert result.get("code") == status.HTTP_201_CREATED
