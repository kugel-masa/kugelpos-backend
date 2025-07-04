# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from logging import getLogger
from kugel_common.database import database as db_helper
from app.config.settings import settings

# setup logger
logger = getLogger(__name__)

"""
Database setup module for the Cart service.

This module handles the creation of MongoDB collections and indexes
needed by the Cart service. It provides functions to create individual
collections as well as a main execution function to create all collections.
"""


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


async def create_cache_cart_collection(tenant_id: str):
    """
    Creates the cache_cart collection with an index on cart_id.

    This collection is used to store shopping cart data in cache.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_CACHE_CART
    index_key_list = [{"keys": {"cart_id": 1}, "unique": True}]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_terminal_counter_collection(tenant_id: str):
    """
    Creates the terminal counter collection with an index on terminal_id.

    This collection is used to manage counters for POS terminals,
    such as transaction sequence numbers.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_TERMINAL_COUTER
    index_key_list = [{"keys": {"terminal_id": 1}, "unique": True}]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_tran_log_collection(tenant_id: str):
    """
    Creates the transaction log collection with a compound index.

    This collection stores completed transaction records and is indexed
    by tenant, store, terminal and transaction number.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_TRAN_LOG
    index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}, "unique": True}
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_request_log_collection(tenant_id: str):
    """
    Creates the request log collection with a compound index.

    This collection stores API request logs and is indexed by tenant,
    store, terminal and request acceptance time.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_REQUEST_LOG
    index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}, "unique": True}
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_tran_log_delivery_status_collection(tenant_id: str):
    """
    Creates the transaction log delivery status collection with indexes.

    This collection tracks the delivery status of transaction logs to subscribing services
    and is indexed by event_id and transaction information.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_TRAN_LOG_DELIVERY_STATUS
    index_key_list = [
        {"keys": {"event_id": 1}, "unique": True},
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}, "unique": False},
        {"keys": {"status": 1, "published_at": 1}, "unique": False},
    ]
    await create_some_collection(
        tenant_id=None, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_status_tran_collection(tenant_id: str):
    """
    Creates the transaction status collection with indexes.

    This collection tracks the void/return status of transactions
    and is indexed by transaction identifiers.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_STATUS_TRAN
    index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}, "unique": True}
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_collections(tenant_id: str):
    """
    Creates all required collections for the Cart service.

    This function is a convenience wrapper that calls all the individual
    collection creation functions.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    await create_cache_cart_collection(tenant_id)
    await create_terminal_counter_collection(tenant_id)
    await create_tran_log_collection(tenant_id)
    await create_request_log_collection(tenant_id)
    await create_tran_log_delivery_status_collection(tenant_id)
    await create_status_tran_collection(tenant_id)

    # add more collections here


async def execute(tenant_id: str):
    """
    Main entry point for database setup.

    Executes all database setup tasks for the specified tenant.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    logger.info("Setting up database execution started...")
    await create_collections(tenant_id)
    # add more setup tasks here
