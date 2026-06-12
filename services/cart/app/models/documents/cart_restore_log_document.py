# Copyright 2026 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Audit record for cart snapshot restore attempts (issue #148)
"""
from typing import Optional
from kugel_common.models.documents.abstract_document import AbstractDocument


class CartRestoreLogDocument(AbstractDocument):
    """
    Audit trail of restore API usage.

    One record per restore attempt — success, existing-cart-returned, or
    rejection — so that snapshot replays and verification failures can be
    traced after the fact (replay posture is accept + detect).
    """

    # Requesting terminal (from the authenticated context)
    tenant_id: str
    store_code: str
    terminal_no: int

    # Target cart (from the presented snapshot)
    cart_id: Optional[str] = None

    # Outcome: "restored" / "existing_returned" / "rejected"
    result: str
    # Cart error code on rejection (e.g. 401501); None on success
    reject_reason: Optional[str] = None
    # True when the presented snapshot differs from an existing cart
    diverged: bool = False

    # Snapshot metadata (from the presented envelope, when parseable)
    snapshot_issued_at: Optional[str] = None
    snapshot_terminal_no: Optional[int] = None
    snapshot_kid: Optional[str] = None
    snapshot_schema_version: Optional[int] = None

    # Record time
    event_datetime: str
