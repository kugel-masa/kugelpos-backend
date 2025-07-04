# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument


class DailyInfoDocument(AbstractDocument):
    """
    Document class representing daily information for terminal verification.

    This class stores information about the verification status of terminal data
    for a specific business date and open counter. It is used to track whether
    all required logs (transactions, cash operations) for a terminal have been
    properly collected and validated for report generation.
    """

    tenant_id: Optional[str] = None  # Identifier for the tenant
    store_code: Optional[str] = None  # Identifier for the store
    terminal_no: Optional[int] = None  # Terminal number
    business_date: Optional[str] = None  # Business date for the verification
    open_counter: Optional[int] = None  # Counter for terminal open/close cycles
    verified: Optional[bool] = None  # Verification status (True if verified, False if failed)
    verified_update_time: Optional[str] = None  # Timestamp of the last verification
    verified_message: Optional[str] = None  # Message describing verification status
