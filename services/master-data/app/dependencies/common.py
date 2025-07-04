# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Common dependency functions for master-data service.

This module provides shared helper functions and dependencies that are used
across multiple API endpoints.
"""
from fastapi import Query


def parse_sort(sort: str = Query(default=None, description="?sort=field1:1,field2:-1")) -> list[tuple[str, int]]:
    """
    Parse the sort query parameter into a list of field-order tuples.

    Format example: ?sort=field1:1,field2:-1
    Where 1 means ascending order and -1 means descending order.

    Args:
        sort: String representation of sort parameters

    Returns:
        list[tuple[str, int]]: List of tuples with field name and sort order
    """
    sort_list = []
    if sort is None:
        # Default sort by category code in ascending order
        sort_list = [("category_code", 1)]
    else:
        # Parse sort query parameter into list of tuples
        sort_list = [tuple(item.split(":")) for item in sort.split(",")]
        sort_list = [(field, int(order)) for field, order in sort_list]
    return sort_list
