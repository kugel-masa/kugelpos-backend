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

"""Tests for app.database.database_setup module."""

import pytest
from unittest.mock import AsyncMock, patch


TENANT_ID = "test_tenant"


@pytest.mark.asyncio
@patch("app.database.database_setup.db_helper")
async def test_create_some_collection(mock_db_helper):
    """Test create_some_collection calls db_helper with correct arguments."""
    mock_db_helper.create_collection_with_indexes_async = AsyncMock()

    from app.database.database_setup import create_some_collection

    collection_name = "test_collection"
    index_keys_list = [{"keys": {"field1": 1}, "unique": True}]
    index_name = "test_index"

    await create_some_collection(
        tenant_id=TENANT_ID,
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
    )

    mock_db_helper.create_collection_with_indexes_async.assert_awaited_once_with(
        db_name=f"db_account_{TENANT_ID}",
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
    )


@pytest.mark.asyncio
@patch("app.database.database_setup.create_some_collection", new_callable=AsyncMock)
async def test_create_user_account_collection(mock_create_some):
    """Test create_user_account_collection creates collection with correct index config."""
    from app.database.database_setup import create_user_account_collection
    from app.config.settings import settings

    await create_user_account_collection(tenant_id=TENANT_ID)

    expected_name = settings.DB_COLLECTION_USER_ACCOUNTS
    expected_index_key_list = [{"keys": {"tenant_id": 1, "username": 1}, "unique": True}]

    mock_create_some.assert_awaited_once_with(
        tenant_id=TENANT_ID,
        collection_name=expected_name,
        index_keys_list=expected_index_key_list,
        index_name=expected_name + "_index",
    )


@pytest.mark.asyncio
@patch("app.database.database_setup.create_some_collection", new_callable=AsyncMock)
async def test_create_request_log_collection(mock_create_some):
    """Test create_request_log_collection creates collection with correct index config."""
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    await create_request_log_collection(tenant_id=TENANT_ID)

    expected_name = settings.DB_COLLECTION_NAME_REQUEST_LOG
    expected_index_key_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}, "unique": True}
    ]

    mock_create_some.assert_awaited_once_with(
        tenant_id=TENANT_ID,
        collection_name=expected_name,
        index_keys_list=expected_index_key_list,
        index_name=expected_name + "_index",
    )


@pytest.mark.asyncio
@patch("app.database.database_setup.create_request_log_collection", new_callable=AsyncMock)
@patch("app.database.database_setup.create_user_account_collection", new_callable=AsyncMock)
async def test_create_collections(mock_create_user, mock_create_request):
    """Test create_collections calls both collection creators."""
    from app.database.database_setup import create_collections

    await create_collections(tenant_id=TENANT_ID)

    mock_create_user.assert_awaited_once_with(TENANT_ID)
    mock_create_request.assert_awaited_once_with(TENANT_ID)


@pytest.mark.asyncio
@patch("app.database.database_setup.create_collections", new_callable=AsyncMock)
async def test_execute(mock_create_collections):
    """Test execute calls create_collections and logs appropriately."""
    from app.database.database_setup import execute

    await execute(tenant_id=TENANT_ID)

    mock_create_collections.assert_awaited_once_with(TENANT_ID)


@pytest.mark.asyncio
@patch("app.database.database_setup.create_collections", new_callable=AsyncMock)
async def test_execute_logging(mock_create_collections):
    """Test execute logs start and completion messages."""
    from app.database.database_setup import execute

    with patch("app.database.database_setup.logger") as mock_logger:
        await execute(tenant_id=TENANT_ID)

        assert mock_logger.info.call_count == 2
        start_msg = mock_logger.info.call_args_list[0][0][0]
        end_msg = mock_logger.info.call_args_list[1][0][0]
        assert TENANT_ID in start_msg
        assert "started" in start_msg
        assert TENANT_ID in end_msg
        assert "completed" in end_msg
