"""
Terminal information cache for reducing HTTP calls to terminal service.
"""

import time
from typing import Dict, Optional, Tuple, List
from logging import getLogger

logger = getLogger(__name__)

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.config.settings import settings


class TerminalInfoCache:
    """Local cache for terminal information with TTL support."""

    def __init__(self, ttl_seconds: int = 300):  # 5分間のTTL
        """
        Initialize the terminal info cache.

        Args:
            ttl_seconds: Time to live for cached entries in seconds (default: 300)
        """
        self._cache: Dict[str, Tuple[TerminalInfoDocument, float]] = {}
        self._ttl = ttl_seconds

    def get(self, terminal_id: str) -> Optional[TerminalInfoDocument]:
        """
        Get terminal info from cache if available and not expired.

        Args:
            terminal_id: The terminal ID to look up

        Returns:
            TerminalInfoDocument if found and not expired, None otherwise
        """

        # If cache is disabled, return None immediately
        if not settings.USE_TERMINAL_CACHE:
            logger.debug("Terminal cache is disabled, returning None")
            return None

        if terminal_id in self._cache:
            terminal_info, timestamp = self._cache[terminal_id]
            if time.time() - timestamp < self._ttl:
                logger.debug(f"Terminal cache hit for {terminal_id}")
                return terminal_info
            # Remove expired entry
            del self._cache[terminal_id]

        logger.debug(f"Terminal cache miss for {terminal_id}")
        return None

    def set(self, terminal_id: str, terminal_info: TerminalInfoDocument) -> None:
        """
        Store terminal info in cache with current timestamp.

        Args:
            terminal_id: The terminal ID to cache
            terminal_info: The terminal info document to cache
        """
        self._cache[terminal_id] = (terminal_info, time.time())

    def clear(self, tenant_id: Optional[str] = None) -> None:
        """
        Clear cached entries.

        Args:
            tenant_id: If provided, clear only entries for this tenant.
                      If None, clear all entries.
        """
        if tenant_id is None:
            self._cache.clear()
        else:
            # Extract terminal IDs that belong to the specified tenant
            keys_to_remove = [
                terminal_id for terminal_id in self._cache.keys() if terminal_id.startswith(f"{tenant_id}-")
            ]
            for key in keys_to_remove:
                self._cache.pop(key, None)

    def remove(self, terminal_id: str) -> None:
        """
        Remove a specific terminal from cache.

        Args:
            terminal_id: The terminal ID to remove
        """
        self._cache.pop(terminal_id, None)

    def size(self, tenant_id: Optional[str] = None) -> int:
        """
        Get the number of items in cache.

        Args:
            tenant_id: If provided, count only entries for this tenant.
                      If None, count all entries.

        Returns:
            Number of cached items
        """
        if tenant_id is None:
            return len(self._cache)
        else:
            # Count only entries that belong to the specified tenant
            return sum(1 for terminal_id in self._cache.keys() if terminal_id.startswith(f"{tenant_id}-"))

    def get_tenant_terminal_ids(self, tenant_id: str) -> List[str]:
        """
        Get all terminal IDs cached for a specific tenant.

        Args:
            tenant_id: The tenant ID to filter by

        Returns:
            List of terminal IDs for the tenant
        """
        return [terminal_id for terminal_id in self._cache.keys() if terminal_id.startswith(f"{tenant_id}-")]
