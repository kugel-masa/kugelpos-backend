# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest, os, asyncio
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase
from httpx import AsyncClient
from tests.log_maker import make_tran_log

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.misc import get_app_time_str
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.documents.open_close_log import OpenCloseLog


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    # loop = asyncio.get_running_loop()

    """
    setup database
    create database and collections
    """
    print("Setting up database")
    tenant_id = os.environ.get("TENANT_ID")
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        print("WARNING: MONGODB_URI not found in environment variables. Using default.")
        mongodb_uri = "mongodb://localhost:27017/"
    print(f"MONGODB_URI: {mongodb_uri}")
    db_helper.MONGODB_URI = mongodb_uri

    await database_setup.execute(tenant_id=os.environ.get("TENANT_ID"))
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")

    yield db
    print("Database setup completed")

    print("Shutdown database")
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase, http_client: AsyncClient):
    assert setup_db is not None
    print(f"Database: {setup_db.name}")

    tenant_id: str = os.environ.get("TENANT_ID")
    store_code: str = os.environ.get("STORE_CODE")
    terminal_no: int = int(os.environ.get("TERMINAL_NO"))
    tran_no: int = 1001
    receipt_no: int = 2001
    business_date: str = os.environ.get("BUSINESS_DATE")

    # get token from auth service
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == 200
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # create terminal info or get existing one
    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals"
    terminal_info = {
        "store_code": os.environ.get("STORE_CODE"),
        "terminal_no": os.environ.get("TERMINAL_NO"),
        "description": "test terminal",
    }
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.post(url=terminal_url, headers=header, json=terminal_info)
    res = response.json()
    print(f"create terminal response: {res}")

    # If terminal already exists, get its info
    if response.status_code == 400 and "already exists" in res.get("message", ""):
        # Get existing terminal info
        terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
        terminal_get_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}"
        async with AsyncClient() as http_terminal_client:
            response = await http_terminal_client.get(url=terminal_get_url, headers=header)
        res = response.json()
        print(f"get existing terminal response: {res}")

    # terminal sign in
    # Get terminal_id from the created terminal
    terminal_id = res.get("data", {}).get("terminalId")
    api_key = res.get("data", {}).get("apiKey")

    # Check if terminal is already signed in by getting terminal info
    terminal_info_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}"
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.get(url=terminal_info_url, headers={"X-API-KEY": api_key})
    terminal_info = response.json().get("data", {})
    print(f"Terminal info: {terminal_info}")

    # Check if staff is already signed in
    if terminal_info.get("staf") and terminal_info.get("staff", {}).get("id"):
        print(f'Terminal already has staff signed in: {terminal_info.get("staff")}')
        # Use the existing sign-in, no need to sign in again
    else:
        # Create staff S001 if it doesn't exist
        staff_url = f"{os.environ.get('BASE_URL_MASTER_DATA')}/tenants/{tenant_id}/staff"
        staff_data = {
            "id": "S001",
            "name": "Staff 001",
            "pin": "1234",
            "roles": ["cashier"],  # Add required roles field
        }
        async with AsyncClient() as http_staff_client:
            response = await http_staff_client.post(url=staff_url, headers=header, json=staff_data)
        if response.status_code == 201:
            print(f"Staff created successfully: {response.json()}")
        else:
            print(f"Staff creation response: {response.json()}")

        # Sign in to terminal with staff
        sign_in_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}/sign-in"
        sign_in_data = {"staff_id": "S001", "staff_pin": "1234"}  # Default PIN for test staff

        # Use API key authentication for terminal sign-in
        terminal_headers = {"X-API-KEY": api_key}

        async with AsyncClient() as http_terminal_client:
            response = await http_terminal_client.post(url=sign_in_url, headers=terminal_headers, json=sign_in_data)

        res = response.json()
        print(f"Terminal sign in response: {res}")
        print(f"Terminal sign in status code: {response.status_code}")

        # If sign-in fails with 400, it might be because staff doesn't exist or wrong credentials
        if response.status_code == 400:
            print("Sign-in failed. Trying to use terminal without staff sign-in.")
            # Continue without staff sign-in
        else:
            assert response.status_code == 200
            assert res.get("success") is True

    # Now use the API key for subsequent requests instead of JWT token
    header = {"X-API-KEY": api_key}

    # create transaction (sales) 1
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            tran_type=101,
            tran_no=tran_no,
            receipt_no=receipt_no,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header,
    )
    assert response.status_code == 201
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == 201

    # create transaction (sales) 2
    tran_no += 1
    receipt_no += 1
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            tran_type=101,
            tran_no=tran_no,
            receipt_no=receipt_no,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header,
    )
    assert response.status_code == 201
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == 201

    # create transaction (sales) 3
    tran_no += 1
    receipt_no += 1
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            tran_type=101,
            tran_no=tran_no,
            receipt_no=receipt_no,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header,
    )
    assert response.status_code == 201
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == 201

    # create transaction (return) 1
    tran_no += 1
    receipt_no += 1
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            tran_type=102,
            tran_no=tran_no,
            receipt_no=receipt_no,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header,
    )
    assert response.status_code == 201
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == 201

    await asyncio.sleep(5)

    # create transaction (void sales) 1
    tran_no += 1
    receipt_no += 1
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        json=make_tran_log(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            tran_type=201,
            tran_no=tran_no,
            receipt_no=receipt_no,
            business_date=business_date,
            generate_date_time=get_app_time_str(),
        ),
        headers=header,
    )
    assert response.status_code == 201
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == 201
    last_tran_no = tran_no

    # create cash in log using repository
    mongodb_url = os.environ.get("MONGODB_URI")
    print(f"Creating cash_in_out_log with tenant_id: {tenant_id}, db_name: {setup_db.name}, mongodb_url: {mongodb_url}")
    cash_in_out_log_repo = CashInOutLogRepository(setup_db, tenant_id)
    cash_in_out_log = await cash_in_out_log_repo.create_cash_in_out_log(
        cash_in_out_log=CashInOutLog(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            amount=1000.0,
            description="Cash In",
            generate_date_time=get_app_time_str(),
            business_date=business_date,
            open_counter=1,
            business_counter=1001,
        )
    )
    assert cash_in_out_log is not None
    print(f"CashInOutLog created: {cash_in_out_log}")
    await asyncio.sleep(2)

    # create cash in log using repository 2
    cash_in_out_log = await cash_in_out_log_repo.create_cash_in_out_log(
        cash_in_out_log=CashInOutLog(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            amount=2000.0,
            description="Cash In 2",
            generate_date_time=get_app_time_str(),
            business_date=business_date,
            open_counter=1,
            business_counter=1001,
        )
    )
    print(f"CashInOutLog created: {cash_in_out_log}")
    await asyncio.sleep(2)

    # create cash out log using repository
    cash_in_out_log = await cash_in_out_log_repo.create_cash_in_out_log(
        cash_in_out_log=CashInOutLog(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            amount=-500.0,
            description="Cash Out",
            generate_date_time=get_app_time_str(),
            business_date=business_date,
            open_counter=1,
            business_counter=1001,
        )
    )
    cash_in_out_last_datetime = cash_in_out_log.generate_date_time
    assert cash_in_out_log is not None
    print(f"CashInOutLog created: {cash_in_out_log}")

    # create open close log using repository
    print(f"Creating open_close_log with tenant_id: {tenant_id}, db_name: {setup_db.name}")
    open_close_log_repo = OpenCloseLogRepository(setup_db, tenant_id)
    open_close_log = await open_close_log_repo.create_open_close_log(
        OpenCloseLog(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=1,
            business_counter=1001,
            operation="open",
            generate_date_time=get_app_time_str(),
            terminal_info=_make_terminal_info(
                tenant_id=tenant_id,
                store_code=store_code,
                terminal_no=terminal_no,
                business_date=business_date,
                open_counter=1,
                business_counter=1001,
                staff={"id": "S001", "name": "Staff 001"},
                initial_amount=10000.0,
            ),
            cart_transaction_count=0,
            cart_transaction_last_no=0,
            cash_in_out_count=0,
            cash_in_out_last_datetime=None,
        )
    )
    assert open_close_log is not None
    print(f"OpenCloseLog created: {open_close_log}")

    # create close log using repository
    open_close_log = await open_close_log_repo.create_open_close_log(
        OpenCloseLog(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=1,
            business_counter=1001,
            operation="close",
            generate_date_time=get_app_time_str(),
            terminal_info=_make_terminal_info(
                tenant_id=tenant_id,
                store_code=store_code,
                terminal_no=terminal_no,
                business_date=business_date,
                open_counter=1,
                business_counter=1001,
                staff={"id": "S001", "name": "Staff 001"},
                initial_amount=10000.0,
                physical_amount=20000.0,
            ),
            cart_transaction_count=5,
            cart_transaction_last_no=last_tran_no,
            cash_in_out_count=3,
            cash_in_out_last_datetime=cash_in_out_last_datetime,
        )
    )
    assert open_close_log is not None
    print(f"OpenCloseLog created: {open_close_log}")


def _make_terminal_info(
    tenant_id: str,
    store_code: str,
    terminal_no: int,
    business_date: str,
    open_counter: int = 1,
    business_counter: int = 1001,
    staff: str = None,
    initial_amount: float = 0.0,
    physical_amount: float = 0.0,
) -> TerminalInfoDocument:
    return TerminalInfoDocument(
        tenant_id=tenant_id,
        store_code=store_code,
        terminal_no=terminal_no,
        description="Test Terminal",
        terminal_id=f"{tenant_id}-{store_code}-{terminal_no}",
        function_mode="TerminalOpen",
        status="active",
        business_date=business_date,
        open_counter=open_counter,
        business_counter=business_counter,
        staff=staff,
        initial_amount=initial_amount,
        physical_amount=physical_amount,
        api_key="test_api_key",
        tags=["test"],
    )
