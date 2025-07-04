# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument


class OpenCloseLog(AbstractDocument):
    """
    Document class representing a terminal open/close operation log.

    This class stores information about terminal opening and closing operations,
    including counts of transactions and cash operations during the session.
    It is used to track terminal activity periods and validate that all
    transactions are accounted for when generating reports.
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
    operation: Optional[str] = None  # Type of operation ('open' or 'close')
    generate_date_time: Optional[str] = None  # Date and time when the log was generated
    terminal_info: Optional[TerminalInfoDocument] = None  # Terminal information
    cart_transaction_count: Optional[int] = None  # Count of transactions during the session
    cart_transaction_last_no: Optional[int] = None  # Last transaction number in the session
    cash_in_out_count: Optional[int] = None  # Count of cash operations during the session
    cash_in_out_last_datetime: Optional[str] = None  # Timestamp of the last cash operation
    receipt_text: Optional[str] = None  # Formatted text for receipt printing
    journal_text: Optional[str] = None  # Formatted text for journal
