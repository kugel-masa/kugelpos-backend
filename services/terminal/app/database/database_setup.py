# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from app.config.settings import settings
from logging import getLogger
from kugel_common.database import database as db_helper

# Setup logger for database operations
logger = getLogger(__name__)


async def create_some_collection(
    tenant_id: str,
    collection_name: str,
    index_keys_list: list,
    index_name: str,
):
    """
    Creates a MongoDB collection with specified indexes.

    Args:
        tenant_id: The tenant identifier used to create the database name
        collection_name: Name of the collection to create
        index_keys_list: List of index key definitions for the collection
        index_name: Name for the created index

    Returns:
        None
    """
    # Create the database name based on tenant_id
    if tenant_id is None:
        db_name = f"{settings.DB_NAME_PREFIX}_commons"
    else:
        db_name = f"{settings.DB_NAME_PREFIX}_{tenant_id}"

    # Create the collection with indexes
    await db_helper.create_collection_with_indexes_async(
        db_name=db_name, collection_name=collection_name, index_keys_list=index_keys_list, index_name=index_name
    )


async def create_tenant_info_collection(tenant_id: str):
    """
    Creates the tenant information collection with required indexes

    The tenant_info collection stores basic information about tenants
    and has a unique index on tenant_id

    Args:
        tenant_id: Tenant ID to create collection for
    """
    name = settings.DB_COLLECTION_NAME_TENANT_INFO
    index_key_list = [{"keys": {"tenant_id": 1}, "unique": True}]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_terminal_info_collection(tenant_id: str):
    """
    Creates the terminal information collection with required indexes

    The terminal_info collection stores information about POS terminals
    It has unique indexes on terminal_id and the combination of
    tenant_id, store_code, and terminal_no

    Args:
        tenant_id: Tenant ID to create collection for
    """
    name = settings.DB_COLLECTION_NAME_TERMINAL_INFO
    index_key_list = [
        {"keys": {"terminal_id": 1}, "unique": True},
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_cash_in_out_log_collection(tenant_id: str):
    """
    Creates the cash in/out log collection with required indexes

    This collection stores records of all cash drawer activities
    including cash in (deposits) and cash out (withdrawals)

    It has a unique index on the combination of terminal identifier and timestamp
    and a secondary index for business date and open counter

    Args:
        tenant_id: Tenant ID to create collection for
    """
    name = settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG
    index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "generate_date_time": 1}, "unique": True},
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_date": 1, "open_counter": 1},
            "unique": False,
        },
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_request_log_collection(tenant_id: str):
    """
    Creates the request log collection with required indexes

    This collection stores logs of API requests made to the system
    and has a unique index on terminal identifier and request timestamp

    Args:
        tenant_id: Tenant ID to create collection for
    """
    name = settings.DB_COLLECTION_NAME_REQUEST_LOG
    index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}, "unique": True}
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_open_close_log_collection(tenant_id: str):
    """
    Creates the open/close log collection with required indexes

    This collection stores records of terminal opening and closing operations
    with a unique index on the terminal identifier, business date,
    open counter, and operation type

    Args:
        tenant_id: Tenant ID to create collection for
    """
    name = settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG
    index_key_list = [
        {
            "keys": {
                "tenant_id": 1,
                "store_code": 1,
                "terminal_no": 1,
                "business_date": 1,
                "open_counter": 1,
                "operation": 1,
            },
            "unique": True,
        }
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_terminallog_delivery_status_collection(tenant_id: str):
    """
    Creates the terminal log delivery status collection with required indexes

    This collection stores status information for terminal log message deliveries
    with a unique index on event_id and indexes for querying by terminal identifiers

    Args:
        tenant_id: Tenant ID to create collection for
    """
    name = settings.DB_COLLECTION_NAME_TERMINALLOG_DELIVERY_STATUS
    index_key_list = [
        {"keys": {"event_id": 1}, "unique": True},
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_date": 1, "open_counter": 1},
            "unique": False,
        },
        {"keys": {"status": 1, "published_at": 1}, "unique": False},
    ]
    await create_some_collection(
        tenant_id=None, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_collections(tenant_id: str):
    """
    Creates all required collections for a tenant

    This function orchestrates the creation of all necessary MongoDB collections
    for a new tenant in the system

    Args:
        tenant_id: Tenant ID to create collections for
    """
    await create_tenant_info_collection(tenant_id)
    await create_terminal_info_collection(tenant_id)
    await create_cash_in_out_log_collection(tenant_id)
    await create_request_log_collection(tenant_id)
    await create_open_close_log_collection(tenant_id)
    await create_terminallog_delivery_status_collection(tenant_id)
    # Additional collections can be added here as needed


async def execute(tenant_id: str):
    """
    Main database setup function that initializes all required database structures

    This function is the entry point for setting up the database for a new tenant

    Args:
        tenant_id: Tenant ID to set up database for
    """
    logger.info(f"Setting up database for tenant_id:{tenant_id} execution started...")
    await create_collections(tenant_id)
    # Additional setup tasks can be added here as needed
