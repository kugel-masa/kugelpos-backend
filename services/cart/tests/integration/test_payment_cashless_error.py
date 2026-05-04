# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import os
import json
from fastapi import status


@pytest.mark.asyncio
async def test_cashless_payment_with_detailed_receipt_info(http_client):
    """Test cashless payment with detailed receipt info that causes 500 error"""
    
    # Environment variables
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    
    # Headers
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    # Create new cart
    cart_data = {
        "tenant_id": tenant_id,
        "terminal_id": terminal_id,
        "operator_code": "9999",
        "operator_name": "Test Operator"
    }
    
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json=cart_data,
        headers=headers
    )
    
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Cart creation failed: {response.status_code}")
        print(f"Response: {response.text}")
    assert response.status_code == status.HTTP_201_CREATED
    cart_response = response.json()
    cart_id = cart_response["data"]["cartId"]
    print(f"Created cart: {cart_id}")
    
    # Add an item to the cart
    item_data = {
        "item_code": "49-01",
        "quantity": 1
    }
    
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    print("Added item to cart")
    
    # Get cart details to check balance
    response = await http_client.get(
        f"/api/v1/carts/{cart_id}?terminal_id={terminal_id}",
        headers=headers
    )
    cart_data = response.json()
    print(f"Cart balance before payment: {cart_data['data']['balanceAmount']}")
    
    # Prepare the problematic payment request
    payment_detail = {
        "receiptInfo": {
            "businessType": 3,
            "companyCode": "00001",
            "companyName": "TEST",
            "errorCode": "",
            "errorCodeExtended": "",
            "kid": "   ",
            "merchantName": "",
            "merchantTelNo": "",
            "slipNo": 99999,
            "tid": "9999900000001",
            "totalAmount": 1650,
            "transactionDate": "2025/07/01 11:50:04",
            "transactionDetail": {
                "aid": "A0000000000000",
                "amount": 1500,
                "amount01": 0,
                "amount02": 0,
                "amount03": 0,
                "amount04": 0,
                "amount05": 0,
                "amount06": 0,
                "applicationLabel": "xxxx Credit",
                "approvalNo": "0000001",
                "arc": "99",
                "atc": "FFFF",
                "bonusCount": 0,
                "bonusMonth01": 0,
                "bonusMonth02": 0,
                "bonusMonth03": 0,
                "bonusMonth04": 0,
                "bonusMonth05": 0,
                "bonusMonth06": 0,
                "cardReadingType": 5,
                "centerErrorCode": "   ",
                "centerProcessNo": 1,
                "cvmResultType": 2,
                "electronicSign": "",
                "goodsCode": "990",
                "maskedPan": "123456******1234",
                "onOffIdentifier": False,
                "orgSlipNo": 0,
                "otherAmount": 150,
                "panSeqNo": "99",
                "paymentCount": 0,
                "paymentType": "10",
                "sgwTransactionId": "9999999999999999",
                "startMonth": 0,
                "tieUpType": "0",
                "transactionMessage": "感謝惠顧、敬請再次光臨。",
                "upiProcessDate": "2025/07/01 11:50:15",
                "upiProcessNo": "000001"
            },
            "transactionState": 1,
            "transactionType": 1
        },
        "result": 0,
        "resultExtended": 0,
        "transactionSequenceNo": 55
    }
    
    # Convert detail to JSON string
    payment_request = [{
        "payment_code": "11",  # Note: API expects snake_case
        "amount": 1650,
        "detail": json.dumps(payment_detail, ensure_ascii=False)
    }]
    
    print(f"Payment request: {json.dumps(payment_request, indent=2, ensure_ascii=False)}")
    
    # Send the payment request
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=payment_request,
        headers=headers
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    # This is where we expect the 406 error
    if response.status_code == status.HTTP_406_NOT_ACCEPTABLE:
        print("Reproduced the 406 error!")
        print(f"Error details: {response.json()}")
        
        # For debugging, let's also check the cart status
        status_response = await http_client.get(
            f"/api/v1/carts/{cart_id}",
            headers=headers
        )
        print(f"Cart status after error: {status_response.json()}")
    else:
        # If it doesn't fail, that's also useful information
        print(f"Unexpected status code: {response.status_code}")
        print(f"Response: {response.json()}")


@pytest.mark.asyncio
async def test_cashless_payment_simple(http_client):
    """Test cashless payment with minimal detail to isolate the issue"""
    
    # Environment variables
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    
    # Headers
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    # Create new cart
    cart_data = {
        "tenant_id": tenant_id,
        "terminal_id": terminal_id,
        "operator_code": "9999",
        "operator_name": "Test Operator"
    }
    
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json=cart_data,
        headers=headers
    )
    
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Cart creation failed: {response.status_code}")
        print(f"Response: {response.text}")
    assert response.status_code == status.HTTP_201_CREATED
    cart_response = response.json()
    cart_id = cart_response["data"]["cartId"]
    
    # Add an item
    item_data = {
        "item_code": "49-01",
        "quantity": 1
    }
    
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Get cart details to check balance
    response = await http_client.get(
        f"/api/v1/carts/{cart_id}?terminal_id={terminal_id}",
        headers=headers
    )
    cart_data = response.json()
    print(f"Cart balance before payment: {cart_data['data']['balanceAmount']}")
    
    # Simple payment without detail
    payment_request = [{
        "payment_code": "11",
        "amount": cart_data['data']['balanceAmount']  # Use exact balance
    }]
    
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=payment_request,
        headers=headers
    )
    
    print(f"Simple payment response status: {response.status_code}")
    print(f"Simple payment response: {response.text}")


@pytest.mark.asyncio
async def test_cashless_payment_with_wrong_case(http_client):
    """Test cashless payment with camelCase field names (original request format)"""
    
    # Environment variables
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    
    # Headers
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    # Create new cart
    cart_data = {
        "tenant_id": tenant_id,
        "terminal_id": terminal_id,
        "operator_code": "9999",
        "operator_name": "Test Operator"
    }
    
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json=cart_data,
        headers=headers
    )
    
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Cart creation failed: {response.status_code}")
        print(f"Response: {response.text}")
    assert response.status_code == status.HTTP_201_CREATED
    cart_response = response.json()
    cart_id = cart_response["data"]["cartId"]
    
    # Add an item
    item_data = {
        "item_code": "49-01",
        "quantity": 1
    }
    
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Payment request with camelCase (as in original request)
    payment_request = [{
        "paymentCode": "11",  # camelCase instead of snake_case
        "amount": 1650,
        "detail": "{\"receiptInfo\":{\"businessType\":3}}"  # Simple detail
    }]
    
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=payment_request,
        headers=headers
    )
    
    print(f"CamelCase payment response status: {response.status_code}")
    print(f"CamelCase payment response: {response.text}")
    
    # This should cause validation error (422) due to wrong field names