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
import pytest, os, asyncio
from fastapi import status
from app.enums.cart_status import CartStatus
from httpx import AsyncClient

# ヘルパー関数 - 認証トークンの取得
async def get_authentication_token():
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    
    try:
        async with AsyncClient() as http_auth_client:
            response = await http_auth_client.post(url=token_url, data=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        res = response.json()
        print(f"Auth Response: {res}")
        token = res.get("access_token")
        print(f"Token: {token}")
        return token
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        raise e

# ヘルパー関数 - テナント作成
async def create_tenant(http_client, token):
    tenant_id = os.environ.get("TENANT_ID")
    req_data = {"tenant_id": tenant_id}
    header = {"Authorization": f"Bearer {token}"}
    
    try:
        response = await http_client.post("/api/v1/tenants", json=req_data, headers=header)
        
        if response.status_code == status.HTTP_201_CREATED:
            res = response.json()
            assert res.get("success") == True
            assert res.get("code") == status.HTTP_201_CREATED
            assert res.get("data").get("tenantId") == tenant_id
            return tenant_id
        elif response.status_code == status.HTTP_409_CONFLICT:
            # テナントが既に存在する場合も成功とみなす
            print(f"Tenant {tenant_id} already exists")
            return tenant_id
        else:
            print(f"Failed to create tenant: {response.status_code} {response.text}")
            raise Exception(f"Failed to create tenant: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Tenant creation error: {str(e)}")
        raise e

# ヘルパー関数 - ターミナル情報取得
async def get_terminal_info(tenant_id=None):
    if (tenant_id is None):
        tenant_id = os.environ.get("TENANT_ID")
    
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")
    
    try:
        async with AsyncClient(base_url=base_url) as http_terminal_client:
            response = await http_terminal_client.get(f"/terminals/{terminal_id}", headers=header)
        
        assert response.status_code == status.HTTP_200_OK
        res = response.json()
        print(f"Terminal Info Response: {res}")
        assert res.get("success") == True
        assert res.get("code") == status.HTTP_200_OK
        assert res.get("data").get("terminalId") == terminal_id
        
        return res.get("data")
    except Exception as e:
        print(f"Terminal info error: {str(e)}")
        raise e

# ヘルパー関数 - ターミナルのオープン処理
async def open_terminal(tenant_id=None):
    if (tenant_id is None):
        tenant_id = os.environ.get("TENANT_ID")
    
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")
    
    # 機能モードをOpenTerminalに変更
    req_data = {"function_mode": "OpenTerminal"}
    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.patch(
            f"/terminals/{terminal_id}/function_mode", json=req_data, headers=header
        )
    
    if (response.status_code != status.HTTP_200_OK):
        print(f"Failed to set function mode: {response.status_code} {response.text}")
    
    # サインイン
    req_data = {"staff_id": "S001"}
    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.post(
            f"/terminals/{terminal_id}/sign-in", json=req_data, headers=header
        )
    
    if (response.status_code != status.HTTP_200_OK):
        print(f"Failed to sign in: {response.status_code} {response.text}")
    
    # ターミナルオープン
    req_data = {"initial_amount": 500000}
    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.post(
            f"/terminals/{terminal_id}/open", json=req_data, headers=header
        )
    
    if (response.status_code != status.HTTP_200_OK):
        print(f"Failed to open terminal: {response.status_code} {response.text}")
    
    # 機能モードをSalesに変更
    req_data = {"function_mode": "Sales"}
    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.patch(
            f"/terminals/{terminal_id}/function_mode", json=req_data, headers=header
        )
    
    if (response.status_code != status.HTTP_200_OK):
        print(f"Failed to set function mode to Sales: {response.status_code} {response.text}")
    
    return terminal_id

# ヘルパー関数 - ターミナルのクローズ処理
async def close_terminal(tenant_id=None):
    if (tenant_id is None):
        tenant_id = os.environ.get("TENANT_ID")
    
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")
    
    # ターミナルクローズ
    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.post(
            f"/terminals/{terminal_id}/close", headers=header
        )
    
    if (response.status_code != status.HTTP_200_OK):
        print(f"Failed to close terminal: {response.status_code} {response.text}")
    
    # サインアウト
    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.post(
            f"/terminals/{terminal_id}/sign-out", headers=header
        )
    
    if (response.status_code != status.HTTP_200_OK):
        print(f"Failed to sign out: {response.status_code} {response.text}")
    
    return terminal_id

@pytest.mark.asyncio
async def drop_test_database(set_env_vars):
    """テスト用のデータベースをドロップする"""
    from kugel_common.database import database as db_helper
    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    
    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    
    if target_db_name in await db_client.list_database_names():
        print(f"Dropping existing test database: {target_db_name}")
        await db_client.drop_database(target_db_name)
    else:
        print(f"No existing test database found: {target_db_name}")

@pytest.mark.asyncio
async def setup_data_tranlog(set_env_vars):
    from tests.setup_data import setup_data_tranlog
    """トランザクションログのセットアップ"""
    tranlog_created = await setup_data_tranlog()

@pytest.mark.asyncio
async def setup_data_invoice_number(set_env_vars):
    from tests.setup_data import setup_data_invoice_number
    """INVOICE_REGISTRATION_NUMBERのセットアップ"""
    invoice_number_created = await setup_data_invoice_number()

# メインのテスト - カート操作の基本テスト
@pytest.mark.asyncio
async def test_cart_operations(http_client):
    """カートの基本的な操作テスト"""
    print("Testing cart operations started")

    # 認証トークンの取得
    token = await get_authentication_token()
    
    # テナント作成
    tenant_id = await create_tenant(http_client, token)
    
    # ターミナル情報の取得
    terminal_info = await get_terminal_info(tenant_id)
    store_code = terminal_info['storeCode']
    terminal_no = terminal_info['terminalNo']
    terminal_id = terminal_info['terminalId']
    
    # ターミナルが既にOpenedでない場合のみ、オープンプロセスを実行する
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    else:
        print(f"Terminal is already opened with status: {current_status}")
    
    # API キーをヘッダーに設定
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    assert res.get("success") == True
    cartId = res.get("data").get("cartId")
    assert cartId is not None
    
    # カートの取得
    response = await http_client.get(
        f"/api/v1/carts/{cartId}?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    cart = res.get("data")
    assert cart.get("cartId") == cartId
    assert cart.get("cartStatus") == CartStatus.Idle.value
    assert cart.get("tenantId") == tenant_id
    assert cart.get("storeCode") == store_code
    assert cart.get("terminalNo") == terminal_no
    
    # カートのキャンセル
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("cartId") == cartId
    assert res.get("data").get("cartStatus") == CartStatus.Cancelled.value
    
    print("Basic cart operations test completed")

# 商品操作のテスト
@pytest.mark.asyncio
async def test_line_item_operations(http_client):
    """商品操作（追加、数量変更、キャンセル）のテスト"""
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # 新しいカートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("cartStatus") == CartStatus.EnteringItem.value
    assert res.get("data").get("lineItems")[0].get("isCancelled") == False
    
    # 商品の数量変更
    lineNo = 1
    response = await http_client.patch(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/quantity?terminal_id={terminal_id}",
        json={"quantity": 3},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("lineItems")[0].get("quantity") == 3
    
    # 特定単価での商品追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1, "unitPrice": 88}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("lineItems")[1].get("unitPrice") == 88
    
    # 商品の単価変更
    lineNo = 2
    response = await http_client.patch(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/unitPrice?terminal_id={terminal_id}",
        json={"unitPrice": 95},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("lineItems")[1].get("unitPrice") == 95
    assert res.get("data").get("lineItems")[1].get("isUnitPriceChanged") == True
    
    # 商品のキャンセル
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/cancel?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("lineItems")[1].get("isCancelled") == True
    
    # カートをキャンセルして終了
    await http_client.post(
        f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header
    )
    
    print("Line item operations test completed")

# 割引処理のテスト
@pytest.mark.asyncio
async def test_discount_operations(http_client):
    """割引処理（商品割引、小計割引）のテスト"""
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 商品に金額割引を追加（detailフィールドに割引理由を追加）
    lineNo = 1
    line_discount_detail = "{ discountReason : 'ポイント値引き' }"
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 10, "discountDetail": line_discount_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountType") == "DiscountAmount"
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountValue") == 10
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountAmount") == 10
    # detailフィールドの値を確認
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountDetail") == line_discount_detail
    
    # 別の商品を追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-02", "quantity": 3}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 商品にパーセント割引を追加
    lineNo = 2
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountPercentage", "discountValue": 10}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("lineItems")[1].get("discounts")[0].get("discountType") == "DiscountPercentage"
    
    # 小計処理を実行
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 小計に金額割引を追加（detailフィールドにポイント値引き情報を追加）
    discount_detail = "{ discountReason : 'ポイント値引き' }"
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 50, "discountDetail": discount_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("subtotalDiscounts")[0].get("discountType") == "DiscountAmount"
    assert res.get("data").get("subtotalDiscounts")[0].get("discountValue") == 50
    assert res.get("data").get("subtotalDiscounts")[0].get("discountDetail") == discount_detail
    
    # 小計割引を上書き
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 100, "discountDetail": discount_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("subtotalDiscounts")[0].get("discountValue") == 100
    assert res.get("data").get("subtotalDiscounts")[0].get("discountDetail") == discount_detail
    
    # カートをキャンセルして終了
    await http_client.post(
        f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header
    )
    
    print("Discount operations test completed")

# 支払いと請求処理のテスト
@pytest.mark.asyncio
async def test_payment_process(http_client):
    """支払いと請求処理のテスト"""
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 小計処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    total_amount = res.get("data").get("totalAmountWithTax")
    
    # 一部支払い（残高不足）
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 100, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 残高不足での請求処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    
    # 追加支払い（キャッシュレス）
    detail_data = str({"card_no": "1234567890"})
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "11", "amount": 50, "detail": detail_data}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # さらに支払いを追加（残高を超える）
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 1000, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 請求処理（成功）
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value
    
    # お釣りの確認
    assert res.get("data").get("totalAmountWithTax") < res.get("data").get("depositAmount")
    assert res.get("data").get("changeAmount") > 0
    
    print("Payment process test completed")

# 残高不足時の請求処理テスト
@pytest.mark.asyncio
async def test_bill_with_insufficient_balance(http_client):
    """残高不足での請求処理をテスト"""
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 3}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 小計処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 一部支払い（残高不足）
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 50, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 残高不足での請求処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    
    # カートをキャンセルして終了
    await http_client.post(
        f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header
    )
    
    print("Insufficient balance test completed")

# 印紙税のテスト stamp duty
@pytest.mark.asyncio
async def test_stamp_duty(http_client):
    # 5万円以上の取引を行い、印紙税が適用されることを確認するテスト

    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    store_code = terminal_info['storeCode']
    terminal_no = terminal_info['terminalNo']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成と取引完了
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")

    # 商品を追加
    await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 500}],
        headers=header,
    )

    # 小計処理
    await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )

    # 支払い
    await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 60000, "detail": "Cash payment"}],
        headers=header,
    )

    # 請求処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True

    # 印紙税が適用されていることを確認
    assert res.get("data").get("stampDutyAmount") == 200
    print(f"journal data stamp duty: {res.get('data').get('journalText')}")


