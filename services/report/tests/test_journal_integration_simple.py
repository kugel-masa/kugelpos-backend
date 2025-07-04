#!/usr/bin/env python
"""
Simple script to test journal integration with API key requests.
This helps debug why journal entries are not being created.
"""
import asyncio
import os
from httpx import AsyncClient
from datetime import datetime


async def test_api_key_journal_integration():
    # Get environment variables
    tenant_id = os.environ.get("TENANT_ID", "kugel")
    store_code = os.environ.get("STORE_CODE", "S001")
    terminal_no = int(os.environ.get("TERMINAL_NO", "1"))
    terminal_id = os.environ.get("TERMINAL_ID", f"{tenant_id}_{store_code}_{terminal_no}")
    business_date = datetime.now().strftime("%Y%m%d")
    base_url_report = os.environ.get("BASE_URL_REPORT", "http://localhost:8004")
    base_url_terminal = os.environ.get("BASE_URL_TERMINAL", "http://localhost:8001")
    token_url = os.environ.get("TOKEN_URL", "http://localhost:8000/api/v1/auth/token")

    print(
        f"Testing with: tenant_id={tenant_id}, store_code={store_code}, terminal_no={terminal_no}, terminal_id={terminal_id}"
    )

    # Step 1: Get JWT token
    print("\n1. Getting JWT token...")
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as client:
        response = await client.post(url=token_url, data=login_data)

    if response.status_code != 200:
        print(f"Failed to get token: {response.status_code} - {response.text}")
        return

    token = response.json().get("access_token")
    headers_jwt = {"Authorization": f"Bearer {token}"}
    print(f"Got token: {token[:20]}...")

    # Step 2: Get API key for terminal
    print("\n2. Getting API key for terminal...")
    async with AsyncClient() as client:
        response = await client.get(f"{base_url_terminal}/terminals/{terminal_id}", headers=headers_jwt)

    if response.status_code != 200:
        print(f"Failed to get terminal info: {response.status_code} - {response.text}")
        return

    api_key = response.json()["data"]["apiKey"]
    headers_api = {"X-API-KEY": api_key}
    print(f"Got API key: {api_key[:20]}...")

    # Step 3: Test JWT request (should NOT create journal)
    print("\n3. Testing JWT request (should NOT create journal)...")
    async with AsyncClient() as client:
        response = await client.get(
            f"{base_url_report}/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
            params={
                "report_scope": "flash",
                "report_type": "sales",
                "business_date": business_date,
                "open_counter": 1,
                "business_counter": 1,
            },
            headers=headers_jwt,
        )

    print(f"JWT request status: {response.status_code}")
    if response.status_code == 200:
        print("JWT request successful - journal should NOT be created")
    else:
        print(f"JWT request failed: {response.text}")

    # Step 4: Test API key request (SHOULD create journal)
    print("\n4. Testing API key request (SHOULD create journal)...")
    async with AsyncClient() as client:
        response = await client.get(
            f"{base_url_report}/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
            params={
                "terminal_id": terminal_id,  # This is the key difference!
                "report_scope": "flash",
                "report_type": "sales",
                "business_date": business_date,
                "open_counter": 1,
                "business_counter": 1,
            },
            headers=headers_api,
        )

    print(f"API key request status: {response.status_code}")
    if response.status_code == 200:
        print("API key request successful - journal SHOULD be created")
        data = response.json()["data"]
        print(f"Report generated with receiptText length: {len(data.get('receiptText', ''))}")
    else:
        print(f"API key request failed: {response.text}")

    # Step 5: Check logs for journal creation
    print("\n5. Check docker logs for journal creation:")
    print("Run: docker-compose logs report | grep -i journal")
    print("Look for: 'API key request detected' and 'Report sent to journal successfully'")

    # Step 6: Check journal database
    print("\n6. Check journal database:")
    print("Run: docker exec -it mongodb mongosh")
    print("Then: use kugel_journal")
    print("Then: db.journals.find({transactionType: {$in: [501, 502]}}).sort({generateDateTime: -1}).limit(5)")


if __name__ == "__main__":
    asyncio.run(test_api_key_journal_integration())
