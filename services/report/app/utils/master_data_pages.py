# Copyright 2026 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""Paging through a master-data list, shared by the report makers (#313, #326)."""

import logging
from typing import Optional

MASTER_DATA_PAGE_SIZE = 100

# A guard against a server that never says it is done: 100 pages of 100 rows
MAX_MASTER_DATA_PAGES = 100

logger = logging.getLogger(__name__)


def has_next_page(metadata: Optional[dict], page: int, received: int, page_size: int = MASTER_DATA_PAGE_SIZE) -> bool:
    """
    Whether a master-data list has a page after ``page``.

    master-data answers ``total`` in the metadata; ``has_next`` and
    ``total_pages`` are honoured as well. Without any of them, a full page
    means there may be another. Reading stops after MAX_MASTER_DATA_PAGES.

    Args:
        metadata: The response's metadata, if any
        page: The page just read (1-based)
        received: How many records that page held
        page_size: The page size requested

    Returns:
        bool: True when another page should be read
    """
    if received == 0:
        return False
    if page >= MAX_MASTER_DATA_PAGES:
        logger.warning(f"Stopped reading a master-data list after {page} pages")
        return False
    if metadata:
        has_next = metadata.get("has_next", metadata.get("hasNext"))
        if has_next is not None:
            return bool(has_next)
        total_pages = metadata.get("total_pages", metadata.get("totalPages"))
        if total_pages is not None:
            return page < total_pages
        total = metadata.get("total")
        if total is not None:
            return page * page_size < total
    return received >= page_size
