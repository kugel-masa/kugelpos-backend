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
    drop_indexes_by_keys: list = None,
):
    """
    Creates a MongoDB collection with specified indexes.

    Args:
        tenant_id: The tenant identifier used to create the database name
        collection_name: Name of the collection to create
        index_keys_list: List of index key definitions for the collection
        index_name: Name for the created index
        drop_indexes_by_keys: Index key patterns to retire first, matched by
            pattern rather than by name (issue #182 uses it to replace the
            index keyed on fields a request log document does not have)

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
        db_name=db_name,
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
        drop_indexes_by_keys=drop_indexes_by_keys,
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
        # Issue #182: the key columns were `store_code` and `terminal_no` at the
        # top level, where a request log document does not have them - they live
        # under `terminal_info`. So the index resolved to
        # (tenant_id, null, null, accept_time) and the constraint it enforced was
        # one request per tenant per timestamp, never the per-terminal separation
        # it was written for.
        #
        # Corrected to the paths that exist, and no longer unique. What a unique
        # index here could protect against - the same request written twice - does
        # not happen: insert_many stamps `_id` into the documents in place, so a
        # retried batch is refused by `_id` (issue #183). What it did do was
        # reject audit records that legitimately happened, silently; measured at
        # 66 rows across this environment.
        {
            "keys": {
                "tenant_id": 1,
                "terminal_info.store_code": 1,
                "terminal_info.terminal_no": 1,
                "request_info.accept_time": 1,
            },
            "unique": False,
        },
    ]
    # Retention (issue #221). Nothing in this tree reads the request log and
    # nothing removed one either: measured downstream at 6.4M documents /
    # 23.8 GiB, 97% of the database, on a store PC. Keyed on `created_at` alone -
    # deliberately a different key pattern from the index(es) above, because
    # MongoDB will not swap options on an existing key pattern, and
    # `request_info.accept_time` is a string, which a TTL never expires.
    #
    # Declared only when retention is positive: `expireAfterSeconds: 0` is not
    # "no expiry" to MongoDB, it means "expire AT the stored date", which would
    # delete each request log almost as soon as it is written. 0 therefore means
    # "do not declare it" - an index already created stays until it is dropped by
    # hand, which is the conservative direction for a switch that only ever
    # removes data.
    if settings.REQUEST_LOG_TTL_SECONDS > 0:
        index_key_list.append(
            {
                "keys": {"created_at": 1},
                "unique": False,
                "expireAfterSeconds": settings.REQUEST_LOG_TTL_SECONDS,
            }
        )
    # Both copies (issue #221). The buffer writes every request log twice - to the
    # tenant database and to `{prefix}_commons` - but provisioning only ever ran
    # for the tenant, so the commons copy had no index at all beyond `_id_`, and
    # no way to shrink, while receiving exactly the same volume. `tenant_id=None`
    # is how create_some_collection addresses the commons database.
    for target in (tenant_id, None):
        # Pre-#221 documents carry no date, and a TTL index never expires those.
        # Before the index, so the rows the index exists for are already covered
        # by the time it starts running.
        await db_helper.backfill_created_at_from_id_async(
            db_name=f"{settings.DB_NAME_PREFIX}_commons" if target is None else f"{settings.DB_NAME_PREFIX}_{target}",
            collection_name=name,
        )
        await create_some_collection(
            tenant_id=target,
            collection_name=name,
            index_keys_list=index_key_list,
            index_name=name + "_index",
            # Retire the index keyed on fields that do not exist (issue #182).
            drop_indexes_by_keys=[{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}],
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
    """Create every collection this service needs for a tenant.

    Through run_setup_steps_async so that one blocked collection does not stop
    the rest from being created, and so a failure names every blocked collection
    at once rather than one restart at a time (issue #185).
    """
    await db_helper.run_setup_steps_async(
        tenant_id,
        [
            create_tenant_info_collection,
            create_terminal_info_collection,
            create_cash_in_out_log_collection,
            create_request_log_collection,
            create_open_close_log_collection,
            create_terminallog_delivery_status_collection,
        ],
    )


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
