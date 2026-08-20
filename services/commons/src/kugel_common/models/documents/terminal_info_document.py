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
from typing import Optional
from pydantic import ConfigDict, Field
from kugel_common.utils.misc import to_lower_camel
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument

class TerminalInfoDocument(AbstractDocument):
    """
    Document model representing terminal information.
    
    This class extends AbstractDocument to store and manage information about POS terminals,
    including their identification, operational state, business date, and associated staff.
    It serves as the core model for terminal management and operations.
    """
    tenant_id: str = None
    store_code: str = None
    terminal_no: int = None
    description: Optional[str] = None
    terminal_id: Optional[str] = None
    function_mode: Optional[str] = None
    status: Optional[str] = None
    business_date: Optional[str] = None
    open_counter: Optional[int] = None
    business_counter: Optional[int] = None
    # Client-carried cart phase 2 (issue #156): continuous, customer-facing
    # receipt number counter. Terminal service is its durable home; it seeds the
    # current value at open and the terminal carries/advances it during the
    # session (see FR-012). Carried in the terminal token claims.
    receipt_no: Optional[int] = None
    # Durable home of the terminal's running receipt counter (issue #166). The
    # terminal advances it offline and presents it at open, where max() picks the
    # higher value so a number is never reused. receipt_no above is the pre-#166
    # spelling of the same value and is kept until clients have migrated.
    receipt_counter: Optional[int] = None
    staff: Optional[StaffMasterDocument] = None
    initial_amount: Optional[float] = None
    physical_amount: Optional[float] = None
    api_key: Optional[str] = None
    jwt_token: Optional[str] = Field(default=None, exclude=True)
    tags: Optional[list[str]] = None

    # camel case
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)