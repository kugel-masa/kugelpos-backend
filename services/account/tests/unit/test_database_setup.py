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
        drop_indexes_by_keys=None,
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
@patch("app.database.database_setup.db_helper")
@patch("app.database.database_setup.create_some_collection", new_callable=AsyncMock)
async def test_retention_of_zero_declares_no_ttl_at_all(mock_create_some, mock_db_helper, monkeypatch):
    """0 has to mean "no expiry", and to MongoDB it does not (issue #221).

    `expireAfterSeconds: 0` on a date field means "expire AT the stored date",
    so passing the setting straight through would delete each request log almost
    as soon as it was written - the opposite of what an operator setting 0 is
    asking for.
    """
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    monkeypatch.setattr(settings, "REQUEST_LOG_TTL_SECONDS", 0)
    mock_db_helper.backfill_created_at_from_id_async = AsyncMock(return_value=0)

    await create_request_log_collection(tenant_id=TENANT_ID)

    for call in mock_create_some.await_args_list:
        for index in call.kwargs["index_keys_list"]:
            assert "expireAfterSeconds" not in index, index


@pytest.mark.asyncio
@patch("app.database.database_setup.db_helper")
async def test_the_commons_target_is_the_commons_database(mock_db_helper):
    """`tenant_id=None` means the shared commons database, not a tenant of that name.

    The request log is written to both, so provisioning has to reach both
    (issue #221) - and this service's helper interpolated the tenant into the
    name unconditionally, which turned the commons pass into a database
    literally called `db_account_None`. It was created, indexed, and read by
    nothing.
    """
    from app.database.database_setup import create_some_collection
    from app.config.settings import settings

    mock_db_helper.create_collection_with_indexes_async = AsyncMock()

    await create_some_collection(tenant_id=None, collection_name="c", index_keys_list=[], index_name="i")

    called = mock_db_helper.create_collection_with_indexes_async.await_args.kwargs["db_name"]
    assert called == f"{settings.DB_NAME_PREFIX}_commons", called
    assert "None" not in called


@pytest.mark.asyncio
@patch("app.database.database_setup.db_helper")
@patch("app.database.database_setup.create_some_collection", new_callable=AsyncMock)
async def test_create_request_log_collection(mock_create_some, mock_db_helper):
    """Test create_request_log_collection creates collection with correct index config."""
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    # Patched, not merely mocked out: the backfill this now runs first would
    # otherwise reach a real MongoDB from a unit test.
    mock_db_helper.backfill_created_at_from_id_async = AsyncMock(return_value=0)

    await create_request_log_collection(tenant_id=TENANT_ID)

    expected_name = settings.DB_COLLECTION_NAME_REQUEST_LOG
    # Issue #182: keyed on the paths a request log document actually has -
    # `store_code` and `terminal_no` live under `terminal_info`, so at the top
    # level they indexed as null and the constraint was one request per tenant
    # per timestamp. No longer unique either: an audit trail should not be the
    # thing that decides a record did not happen.
    expected_index_key_list = [
        {
            "keys": {
                "tenant_id": 1,
                "terminal_info.store_code": 1,
                "terminal_info.terminal_no": 1,
                "request_info.accept_time": 1,
            },
            "unique": False,
        },
        # Issue #221: the collection had no way to shrink. Keyed on `created_at`
        # alone, which is a different key pattern from the index above on
        # purpose - MongoDB will not swap options on an existing pattern.
        {
            "keys": {"created_at": 1},
            "unique": False,
            "expireAfterSeconds": settings.REQUEST_LOG_TTL_SECONDS,
        },
    ]

    # Twice: the buffer writes every request log to the tenant database AND to
    # `{prefix}_commons`, and provisioning used to reach only the first, leaving
    # the commons copy with no index and no expiry (issue #221). tenant_id=None
    # is how create_some_collection addresses the commons database.
    drop = [{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}]
    assert mock_create_some.await_count == 2
    for expected_target, call in zip((TENANT_ID, None), mock_create_some.await_args_list):
        assert call.kwargs == {
            "tenant_id": expected_target,
            "collection_name": expected_name,
            "index_keys_list": expected_index_key_list,
            "index_name": expected_name + "_index",
            "drop_indexes_by_keys": drop,
        }


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
