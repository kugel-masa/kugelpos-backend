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
):
    db_name = f"{settings.DB_NAME_PREFIX}_{tenant_id}"
    await db_helper.create_collection_with_indexes_async(
        db_name=db_name, collection_name=collection_name, index_keys_list=index_keys_list, index_name=index_name
    )


# create tran collection
async def create_tran_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_TRAN
    index_keys_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}, "unique": True}
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
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
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}, "unique": True}
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_key_list, index_name=name + "_index"
    )


# create all collections
async def create_collections(tenant_id: str):
    await create_tran_collection(tenant_id)
    await create_cash_in_out_log_collection(tenant_id)
    await create_open_close_log_collection(tenant_id)
    await create_journal_collection(tenant_id)
    await create_request_log_collection(tenant_id)

    # add more collections here


# setup database
async def execute(tenant_id: str):
    logger.info(f"Setting up database for tenant_id:{tenant_id} execution started...")
    await create_collections(tenant_id)
    # add more setup tasks here