# トランザクション操作のテスト
@pytest.mark.asyncio
async def test_transaction_operations(http_client):
    """トランザクション操作（返品、取消など）のテスト"""
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    store_code = terminal_info['storeCode']
    terminal_no = terminal_info['terminalNo']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成と取引完了
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加
    await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )

    # 商品の追加
    await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=header,
    )
    
    # 小計処理
    await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )
    
    # 支払い
    await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 1000, "detail": "Cash payment"}],
        headers=header,
    )
    
    # 請求処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    transaction_no = response.json().get("data").get("transactionNo")
    res = response.json()
    assert res.get("success") == True
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0
    print(f"Journal data NornalSales: {journal_data}")
    
    # トランザクション一覧取得
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert len(res.get("data")) > 0
    for tran in res.get("data"):
        journal_data = tran.get("journalText")
        assert journal_data is not None
        assert len(journal_data) > 0
        print(f"Journal data: {journal_data}")
    
    # パラメータ付きでトランザクション一覧取得
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions",
        params={
            "terminal_id": terminal_id, 
            "limit": 10, 
            "page": 1, 
            "sort": "business_date:-1,transaction_no:1",
            "transaction_type": [101],
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True

    # トランザクション詳細取得
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("transactionNo") == transaction_no
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None 
    assert len(journal_data) > 0
    print(f"Journal data: {journal_data}")
    
    # 取引返品処理
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return?terminal_id={terminal_id}",
        headers=header,
        json=[{"paymentCode": "01", "amount": 330, "detail": "Cash payment"}],
    )
    
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    return_transaction_no = res.get("data").get("transactionNo")
    
    # 返品したトランザクション詳細取得
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0
    print(f"Journal data Return: {journal_data}")
    
    # 返品取引取消処理
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_transaction_no}/void?terminal_id={terminal_id}",
        headers=header,
        json=[
            {"paymentCode": "01", "amount": 330, "detail": "Cash payment"},
        ],
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    void_transaction_no = res.get("data").get("transactionNo")
    
    # 取消したトランザクション詳細取得
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{void_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0
    print(f"Journal data VoidReturn: {journal_data}")
    
    print("Transaction operations test completed")

# その他支払いのテスト
@pytest.mark.asyncio
async def test_payment_by_others(http_client):
    """「その他」支払い方法のテスト"""
    print("Testing payment by others started")
    
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 小計処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    total_amount = res.get("data").get("totalAmountWithTax")
    
    # その他支払い（コード12）
    others_detail = "{ paymentMethod: '商品券', voucherNumber: 'ABC123' }"
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "12", "amount": total_amount, "detail": others_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    
    # 支払いが正しく追加されていることを確認
    assert res.get("success") == True
    payments = res.get("data").get("payments")
    assert len(payments) > 0
    
    # 「その他」支払いの検証
    others_payment = next((p for p in payments if p.get("paymentCode") == "12"), None)
    assert others_payment is not None
    assert others_payment.get("paymentAmount") == total_amount
    assert others_payment.get("paymentDetail") == others_detail
    
    # 請求処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value
    
    # 取引の詳細を取得して確認
    transaction_no = res.get("data").get("transactionNo")
    store_code = terminal_info['storeCode'] 
    terminal_no = terminal_info['terminalNo']
    
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    
    # 「その他」支払いが取引に記録されているか確認
    payments = res.get("data").get("payments")
    others_payment = next((p for p in payments if p.get("paymentCode") == "12"), None)
    assert others_payment is not None
    assert others_payment.get("paymentAmount") == total_amount
    assert others_payment.get("paymentDetail") == others_detail
    
    print("Testing payment by others completed")

# 複数支払い方法のテスト
@pytest.mark.asyncio
async def test_multiple_payment_methods(http_client):
    """複数の支払い方法（現金、キャッシュレス、その他）を組み合わせたテスト"""
    print("Testing multiple payment methods started")
    
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    store_code = terminal_info['storeCode']
    terminal_no = terminal_info['terminalNo']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if (current_status != 'Opened'):
        await open_terminal(tenant_id)
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 商品の追加（価格が高めの商品を複数追加）
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 10}],  # 100円 x 10個 = 1,000円
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 小計処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    total_amount = res.get("data").get("totalAmountWithTax")
    assert total_amount > 0
    print(f"合計金額（税込）: {total_amount}円")
    
    # 1. その他支払い（商品券）で一部支払い
    others_detail = "{ paymentMethod: '商品券', voucherNumber: 'ABC123' }"
    others_amount = 300  # 300円分の商品券
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "12", "amount": others_amount, "detail": others_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 2. キャッシュレスで一部支払い
    cashless_detail = str({"card_no": "9876543210", "auth_code": "XYZ789"})
    cashless_amount = 400  # 400円分のキャッシュレス決済
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "11", "amount": cashless_amount, "detail": cashless_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 3. 現金で残りを支払い（お釣りが発生するように多めに）
    cash_amount = 2000  # 2000円の現金（お釣りが発生する）
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": cash_amount, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    
    # 支払い状況の確認
    res = response.json()
    payments = res.get("data").get("payments")
    assert len(payments) == 3  # 3種類の支払い方法
    
    # 請求処理
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") == True
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value
    
    # お釣りの確認
    expected_change = cash_amount - (total_amount - others_amount - cashless_amount)
    assert res.get("data").get("changeAmount") == expected_change
    
    # レシートにすべての支払い方法が記載されていることを確認
    journal_text = res.get("data").get("journalText")
    assert "商品券" in journal_text or "Others" in journal_text
    assert "Cashless" in journal_text
    assert "Cash" in journal_text
    assert f"お釣り                  \\{int(expected_change):,}" in journal_text
    print(f"journal_text: {journal_text}")
    
    # トランザクションの詳細を確認
    transaction_no = res.get("data").get("transactionNo")
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    
    # すべての支払いが記録されているか確認
    payments = res.get("data").get("payments")
    assert len(payments) == 3
    
    # その他支払いの確認
    others_payment = next((p for p in payments if p.get("paymentCode") == "12"), None)
    assert others_payment is not None
    assert others_payment.get("paymentAmount") == others_amount
    
    # キャッシュレス支払いの確認
    cashless_payment = next((p for p in payments if p.get("paymentCode") == "11"), None)
    assert cashless_payment is not None
    assert cashless_payment.get("paymentAmount") == cashless_amount
    
    # 現金支払いの確認
    cash_payment = next((p for p in payments if p.get("paymentCode") == "01"), None)
    assert cash_payment is not None
    # 現金支払いの場合、支払金額はお釣りを引いた金額になっているはず
    assert cash_payment.get("paymentAmount") == total_amount - others_amount - cashless_amount
    
    print("Multiple payment methods test completed")

# 未登録商品エラーのテスト
@pytest.mark.asyncio
async def test_unregistered_item_error(http_client):
    """未登録商品コードを使用した場合のエラー処理をテスト"""
    print("Testing unregistered item error started")
    
    # 認証トークンとテナント/ターミナル設定
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info['terminalId']
    api_key = terminal_info.get('apiKey')
    header = {"X-API-KEY": api_key}
    
    # ターミナルがオープン状態になっていることを確認
    current_status = terminal_info.get('status', '')
    if current_status != 'Opened':
        await open_terminal(tenant_id)
    
    # カートの作成
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")
    
    # 未登録の商品コードを使用して商品を追加
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "NONEXISTENT", "quantity": 1}],
        headers=header,
    )
    
    # 未登録商品の場合、404 Not Foundまたは422 Unprocessable Entityが返されることを確認
    assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY]
    res = response.json()
    print(f"Response non exist item: {res}")
    
    # カートをキャンセルして終了
    await http_client.post(
        f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header
    )
    
    print("Unregistered item error test completed")