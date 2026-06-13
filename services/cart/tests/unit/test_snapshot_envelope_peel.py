# Copyright 2026 masa@kugel
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
"""Unit tests for the phase 2 request snapshot envelope peel (issue #156)."""
import json

from app.middleware.snapshot_envelope import peel_snapshot_envelope


def test_wrapped_array_payload_is_peeled():
    """A wrapped body with an array payload yields the snapshot and the bare array."""
    env = {"schema_version": 1, "kid": "v1", "signature": "abc"}
    body = json.dumps({"signedSnapshot": env, "payload": [{"item_code": "X"}]}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot == env
    assert json.loads(new_body) == [{"item_code": "X"}]


def test_wrapped_object_payload_is_peeled():
    """A wrapped body with an object payload yields the snapshot and the bare object."""
    env = {"schema_version": 1}
    body = json.dumps({"signedSnapshot": env, "payload": {"quantity": 3}}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot == env
    assert json.loads(new_body) == {"quantity": 3}


def test_wrapped_without_payload_yields_empty_body():
    """Body-less operations wrap only the snapshot; forwarded body is empty."""
    env = {"schema_version": 1}
    body = json.dumps({"signedSnapshot": env}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot == env
    assert new_body == b""


def test_legacy_bare_array_passes_through():
    """A phase 1 bare array (no signedSnapshot key) is returned unchanged."""
    body = json.dumps([{"item_code": "X"}]).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert new_body == body


def test_legacy_bare_object_passes_through():
    """A phase 1 bare object without the wrapper key is returned unchanged."""
    body = json.dumps({"quantity": 3}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert new_body == body


def test_empty_body_passes_through():
    snapshot, new_body = peel_snapshot_envelope(b"")
    assert snapshot is None
    assert new_body == b""


def test_non_json_body_passes_through():
    """Malformed / non-JSON bodies never raise and pass through untouched."""
    body = b"not json at all"
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert new_body == body


def test_null_snapshot_value_is_returned_as_none_path():
    """An explicit null signedSnapshot is treated as present-but-null (no crash)."""
    body = json.dumps({"signedSnapshot": None, "payload": [{"a": 1}]}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert json.loads(new_body) == [{"a": 1}]
