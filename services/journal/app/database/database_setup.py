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
    # `None` addresses the shared commons database, the convention cart and
    # terminal already used for the collections written there (issue #221).
    # Without this it produced a database literally named "<prefix>_None",
    # which nothing reads and nothing would ever have noticed.
    db_name = f"{settings.DB_NAME_PREFIX}_commons" if tenant_id is None else f"{settings.DB_NAME_PREFIX}_{tenant_id}"
    await db_helper.create_collection_with_indexes_async(
        db_name=db_name,
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
        drop_indexes_by_keys=drop_indexes_by_keys,
    )


# create tran collection
async def create_tran_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_TRAN
    # Client-carried cart phase 2 (issue #156 / #152): cart_id is the dedupe
    # identity (partial-unique). The numbering tuple includes business_counter
    # because transaction_no is the per-open seq.
    index_keys_list = [
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_counter": 1, "transaction_no": 1},
            "unique": True,
        },
        {
            "keys": {"tenant_id": 1, "store_code": 1, "cart_id": 1},
            "unique": True,
            "partialFilterExpression": {"cart_id": {"$type": "string"}},
        },
    ]
    await create_some_collection(
        tenant_id=tenant_id,
        collection_name=name,
        index_keys_list=index_keys_list,
        index_name=name + "_index",
        # Issue #156 migration: drop the old unique index missing business_counter.
        drop_indexes_by_keys=[{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}],
    )


# create cash_in_out_log collection
async def create_cash_in_out_log_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG
    index_key_list = [
        {
            "keys": {
                "tenant_id": 1,
                "store_code": 1,
                "terminal_no": 1,
                "business_date": 1,
                "open_counter": 1,
                "generate_date_time": 1,
            },
            "unique": True,
        },
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


# create open_close_log collection
async def create_open_close_log_collection(tenant_id: str):
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


# create journal collection
async def create_journal_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_JOURNAL
    index_keys_list = [
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_type": 1, "generate_date_time": 1},
            "unique": True,
        },
        {
            "keys": {
                "tenant_id": 1,
                "store_code": 1,
                "terminal_no": 1,
                "transaction_type": 1,
            },
            "unique": False,
        },
        {
            "keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_date": 1, "receipt_no": 1},
            "unique": False,
        },
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
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
            create_tran_collection,
            create_cash_in_out_log_collection,
            create_open_close_log_collection,
            create_journal_collection,
            create_request_log_collection,
        ],
    )


# setup database
async def execute(tenant_id: str):
    logger.info(f"Setting up database for tenant_id:{tenant_id} execution started...")
    await create_collections(tenant_id)
    # add more setup tasks here
