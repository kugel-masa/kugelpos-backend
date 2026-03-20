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
import pytest

from app.utils.json_settings import is_json_serializable, ensure_json_format, process_setting_values


class TestIsJsonSerializable:
    """Tests for is_json_serializable()."""

    def test_non_string_input_returns_false(self):
        """Non-string values (int, None, list) must return False."""
        assert is_json_serializable(123) is False
        assert is_json_serializable(None) is False
        assert is_json_serializable([1, 2]) is False

    def test_plain_string_returns_false(self):
        assert is_json_serializable("hello") is False

    def test_json_array_string_returns_true(self):
        assert is_json_serializable('[{"key": "val"}]') is True

    def test_json_object_string_returns_true(self):
        assert is_json_serializable('{"key": "val"}') is True

    def test_string_with_whitespace_returns_true(self):
        assert is_json_serializable('  [1, 2, 3]  ') is True

    def test_mixed_brackets_returns_true(self):
        """Starts with [ and ends with } -- both are valid start/end chars."""
        assert is_json_serializable("[1, 2}") is True

    def test_no_matching_end_returns_false(self):
        """Starts with [ but ends with a non-bracket char."""
        assert is_json_serializable("[1, 2") is False

    def test_empty_brackets_returns_true(self):
        assert is_json_serializable("[]") is True
        assert is_json_serializable("{}") is True


class TestEnsureJsonFormat:
    """Tests for ensure_json_format()."""

    def test_non_json_string_returned_as_is(self):
        assert ensure_json_format("plain text") == "plain text"

    def test_valid_json_returned_normalized(self):
        result = ensure_json_format('[{"text": "Hello"}]')
        assert result == '[{"text": "Hello"}]'

    def test_python_literal_converted_to_json(self):
        """Single-quoted Python dict/list should be converted to double-quoted JSON."""
        result = ensure_json_format("[{'text': 'Hello', 'align': 'left'}]")
        assert result == '[{"text": "Hello", "align": "left"}]'

    def test_malformed_json_returned_as_is(self):
        """Neither valid JSON nor valid Python literal -- return original."""
        malformed = "[{bad json content!}]"
        result = ensure_json_format(malformed)
        assert result == malformed

    def test_valid_json_object(self):
        result = ensure_json_format('{"a": 1}')
        assert result == '{"a": 1}'

    def test_python_dict_literal(self):
        result = ensure_json_format("{'a': 1, 'b': 2}")
        assert result == '{"a": 1, "b": 2}'


class TestProcessSettingValues:
    """Tests for process_setting_values()."""

    def test_dict_with_value_key_gets_processed(self):
        values = [{"value": "[{'text': 'Hello'}]", "store_code": "S1"}]
        result = process_setting_values(values)
        assert result[0]["value"] == '[{"text": "Hello"}]'
        assert result[0]["store_code"] == "S1"

    def test_dict_without_value_key_unchanged(self):
        values = [{"store_code": "S1", "terminal_no": 1}]
        result = process_setting_values(values)
        assert result == values

    def test_dict_with_non_string_value_unchanged(self):
        values = [{"value": 42}]
        result = process_setting_values(values)
        assert result[0]["value"] == 42

    def test_original_dict_not_modified(self):
        original = {"value": "[{'a': 1}]", "extra": "data"}
        values = [original]
        process_setting_values(values)
        # Original dict should NOT be mutated
        assert original["value"] == "[{'a': 1}]"

    def test_empty_list(self):
        assert process_setting_values([]) == []

    def test_plain_string_value_unchanged(self):
        values = [{"value": "plain"}]
        result = process_setting_values(values)
        assert result[0]["value"] == "plain"
