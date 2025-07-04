# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument


class CashInOutLog(AbstractDocument):
    """
    Document class representing a cash drawer operation log.

    This class stores information about cash operations such as adding or
    removing cash from the terminal drawer. These operations include activities
    like adding float/bank at the start of a day, removing excess cash,
    or adding additional cash when needed.
    """

    tenant_id: Optional[str] = None  # Identifier for the tenant
    store_code: Optional[str] = None  # Identifier for the store
    store_name: Optional[str] = None  # Name of the store
    terminal_no: Optional[int] = None  # Terminal number
    staff_id: Optional[str] = None  # ID of staff performing the operation
    staff_name: Optional[str] = None  # Name of staff performing the operation
    business_date: Optional[str] = None  # Business date for the operation
    open_counter: Optional[int] = None  # Counter for terminal open/close cycles
    business_counter: Optional[int] = None  # Business counter for the day
    generate_date_time: Optional[str] = None  # Date and time when the log was generated
    amount: Optional[float] = None  # Amount of cash added (positive) or removed (negative)
    description: Optional[str] = None  # Description of the cash operation
    receipt_text: Optional[str] = None  # Formatted text for receipt printing
    journal_text: Optional[str] = None  # Formatted text for journal
