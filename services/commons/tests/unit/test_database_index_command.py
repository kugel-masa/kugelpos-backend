# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""Unit tests for create_indexes_command, including TTL (expireAfterSeconds) support."""
import pytest

from kugel_common.database.database import create_indexes_command


pytestmark = pytest.mark.unit


def test_basic_index_command():
    cmd = create_indexes_command(
        collection_name="cache_cart", index_keys={"cart_id": 1}, index_name="cache_cart_index", unique=True
    )
    assert cmd["createIndexes"] == "cache_cart"
    assert len(cmd["indexes"]) == 1
    index = cmd["indexes"][0]
    assert index["key"] == {"cart_id": 1}
    assert index["name"] == "cache_cart_index"
    assert index["unique"] is True
    assert "expireAfterSeconds" not in index
    assert "partialFilterExpression" not in index


def test_ttl_index_includes_expire_after_seconds():
    cmd = create_indexes_command(
        collection_name="cache_cart",
        index_keys={"created_at": 1},
        index_name="cache_cart_ttl",
        expire_after_seconds=36000,
    )
    index = cmd["indexes"][0]
    assert index["key"] == {"created_at": 1}
    assert index["expireAfterSeconds"] == 36000


def test_expire_after_seconds_zero_is_emitted():
    # expireAfterSeconds=0 is valid (expire immediately when the date is reached);
    # it must not be dropped as a falsy value.
    cmd = create_indexes_command(
        collection_name="c", index_keys={"created_at": 1}, index_name="c_ttl", expire_after_seconds=0
    )
    assert cmd["indexes"][0]["expireAfterSeconds"] == 0


def test_no_ttl_when_not_specified():
    cmd = create_indexes_command(collection_name="c", index_keys={"a": 1}, index_name="c_idx")
    assert "expireAfterSeconds" not in cmd["indexes"][0]
