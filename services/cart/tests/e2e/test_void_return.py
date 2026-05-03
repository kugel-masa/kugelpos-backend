# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import os
from fastapi import status
from httpx import AsyncClient


# ヘルパー関数 - 認証トークンの取得
async def get_authentication_token():
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}

    async with AsyncClient() as http_auth_client:
        response = await http_auth_client.post(url=token_url, data=login_data)
        assert response.status_code == status.HTTP_200_OK
        return response.json().get("access_token")


# ヘルパー関数 - ターミナル情報の取得
def get_terminal_info():
    terminal_id = os.environ.get("TERMINAL_ID")
    tenant_id = os.environ.get("TENANT_ID")
    # Extract store_code and terminal_no from terminal_id (format: TENANT-STORE-TERMNO)
    parts = terminal_id.split("-")
    store_code = parts[1] if len(parts) > 1 else "5678"
    terminal_no = int(parts[2]) if len(parts) > 2 else 9
    return terminal_id, tenant_id, store_code, terminal_no


# ヘルパー関数 - APIキーの取得
async def get_api_key(http_client, token):
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    base_url = os.environ.get("BASE_URL_TERMINAL")

    header = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(base_url=base_url) as terminal_client:
        response = await terminal_client.get(f"/terminals/{terminal_id}", headers=header)

    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        return res.get("data", {}).get("apiKey")
    return None


