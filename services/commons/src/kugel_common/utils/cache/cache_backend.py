# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Abstract cache backend interface.

Backend implementations MUST NOT raise exceptions for backend connectivity
or serialization failures. They return None / False to indicate failure so
the caller can gracefully fall back to the source of truth.
"""
from abc import ABC, abstractmethod
from typing import Optional


class AbstractCacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[dict]:
        """Return the cached dict, or None on miss / backend error."""
        ...

    @abstractmethod
    async def set(self, key: str, value: dict, ttl_seconds: int) -> bool:
        """Persist value with TTL. Return True on success, False on backend error."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove the entry. Return True on success or already absent, False on error."""
        ...

    @abstractmethod
    async def increment(self, key: str) -> Optional[int]:
        """
        Increment an integer counter at the key.

        Implementations should aim for atomicity but are permitted to use
        read-then-write under high contention; lost updates are acceptable
        for the generation-counter use case (any successful bump invalidates
        prior entries).

        Returns the new value, or None on backend error.
        """
        ...

    async def close(self) -> None:
        """Optional teardown hook (e.g., close underlying HTTP clients)."""
        return None
