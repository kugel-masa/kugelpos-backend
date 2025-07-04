# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import pytest_asyncio
import os
from motor.motor_asyncio import AsyncIOMotorDatabase


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):

    from kugel_common.database import database as db_helper
    from app.database import database_setup

    """
    setup database
    create database and collections
    """
    print("Setting up database for tenant")
    # Reset the database connection to ensure clean state
    await db_helper.close_client_async()

    await database_setup.execute(os.environ.get("TENANT_ID"))

    """
    setup data : Staff
    """
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    from app.services.staff_master_service import StaffMasterService
    from app.models.repositories.staff_master_repository import StaffMasterRepository

    master_service_repo = StaffMasterRepository(db, os.environ.get("TENANT_ID"))
    master_service = StaffMasterService(master_service_repo)

    staff = await master_service.create_staff_async(staff_id="S001", staff_name="Staff1", pin="1234", roles=["staf"])
    assert staff is not None

    """
    setup data : Category Master
    """
    from app.services.category_master_service import CategoryMasterService
    from app.models.repositories.category_master_repository import CategoryMasterRepository

    category_service_repo = CategoryMasterRepository(db, os.environ.get("TENANT_ID"))
    category_service = CategoryMasterService(category_service_repo)

    category = await category_service.create_category_async(
        category_code="001", description="Category1", description_short="Cat1", tax_code="01"
    )

    """
    setup data : Item Common Master
    """
    from app.services.item_common_master_service import ItemCommonMasterService
    from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository

    item_service_repo = ItemCommonMasterRepository(db, os.environ.get("TENANT_ID"))
    item_service = ItemCommonMasterService(item_service_repo)

    item = await item_service.create_item_async(
        item_code="49-01",
        description="Item1",
        unit_price=120.00,
        unit_cost=50.00,
        item_details=["detail1", "detail2"],
        image_urls=["url1", "url2"],
        category_code="001",
        tax_code="01",
    )
    assert item is not None

    item = await item_service.create_item_async(
        item_code="49-02",
        description="Item2",
        unit_price=280.00,
        unit_cost=140.00,
        item_details=["detail1", "detail2"],
        image_urls=["url1", "url2"],
        category_code="001",
        tax_code="01",
    )
    assert item is not None

    """
    setup data : Item Store Master
    """
    from app.services.item_store_master_service import ItemStoreMasterService
    from app.models.repositories.item_store_master_repository import ItemStoreMasterRepository

    item_store_service_repo = ItemStoreMasterRepository(db, os.environ.get("TENANT_ID"), "5678")
    item_common_service_repo = ItemCommonMasterRepository(db, os.environ.get("TENANT_ID"))
    item_store_service = ItemStoreMasterService(item_store_service_repo, item_common_service_repo)

    item_store = await item_store_service.create_item_async(item_code="49-01", store_price=100.00)
    assert item_store is not None

    """
    setup data : Payments
    """
    from app.services.payment_master_service import PaymentMasterService
    from app.models.repositories.payment_master_repository import PaymentMasterRepository

    payment_service_repo = PaymentMasterRepository(db, os.environ.get("TENANT_ID"))
    payment_service = PaymentMasterService(payment_service_repo)

    # cash payment
    payment = await payment_service.create_payment_async(
        payment_code="01",
        description="Cash",
        limit_amount=0.0,
        can_refund=True,
        can_deposit_over=True,
        can_change=True,
        is_active=True,
    )

    # cashless payment
    payment = await payment_service.create_payment_async(
        payment_code="11",
        description="Cashless",
        limit_amount=100000.0,
        can_refund=False,
        can_deposit_over=False,
        can_change=False,
        is_active=True,
    )

    # others payment
    payment = await payment_service.create_payment_async(
        payment_code="12",
        description="Others",
        limit_amount=100000.0,
        can_refund=False,
        can_deposit_over=False,
        can_change=False,
        is_active=True,
    )

    """
    setup data : Settings
    """
    from app.services.settings_master_service import SettingsMasterService
    from app.models.repositories.settings_master_repository import SettingsMasterRepository

    settings_service_repo = SettingsMasterRepository(db, os.environ.get("TENANT_ID"))
    settings_service = SettingsMasterService(settings_service_repo)

    values = [
        {"store_code": "5678", "terminal_no": 9, "value": "this value is for terminal 9"},
        {"store_code": "5678", "value": "this value is for store 5678"},
    ]
    settings = await settings_service.create_settings_async("store_name", "default name", values)

    yield db
    print("Database setup completed")

    print("Shutting down database")
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase):
    assert setup_db is not None
    print(f"Database: {setup_db.name}")
