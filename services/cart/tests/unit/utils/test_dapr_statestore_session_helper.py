# Copyright 2025 masa@kugel
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

"""
Unit tests for dapr_statestore_session_helper module.

Tests verify connection pooling behavior, session lifecycle management,
and configuration of the shared aiohttp session.
"""

import pytest
import aiohttp
from app.utils.dapr_statestore_session_helper import (
    get_dapr_statestore_session,
    close_dapr_statestore_session,
)


@pytest.mark.asyncio
async def test_get_session_creates_new_session():
    """
    Test that get_session creates a session on first call.

    Verifies:
    - Session is created
    - Session is an aiohttp.ClientSession instance
    - Session is not closed
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session = await get_dapr_statestore_session()

    assert session is not None
    assert isinstance(session, aiohttp.ClientSession)
    assert not session.closed

    # Cleanup
    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_get_session_reuses_existing_session():
    """
    Test that get_session reuses the same session instance.

    This is the core behavior for connection pooling - multiple calls
    should return the exact same session object.

    Verifies:
    - Two calls return the same session instance
    - Session identity is preserved (using `is` operator)
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session1 = await get_dapr_statestore_session()
    session2 = await get_dapr_statestore_session()

    # Should be the SAME object (not just equal, but identical)
    assert session1 is session2

    # Cleanup
    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_close_session():
    """
    Test that close_session properly closes the session.

    Verifies:
    - Session is open before close
    - Session is closed after close
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session = await get_dapr_statestore_session()
    assert not session.closed

    await close_dapr_statestore_session()
    assert session.closed


@pytest.mark.asyncio
async def test_get_session_after_close_creates_new_session():
    """
    Test that get_session creates a new session after close.

    This verifies proper lifecycle management - after closing,
    a new session should be created on the next call.

    Verifies:
    - First session is created
    - Session is closed
    - Second session is different from first
    - Second session is not closed
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session1 = await get_dapr_statestore_session()
    await close_dapr_statestore_session()

    session2 = await get_dapr_statestore_session()

    # Should be DIFFERENT objects (new session created)
    assert session1 is not session2
    assert not session2.closed

    # Cleanup
    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_session_timeout_configuration():
    """
    Test that session has correct timeout configuration.

    Verifies timeout settings match the implementation plan:
    - total: 10.0 seconds (complete request/response cycle)
    - connect: 3.0 seconds (connection establishment)
    - sock_read: 5.0 seconds (reading response data)
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session = await get_dapr_statestore_session()

    assert session.timeout.total == 10.0
    assert session.timeout.connect == 3.0
    assert session.timeout.sock_read == 5.0

    # Cleanup
    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_session_connector_configuration():
    """
    Test that session has correct connector configuration.

    Verifies connection pool settings match the implementation plan:
    - limit: 100 (max total concurrent connections)
    - limit_per_host: 50 (max connections to Dapr sidecar)
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session = await get_dapr_statestore_session()

    assert session.connector.limit == 100
    assert session.connector.limit_per_host == 50

    # Cleanup
    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_multiple_close_calls_are_safe():
    """
    Test that calling close multiple times doesn't cause errors.

    Verifies defensive programming - close should be idempotent.
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    session = await get_dapr_statestore_session()

    # Close multiple times - should not raise exception
    await close_dapr_statestore_session()
    await close_dapr_statestore_session()
    await close_dapr_statestore_session()

    assert session.closed


@pytest.mark.asyncio
async def test_close_without_session_is_safe():
    """
    Test that calling close when no session exists doesn't cause errors.

    Verifies defensive programming - close should handle None gracefully.
    """
    # Clean up any existing session first
    await close_dapr_statestore_session()

    # Close when no session exists - should not raise exception
    await close_dapr_statestore_session()