# ヘルパー関数 - カートの作成と商品追加
async def create_cart_with_items(http_client, api_key):
    terminal_id = os.environ.get("TERMINAL_ID")
    header = {"X-API-KEY": api_key}

    # カート作成
    cart_data = {"transaction_type": 101, "user_id": "99", "user_name": "John Doe"}

    response = await http_client.post(f"/api/v1/carts?terminal_id={terminal_id}", json=cart_data, headers=header)
    assert response.status_code == status.HTTP_201_CREATED
    cart_id = response.json().get("data", {}).get("cartId")

    # 商品追加
    items_data = [{"itemCode": "49-01", "quantity": 2}]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}", json=items_data, headers=header
    )
    assert response.status_code == status.HTTP_200_OK

    # 小計
    response = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK

    # 支払い追加
    payment_data = [{"paymentCode": "01", "amount": 1000, "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}", json=payment_data, headers=header
    )
    assert response.status_code == status.HTTP_200_OK

    # 精算
    response = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK

    return response.json().get("data", {})


# Test: 重複取消の防止
@pytest.mark.asyncio
async def test_duplicate_void_prevention(http_client: AsyncClient):
    """
    Test that void operation cannot be performed twice on the same transaction
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Create and complete a transaction
    cart_data = await create_cart_with_items(http_client, api_key)
    transaction_no = cart_data.get("transactionNo")

    # First void - should succeed
    void_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    # Get the void transaction number
    void_transaction_no = res.get("data", {}).get("transactionNo")

    # Verify the void transaction doesn't have is_voided flag set
    # (void transactions themselves don't have these flags)
    assert res.get("data", {}).get("status", {}).get("isVoided") is False
    assert res.get("data", {}).get("status", {}).get("isRefunded") is False

    # Second void attempt on the same original transaction - should fail
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    assert res.get("success") is False
    # Check error message in user_error field
    user_error = res.get("userError", {})
    assert (
        "already been voided" in user_error.get("message", "").lower()
        or "already been voided" in res.get("message", "").lower()
    )


# Test: 重複返品の防止
@pytest.mark.asyncio
async def test_duplicate_return_prevention(http_client: AsyncClient):
    """
    Test that return operation cannot be performed twice on the same transaction
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Create and complete a transaction
    cart_data = await create_cart_with_items(http_client, api_key)
    transaction_no = cart_data.get("transactionNo")

    # First return - should succeed
    return_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return?terminal_id={terminal_id}",
        json=return_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    # Get the return transaction number
    return_transaction_no = res.get("data", {}).get("transactionNo")

    # Second return attempt on the same original transaction - should fail
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return?terminal_id={terminal_id}",
        json=return_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    assert res.get("success") is False
    # Check error message in user_error field
    user_error = res.get("userError", {})
    assert (
        "already been refunded" in user_error.get("message", "").lower()
        or "already been refunded" in res.get("message", "").lower()
    )


# Test: 取消済み取引の返品防止
@pytest.mark.asyncio
async def test_return_voided_transaction_prevention(http_client: AsyncClient):
    """
    Test that return operation cannot be performed on a voided transaction
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Create and complete a transaction
    cart_data = await create_cart_with_items(http_client, api_key)
    transaction_no = cart_data.get("transactionNo")

    # Void the transaction first
    void_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Try to return the voided transaction - should fail
    return_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return?terminal_id={terminal_id}",
        json=return_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    assert res.get("success") is False
    # Check error message in user_error field
    user_error = res.get("userError", {})
    assert (
        "already been voided" in user_error.get("message", "").lower()
        or "already been voided" in res.get("message", "").lower()
    )


# Test: 返品済み取引の取消防止
@pytest.mark.asyncio
async def test_void_returned_transaction_prevention(http_client: AsyncClient):
    """
    Test that void operation cannot be performed on a returned transaction
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Create and complete a transaction
    cart_data = await create_cart_with_items(http_client, api_key)
    transaction_no = cart_data.get("transactionNo")

    # Return the transaction first
    return_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return?terminal_id={terminal_id}",
        json=return_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Try to void the returned transaction - should fail
    void_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    assert res.get("success") is False
    # Check error message in user_error field
    user_error = res.get("userError", {})
    assert (
        "already been refunded" in user_error.get("message", "").lower()
        or "already been refunded" in res.get("message", "").lower()
    )


# Test: 取引一覧でのステータス反映確認
@pytest.mark.asyncio
async def test_transaction_status_in_list(http_client: AsyncClient):
    """
    Test that void/return status is properly reflected in transaction list
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Create multiple transactions
    transaction_nos = []
    cart_data_list = []
    for i in range(3):
        cart_data = await create_cart_with_items(http_client, api_key)
        transaction_nos.append(cart_data.get("transactionNo"))
        cart_data_list.append(cart_data)

    # Void the first transaction
    void_data = [
        {"paymentCode": "01", "amount": cart_data_list[0].get("totalAmountWithTax", 220), "detail": "Cash payment"}
    ]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_nos[0]}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Return the second transaction
    return_data = [
        {"paymentCode": "01", "amount": cart_data_list[1].get("totalAmountWithTax", 220), "detail": "Cash payment"}
    ]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_nos[1]}/return?terminal_id={terminal_id}",
        json=return_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Get transaction list
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}&limit=10&page=1",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    # Find our transactions in the list
    transactions = res.get("data", [])
    our_transactions = {}
    for tran in transactions:
        if tran.get("transactionNo") in transaction_nos:
            our_transactions[tran.get("transactionNo")] = tran

    # Verify status flags
    # First transaction should be marked as voided
    assert our_transactions[transaction_nos[0]].get("status", {}).get("isVoided") is True
    assert our_transactions[transaction_nos[0]].get("status", {}).get("isRefunded") is False

    # Second transaction should be marked as refunded
    assert our_transactions[transaction_nos[1]].get("status", {}).get("isVoided") is False
    assert our_transactions[transaction_nos[1]].get("status", {}).get("isRefunded") is True

    # Third transaction should have both flags as false
    assert our_transactions[transaction_nos[2]].get("status", {}).get("isVoided") is False
    assert our_transactions[transaction_nos[2]].get("status", {}).get("isRefunded") is False


# Test: 単一取引取得でのステータス反映確認
@pytest.mark.asyncio
async def test_transaction_status_in_single_get(http_client: AsyncClient):
    """
    Test that void/return status is properly reflected when getting a single transaction
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Create and complete a transaction
    cart_data = await create_cart_with_items(http_client, api_key)
    transaction_no = cart_data.get("transactionNo")

    # Get the transaction - should have both flags as false
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data", {}).get("status", {}).get("isVoided") is False
    assert res.get("data", {}).get("status", {}).get("isRefunded") is False

    # Void the transaction
    void_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Get the transaction again - should now show as voided
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data", {}).get("status", {}).get("isVoided") is True
    assert res.get("data", {}).get("status", {}).get("isRefunded") is False


# Test: 返品取引の取消で元売上の返品ステータスがリセットされることを確認
@pytest.mark.asyncio
async def test_void_return_resets_original_refund_status(http_client: AsyncClient):
    """
    Test that voiding a return transaction resets the original sale's refund status.
    This tests the fix for issue #98.
    """
    # Setup
    token = await get_authentication_token()
    api_key = await get_api_key(http_client, token)

    if not api_key:
        pytest.skip("API key not available")

    # Get terminal info from environment
    terminal_id, tenant_id, store_code, terminal_no = get_terminal_info()

    header = {"X-API-KEY": api_key}

    # Step 1: Create and complete an original sales transaction
    cart_data = await create_cart_with_items(http_client, api_key)
    original_transaction_no = cart_data.get("transactionNo")

    # Verify original transaction has no void/refund status
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{original_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data", {}).get("status", {}).get("isVoided") is False
    assert res.get("data", {}).get("status", {}).get("isRefunded") is False

    # Step 2: Process a return for the original transaction
    return_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash return"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{original_transaction_no}/return?terminal_id={terminal_id}",
        json=return_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    return_res = response.json()
    return_transaction_no = return_res.get("data", {}).get("transactionNo")

    # Verify original transaction is now marked as refunded
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{original_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data", {}).get("status", {}).get("isVoided") is False
    assert res.get("data", {}).get("status", {}).get("isRefunded") is True

    # Step 3: Void the return transaction
    void_data = [{"paymentCode": "01", "amount": cart_data.get("totalAmountWithTax", 220), "detail": "Cash payment"}]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_transaction_no}/void?terminal_id={terminal_id}",
        json=void_data,
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    void_res = response.json()
    void_transaction_no = void_res.get("data", {}).get("transactionNo")

    # Verify the return transaction is marked as voided
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data", {}).get("status", {}).get("isVoided") is True

    # Step 4: CRITICAL TEST - Verify original transaction's refund status is reset
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{original_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    # Original transaction should no longer be marked as refunded since the return was voided
    assert res.get("data", {}).get("status", {}).get("isVoided") is False
    assert res.get("data", {}).get("status", {}).get("isRefunded") is False  # This should be reset!

    # Also verify in transaction list
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    transactions_list = response.json().get("data", [])

    # Find our transactions in the list
    our_transactions = {
        t["transactionNo"]: t
        for t in transactions_list
        if t["transactionNo"] in [original_transaction_no, return_transaction_no, void_transaction_no]
    }

    # Verify statuses in list view
    assert our_transactions[original_transaction_no].get("status", {}).get("isVoided") is False
    assert our_transactions[original_transaction_no].get("status", {}).get("isRefunded") is False  # Reset!
    assert our_transactions[return_transaction_no].get("status", {}).get("isVoided") is True
    assert our_transactions[return_transaction_no].get("status", {}).get("isRefunded") is False
