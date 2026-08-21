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
    drop_indexes_by_keys: list = None,
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
        db_name=db_name,
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
        drop_indexes_by_keys=drop_indexes_by_keys,
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
    index_key_list = [
        {"keys": {"cart_id": 1}, "unique": True},
        # TTL index: expire orphaned MongoDB fallback copies, aligned with the Redis
        # cartstore TTL. Keyed on created_at (always set on insert); updated_at can be
        # None on first insert and would leave such docs unexpired.
        {"keys": {"created_at": 1}, "expireAfterSeconds": settings.CACHE_CART_TTL_SECONDS},
    ]
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
    # Client-carried cart phase 2 (issue #156): cart_id is the transaction
    # identity (partial-unique). transaction_no is now the per-open seq and is
    # NOT unique on its own across sessions, so the numbering tuple includes
    # business_counter. Mirrors the downstream report/journal indexes.
    index_key_list = [
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_counter": 1, "transaction_no": 1},
            "unique": True,
        },
        {
            "keys": {"tenant_id": 1, "store_code": 1, "cart_id": 1},
            "unique": True,
            "partialFilterExpression": {"cart_id": {"$type": "string"}},
        },
        # Receipt counter high-water (issue #166): what a replacement terminal is
        # reseeded from, and what an audit query walks to find holes. Explicitly
        # NOT unique — the counter is client-owned, the backend cannot enforce it
        # (spec 156 Q58), and gaps are expected where a terminal was replaced or
        # an offline-finalized transaction never arrived.
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "receipt_counter": 1},
            "unique": False,
        },
    ]
    await create_some_collection(
        tenant_id=tenant_id,
        collection_name=name,
        index_keys_list=index_key_list,
        index_name=name + "_index",
        # Issue #156 migration: retire the old unique index that lacked
        # business_counter (transaction_no is now the per-open seq).
        drop_indexes_by_keys=[{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}],
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
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}, "unique": True},
        # Rollback detection (issue #165): walk a cart's revisions in the order
        # they were presented. Normal operation is strictly increasing and a
        # retry repeats a value; anything lower is a replayed older envelope.
        # Partial, because only carried requests have marks to index.
        {
            "keys": {"tenant_id": 1, "snapshot_info.cart_id": 1, "request_info.accept_time": 1},
            "unique": False,
            "partialFilterExpression": {"snapshot_info.cart_id": {"$type": "string"}},
        },
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


async def backfill_status_tran_business_counter(tenant_id: str) -> None:
    """
    Fill in business_counter on pre-#156 transaction status records.

    Client-carried cart phase 2 made transaction_no the per-open seq, so a status
    record is only identified together with the open epoch it belongs to. Records
    written before the migration carry no epoch, and they cannot simply be matched
    with "epoch or null": legacy transaction_no came from a 1-based per-terminal
    counter and seq is 1-based per open session, so the ranges overlap completely
    — this session's seq=1 would find the terminal's very first sale from years
    ago and report its void/refund status as the current transaction's.

    So the epoch is copied in from the transaction the record refers to (the
    tranlog has always carried business_counter). Runs before the index rework so
    the records already match the new key by the time it is enforced.

    A record whose transaction cannot be resolved unambiguously is left alone and
    counted: it stays invisible to the new exact-match lookups, which at worst
    allows a second void of a transaction whose log is already gone — far milder
    than refusing every legitimate one. Backfill failure never blocks startup;
    the collection may simply not exist yet on a fresh tenant.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    status_collection = db[settings.DB_COLLECTION_NAME_STATUS_TRAN]
    tran_collection = db[settings.DB_COLLECTION_NAME_TRAN_LOG]

    filled = 0
    unresolved = 0
    try:
        # {"business_counter": None} matches both a null value and a missing field.
        async for record in status_collection.find({"business_counter": None}):
            key = {
                "tenant_id": record.get("tenant_id"),
                "store_code": record.get("store_code"),
                "terminal_no": record.get("terminal_no"),
                "transaction_no": record.get("transaction_no"),
            }
            # Read two: more than one match means the number spans several open
            # sessions and picking either would stamp the wrong epoch.
            candidates = await tran_collection.find(key, {"business_counter": 1}).to_list(2)
            if len(candidates) != 1 or candidates[0].get("business_counter") is None:
                unresolved += 1
                continue
            await status_collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"business_counter": candidates[0]["business_counter"]}},
            )
            filled += 1
    except Exception as e:
        logger.warning(f"status_tran business_counter backfill skipped for tenant {tenant_id}: {e}")
        return

    if filled or unresolved:
        logger.info(
            f"status_tran business_counter backfill for tenant {tenant_id}: "
            f"filled={filled} unresolved={unresolved}"
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
    # Fill the epoch in on existing records BEFORE the new unique key is enforced,
    # so pre-migration statuses stay reachable by the exact-match lookups.
    await backfill_status_tran_business_counter(tenant_id)

    name = settings.DB_COLLECTION_NAME_STATUS_TRAN
    # Client-carried cart phase 2 (issue #156): transaction_no is the per-open seq
    # and repeats every open session, so the status identity must include
    # business_counter — otherwise one session's void/refund status collides with
    # the same-numbered transaction of another session (a daily open resets seq to
    # 1, so day 2's first sale would read day 1's status). Mirrors the tranlog
    # numbering tuple.
    index_key_list = [
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_counter": 1, "transaction_no": 1},
            "unique": True,
        }
    ]
    await create_some_collection(
        tenant_id=tenant_id,
        collection_name=name,
        index_keys_list=index_key_list,
        index_name=name + "_index",
        # Issue #156 migration: retire the unique index that lacked business_counter.
        drop_indexes_by_keys=[{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}],
    )


async def create_cart_restore_log_collection(tenant_id: str):
    """
    Creates the cart restore audit collection with indexes (issue #148).

    This collection records every restore API attempt (success / existing
    returned / rejected) and is indexed for per-cart tracing and time-ordered
    audit queries. No TTL: retention follows the other log collections.

    Args:
        tenant_id: The tenant identifier used to create the database name

    Returns:
        None
    """
    name = settings.DB_COLLECTION_NAME_LOG_CART_RESTORE
    index_key_list = [
        {"keys": {"cart_id": 1}, "unique": False},
        {"keys": {"event_datetime": 1}, "unique": False},
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
    await create_cart_restore_log_collection(tenant_id)

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
