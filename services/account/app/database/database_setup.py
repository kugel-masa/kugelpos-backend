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
from logging import getLogger
from kugel_common.database import database as db_helper
from app.config.settings import settings

# Configure logger for database setup operations
logger = getLogger(__name__)


async def create_some_collection(tenant_id: str, collection_name: str, index_keys_list: list, index_name: str):
    """
    Create a collection with specified indexes in the tenant's database

    Args:
        tenant_id: The tenant identifier
        collection_name: Name of the collection to create
        index_keys_list: List of index configurations to create on the collection
        index_name: Base name for the indexes

    Returns:
        None
    """
    db_name = f"{settings.DB_NAME_PREFIX}_{tenant_id}"
    await db_helper.create_collection_with_indexes_async(
        db_name=db_name, collection_name=collection_name, index_keys_list=index_keys_list, index_name=index_name
    )


async def create_user_account_collection(tenant_id: str):
    """
    Create the user accounts collection with appropriate indexes

    Creates a collection for storing user account information with a
    compound index on tenant_id and username to ensure uniqueness.

    Args:
        tenant_id: The tenant identifier

    Returns:
        None
    """
    name = settings.DB_COLLECTION_USER_ACCOUNTS
    index_key_list = [{"keys": {"tenant_id": 1, "username": 1}, "unique": True}]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


async def create_request_log_collection(tenant_id: str):
    """
    Create the request log collection with appropriate indexes

    Creates a collection for storing API request logs with a compound index
    on tenant_id, store_code, terminal_no, and request acceptance time.

    Args:
        tenant_id: The tenant identifier

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


async def create_collections(tenant_id: str):
    """
    Create all required collections for a new tenant

    This function should be extended when new collections are added to the system.
    Each collection creation should be added to this function.

    Args:
        tenant_id: The tenant identifier

    Returns:
        None
    """
    await create_user_account_collection(tenant_id)
    await create_request_log_collection(tenant_id)
    # Add more collections here as the system grows


async def execute(tenant_id: str):
    """
    Execute the complete database setup for a new tenant

    This is the main entry point for database initialization.
    It creates all necessary collections with their indexes and
    performs any other setup tasks required for a new tenant.

    Args:
        tenant_id: The tenant identifier

    Returns:
        None
    """
    logger.info(f"Setting up database for tenant_id:{tenant_id} execution started...")
    await create_collections(tenant_id)
    # Add more setup tasks here if needed
    logger.info(f"Database setup for tenant_id:{tenant_id} completed successfully")
