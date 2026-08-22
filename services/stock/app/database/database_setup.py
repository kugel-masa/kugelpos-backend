# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from logging import getLogger

from kugel_common.database import database as db_helper
from app.config.settings import settings

# setup logger
logger = getLogger(__name__)


# create some collection
async def create_some_collection(
    tenant_id: str,
    collection_name: str,
    index_keys_list: list,
    index_name: str,
    drop_indexes_by_keys: list = None,
):
    await db_helper.create_collection_with_indexes_async(
        db_name=f"{settings.DB_NAME_PREFIX}_{tenant_id}",
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
        drop_indexes_by_keys=drop_indexes_by_keys,
    )


# create stock collection
async def create_stock_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_STOCK
    index_keys_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "item_code": 1}, "unique": True},
        {"keys": {"item_code": 1}},
        {"keys": {"last_updated": -1}},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create stock_updates collection
async def create_stock_update_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_STOCK_UPDATE
    index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "item_code": 1, "timestamp": -1}},
        {"keys": {"update_type": 1}},
        {"keys": {"timestamp": -1}},
        {"keys": {"reference_id": 1}},
        # Unique on the transaction identity. Client-carried cart phase 2
        # (issue #156 / #152): a duplicate finalize carries the same cart_id,
        # so this index stops the second stock movement at the DB layer.
        # Partial filter scopes it to transaction-driven updates (cart_id
        # present); manual adjustments (cart_id NULL) are excluded.
        {
            "keys": {
                "tenant_id": 1,
                "store_code": 1,
                "cart_id": 1,
                "item_code": 1,
                "update_type": 1,
            },
            "unique": True,
            "partialFilterExpression": {"cart_id": {"$type": "string"}},
        },
    ]
    await create_some_collection(
        tenant_id=tenant_id,
        collection_name=name,
        index_keys_list=index_key_list,
        index_name=name + "_index",
        # Issue #156 migration: drop the old unique index keyed on transaction_no
        # (now the per-open seq) before relying on the cart_id index.
        drop_indexes_by_keys=[
            {
                "tenant_id": 1,
                "store_code": 1,
                "terminal_no": 1,
                "transaction_no": 1,
                "item_code": 1,
                "update_type": 1,
            }
        ],
    )


# create stock_snapshots collection
async def create_stock_snapshot_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_STOCK_SNAPSHOT
    index_key_list = [{"keys": {"tenant_id": 1, "store_code": 1, "snapshot_time": -1}}, {"keys": {"created_at": -1}}]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


# create request log collection
async def create_request_log_collection(tenant_id: str):
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
        }
    ]
    await create_some_collection(
        tenant_id=tenant_id,
        collection_name=name,
        index_keys_list=index_key_list,
        index_name=name + "_index",
        # Retire the index keyed on fields that do not exist (issue #182).
        drop_indexes_by_keys=[{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}],
    )


# create all collections
async def create_collections(tenant_id: str):
    """Create every collection this service needs for a tenant.

    Through run_setup_steps_async so that one blocked collection does not stop
    the rest from being created, and so a failure names every blocked collection
    at once rather than one restart at a time (issue #185).
    """
    await db_helper.run_setup_steps_async(
        tenant_id,
        [
            create_stock_collection,
            create_stock_update_collection,
            create_stock_snapshot_collection,
            create_request_log_collection,
        ],
    )


# setup database
async def execute(tenant_id: str):
    logger.info(f"Setting up database for tenant_id:{tenant_id} execution started...")
    await create_collections(tenant_id)
    # add more setup tasks here
