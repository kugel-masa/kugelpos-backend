# Copyright 2026 masa@kugel
"""
Logical delete shared by every deletable master (issue #324).

A deleted record keeps its row with ``is_deleted: True``. Every read that is
not asked for deleted records filters them out with ``NOT_DELETED``, which
also treats a record without the field as live, so records written before the
field existed need no migration.

The unique indexes are unchanged, so a deleted record keeps its code: creating
the code again restores the record (see ``restore_async``).
"""

from typing import Any

NOT_DELETED = {"is_deleted": {"$ne": True}}


def alive(query_filter: dict, include_deleted: bool = False) -> dict:
    """
    The filter a read should use.

    Args:
        query_filter: The caller's filter; it is not changed
        include_deleted: True to see deleted records as well

    Returns:
        A copy of the filter, limited to live records unless include_deleted
    """
    filtered = dict(query_filter)
    if not include_deleted:
        filtered.update(NOT_DELETED)
    return filtered


async def soft_delete_async(repo: Any, key_filter: dict) -> bool:
    """
    Mark a live record deleted.

    Args:
        repo: The master's repository (an AbstractRepository)
        key_filter: The filter naming the record by its key

    Returns:
        bool: False when no live record matched (missing or already deleted)
    """
    return await repo.update_one_async(alive(key_filter), {"is_deleted": True})


async def restore_async(repo: Any, key_filter: dict, document: Any) -> bool:
    """
    Replace a deleted record with a new document, which restores it.

    The caller stamps the document as its create does (tenant, shard key,
    created_at) and sets ``is_deleted`` to False; replace_one stamps only
    updated_at.

    Args:
        repo: The master's repository (an AbstractRepository)
        key_filter: The filter naming the record by its key
        document: The new document

    Returns:
        bool: False when no deleted record matched (restored or removed meanwhile)
    """
    return await repo.replace_one_async({**key_filter, "is_deleted": True}, document)
