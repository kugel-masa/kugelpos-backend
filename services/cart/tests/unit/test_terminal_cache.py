"""
Unit tests for TerminalInfoCache.
"""

import time
import pytest
from unittest.mock import MagicMock

from app.utils.terminal_cache import TerminalInfoCache
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument


def create_mock_terminal_info(terminal_id: str) -> TerminalInfoDocument:
    """Create a mock TerminalInfoDocument for testing."""
    return TerminalInfoDocument(
        tenant_id="test_tenant",
        terminal_id=terminal_id,
        store_code="STORE01",
        terminal_no="001",
        status="active",
        staff=None,
    )


class TestTerminalInfoCache:
    """Test cases for TerminalInfoCache class."""

    def test_cache_initialization(self):
        """Test cache initialization with custom TTL."""
        cache = TerminalInfoCache(ttl_seconds=60)
        assert cache._ttl == 60
        assert cache.size() == 0

    def test_cache_set_and_get(self):
        """Test setting and getting items from cache."""
        cache = TerminalInfoCache(ttl_seconds=300)
        terminal_id = "test_tenant-STORE01-001"
        terminal_info = create_mock_terminal_info(terminal_id)

        # Set item in cache
        cache.set(terminal_id, terminal_info)
        assert cache.size() == 1

        # Get item from cache
        cached_info = cache.get(terminal_id)
        assert cached_info is not None
        assert cached_info.terminal_id == terminal_id
        assert cached_info.store_code == "STORE01"

    def test_cache_miss(self):
        """Test getting non-existent item from cache."""
        cache = TerminalInfoCache()
        result = cache.get("non_existent_id")
        assert result is None

    def test_cache_expiration(self):
        """Test that cached items expire after TTL."""
        cache = TerminalInfoCache(ttl_seconds=1)  # 1 second TTL
        terminal_id = "test_tenant-STORE01-001"
        terminal_info = create_mock_terminal_info(terminal_id)

        # Set item in cache
        cache.set(terminal_id, terminal_info)
        assert cache.get(terminal_id) is not None

        # Wait for expiration
        time.sleep(1.1)
        assert cache.get(terminal_id) is None
        assert cache.size() == 0  # Expired entry should be removed

    def test_cache_clear_all(self):
        """Test clearing all items from cache."""
        cache = TerminalInfoCache()

        # Add multiple items from different tenants
        cache.set("tenant1-STORE01-001", create_mock_terminal_info("tenant1-STORE01-001"))
        cache.set("tenant1-STORE01-002", create_mock_terminal_info("tenant1-STORE01-002"))
        cache.set("tenant2-STORE01-001", create_mock_terminal_info("tenant2-STORE01-001"))

        assert cache.size() == 3

        # Clear all cache
        cache.clear()
        assert cache.size() == 0

    def test_cache_clear_by_tenant(self):
        """Test clearing items for specific tenant from cache."""
        cache = TerminalInfoCache()

        # Add items from different tenants
        cache.set("tenant1-STORE01-001", create_mock_terminal_info("tenant1-STORE01-001"))
        cache.set("tenant1-STORE01-002", create_mock_terminal_info("tenant1-STORE01-002"))
        cache.set("tenant2-STORE01-001", create_mock_terminal_info("tenant2-STORE01-001"))

        assert cache.size() == 3
        assert cache.size("tenant1") == 2
        assert cache.size("tenant2") == 1

        # Clear only tenant1 cache
        cache.clear("tenant1")
        assert cache.size() == 1
        assert cache.size("tenant1") == 0
        assert cache.size("tenant2") == 1

        # Verify tenant2 data still exists
        assert cache.get("tenant2-STORE01-001") is not None

    def test_cache_remove(self):
        """Test removing specific item from cache."""
        cache = TerminalInfoCache()
        terminal_id1 = "test_tenant-STORE01-001"
        terminal_id2 = "test_tenant-STORE01-002"

        # Add items
        cache.set(terminal_id1, create_mock_terminal_info(terminal_id1))
        cache.set(terminal_id2, create_mock_terminal_info(terminal_id2))
        assert cache.size() == 2

        # Remove one item
        cache.remove(terminal_id1)
        assert cache.size() == 1
        assert cache.get(terminal_id1) is None
        assert cache.get(terminal_id2) is not None

    def test_cache_update(self):
        """Test updating existing item in cache."""
        cache = TerminalInfoCache()
        terminal_id = "test_tenant-STORE01-001"

        # Set initial item
        initial_info = create_mock_terminal_info(terminal_id)
        cache.set(terminal_id, initial_info)

        # Update with new info
        updated_info = create_mock_terminal_info(terminal_id)
        updated_info.status = "inactive"
        cache.set(terminal_id, updated_info)

        # Verify update
        cached_info = cache.get(terminal_id)
        assert cached_info.status == "inactive"
        assert cache.size() == 1  # Should still be one item

    def test_get_tenant_terminal_ids(self):
        """Test getting terminal IDs for specific tenant."""
        cache = TerminalInfoCache()

        # Add items from different tenants
        cache.set("tenant1-STORE01-001", create_mock_terminal_info("tenant1-STORE01-001"))
        cache.set("tenant1-STORE01-002", create_mock_terminal_info("tenant1-STORE01-002"))
        cache.set("tenant2-STORE01-001", create_mock_terminal_info("tenant2-STORE01-001"))

        # Get terminal IDs for tenant1
        tenant1_ids = cache.get_tenant_terminal_ids("tenant1")
        assert len(tenant1_ids) == 2
        assert "tenant1-STORE01-001" in tenant1_ids
        assert "tenant1-STORE01-002" in tenant1_ids

        # Get terminal IDs for tenant2
        tenant2_ids = cache.get_tenant_terminal_ids("tenant2")
        assert len(tenant2_ids) == 1
        assert "tenant2-STORE01-001" in tenant2_ids

        # Get terminal IDs for non-existent tenant
        tenant3_ids = cache.get_tenant_terminal_ids("tenant3")
        assert len(tenant3_ids) == 0
