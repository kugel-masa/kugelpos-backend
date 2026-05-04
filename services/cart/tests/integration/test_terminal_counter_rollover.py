"""
Test for terminal counter rollover functionality.

This test verifies that the counter correctly rolls over from end_value to start_value
using atomic MongoDB operations.
"""
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.repositories.terminal_counter_repository import TerminalCounterRepository
from app.config.settings import settings


@pytest_asyncio.fixture
async def motor_client():
    """Create a MongoDB client for testing."""
    import os
    # Use localhost with directConnection for local testing to avoid replica set hostname resolution
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true")
    client = AsyncIOMotorClient(mongodb_uri)
    yield client
    client.close()


@pytest_asyncio.fixture
async def terminal_info():
    """Create a test terminal info document."""
    return TerminalInfoDocument(
        tenant_id="TEST_TENANT",
        store_code="TEST_STORE",
        terminal_no=99,
        terminal_id="TEST_TENANT-TEST_STORE-99",
        description="Test Terminal for Counter Rollover",
        function_mode="Sales",
        status="Opened",
        business_date="20251215",
        open_counter=1,
        business_counter=1,
        staff=None,
        initial_amount=0.0,
        physical_amount=None,
        api_key="test_api_key"
    )


@pytest_asyncio.fixture
async def counter_repo(motor_client, terminal_info):
    """Create a terminal counter repository for testing."""
    db = motor_client[f"{settings.DB_NAME_PREFIX}_TEST_TENANT"]
    repo = TerminalCounterRepository(db=db, terminal_info=terminal_info)
    await repo.initialize()

    # Clean up existing test data
    await db[settings.DB_COLLECTION_NAME_TERMINAL_COUTER].delete_many({
        "terminal_id": terminal_info.terminal_id
    })

    yield repo

    # Cleanup after test
    await db[settings.DB_COLLECTION_NAME_TERMINAL_COUTER].delete_many({
        "terminal_id": terminal_info.terminal_id
    })


@pytest.mark.asyncio
async def test_counter_rollover_at_end_value(counter_repo):
    """
    Test that counter correctly rolls over from end_value to start_value.

    Scenario:
    1. Set a small end_value (e.g., 5) for testing
    2. Increment counter from 1 to 5
    3. Verify that next increment rolls over to start_value (1)
    """
    counter_type = "TestCounter"
    start_value = 1
    end_value = 5

    # First increment: should return start_value (1)
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 1, f"First increment should return {start_value}, got {count}"

    # Second increment: should return 2
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 2, f"Second increment should return 2, got {count}"

    # Third increment: should return 3
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 3, f"Third increment should return 3, got {count}"

    # Fourth increment: should return 4
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 4, f"Fourth increment should return 4, got {count}"

    # Fifth increment: should return 5 (end_value)
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 5, f"Fifth increment should return {end_value}, got {count}"

    # Sixth increment: should rollover to start_value (1)
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 1, f"Sixth increment should rollover to {start_value}, got {count}"

    # Seventh increment: should return 2 (continuing after rollover)
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 2, f"Seventh increment should return 2 after rollover, got {count}"


@pytest.mark.asyncio
async def test_counter_rollover_with_non_default_start(counter_repo):
    """
    Test rollover with non-default start_value.

    Scenario:
    1. Use start_value=10, end_value=12
    2. Increment from 10 to 12
    3. Verify rollover to 10
    """
    counter_type = "TestCounterNonDefault"
    start_value = 10
    end_value = 12

    # First increment: should return 10
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 10, f"First increment should return {start_value}, got {count}"

    # Second increment: should return 11
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 11, f"Second increment should return 11, got {count}"

    # Third increment: should return 12 (end_value)
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 12, f"Third increment should return {end_value}, got {count}"

    # Fourth increment: should rollover to 10
    count = await counter_repo.numbering_count(counter_type, start_value, end_value)
    assert count == 10, f"Fourth increment should rollover to {start_value}, got {count}"


@pytest.mark.asyncio
async def test_counter_multiple_rollovers(counter_repo):
    """
    Test that counter can rollover multiple times correctly.

    Scenario:
    1. Use start_value=1, end_value=3
    2. Perform multiple rollovers
    3. Verify each rollover works correctly
    """
    counter_type = "TestCounterMultiple"
    start_value = 1
    end_value = 3

    expected_sequence = [1, 2, 3, 1, 2, 3, 1, 2, 3, 1]

    for i, expected in enumerate(expected_sequence, 1):
        count = await counter_repo.numbering_count(counter_type, start_value, end_value)
        assert count == expected, (
            f"Iteration {i}: expected {expected}, got {count}. "
            f"Sequence so far: {expected_sequence[:i]}"
        )


@pytest.mark.asyncio
async def test_counter_no_rollover_when_below_end_value(counter_repo):
    """
    Test that counter does not rollover when below end_value.

    Scenario:
    1. Use a large end_value
    2. Increment several times
    3. Verify no unexpected rollovers occur
    """
    counter_type = "TestCounterNoRollover"
    start_value = 1
    end_value = 1000

    # Increment 10 times
    for expected in range(1, 11):
        count = await counter_repo.numbering_count(counter_type, start_value, end_value)
        assert count == expected, f"Expected {expected}, got {count}"


@pytest.mark.asyncio
async def test_concurrent_counter_access_with_rollover(counter_repo):
    """
    Test that concurrent access during rollover produces unique sequential values.

    This test simulates concurrent requests near the rollover boundary.
    Even though MongoDB serializes the operations, we verify that all
    returned values are unique and sequential.
    """
    import asyncio

    counter_type = "TestCounterConcurrent"
    start_value = 1
    end_value = 5

    # Pre-increment to get close to rollover (set counter to 4)
    await counter_repo.numbering_count(counter_type, start_value, end_value)
    await counter_repo.numbering_count(counter_type, start_value, end_value)
    await counter_repo.numbering_count(counter_type, start_value, end_value)
    await counter_repo.numbering_count(counter_type, start_value, end_value)

    # Now at 4, next should be 5, then rollover to 1, then 2
    # Launch 3 concurrent increments
    tasks = [
        counter_repo.numbering_count(counter_type, start_value, end_value)
        for _ in range(3)
    ]

    results = await asyncio.gather(*tasks)

    # Results should be [5, 1, 2] in some order (MongoDB serializes them)
    # But all values should be unique
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert len(set(results)) == 3, f"Expected all unique values, got {results}"

    # Verify the results contain the expected values
    expected_values = {5, 1, 2}
    actual_values = set(results)
    assert actual_values == expected_values, (
        f"Expected values {expected_values}, got {actual_values}"
    )
