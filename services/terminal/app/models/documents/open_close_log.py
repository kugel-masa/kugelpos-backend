# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument
from app.models.documents.terminal_info_document import TerminalInfoDocument


class OpenCloseLog(AbstractDocument):
    """
    Open/Close Log Document

    This class represents a terminal opening or closing record in the POS system.
    It tracks each time a terminal is opened for business or closed at the end of
    a business session, along with summary information about the business session.

    Each record contains information about the terminal state, associated staff,
    and transaction summaries for the business session.
    """

    tenant_id: Optional[str] = None  # Tenant ID that owns this record
    store_code: Optional[str] = None  # Store code where the terminal is located
    store_name: Optional[str] = None  # Name of the store for display purposes
    terminal_no: Optional[int] = None  # Terminal number that was opened/closed
    staff_id: Optional[str] = None  # ID of the staff member who performed the operation
    staff_name: Optional[str] = None  # Name of the staff member for display purposes
    business_date: Optional[str] = None  # Business date when the operation occurred (YYYYMMDD)
    open_counter: Optional[int] = None  # Terminal open counter for this business session
    business_counter: Optional[int] = None  # Business counter at the time of operation
    operation: Optional[str] = None  # Type of operation: 'open' or 'close'
    generate_date_time: Optional[str] = None  # Timestamp when the operation occurred
    terminal_info: Optional[TerminalInfoDocument] = None  # Terminal state at the time of operation
    cart_transaction_count: Optional[int] = None  # Number of cart transactions during the session
    cart_transaction_last_no: Optional[int] = None  # Last transaction number during the session
    cash_in_out_count: Optional[int] = None  # Number of cash in/out operations during the session
    cash_in_out_last_datetime: Optional[str] = None  # Timestamp of the last cash in/out operation
    receipt_text: Optional[str] = None  # Formatted text for receipts
    journal_text: Optional[str] = None  # Formatted text for journal entries
