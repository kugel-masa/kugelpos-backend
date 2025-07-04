# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from pydantic import Field
from app.api.common.schemas import BaseJournalSchema
from app.models.documents.jornal_document import JournalDocument

logger = getLogger(__name__)


class SchemasTransformer:

    def __init__(self):
        pass

    def transform_journal_response(self, journal_doc: JournalDocument) -> BaseJournalSchema:
        return BaseJournalSchema(
            tenant_id=journal_doc.tenant_id,
            store_code=journal_doc.store_code,
            terminal_no=journal_doc.terminal_no,
            transaction_no=journal_doc.transaction_no,
            journal_seq_no=-1,
            transaction_type=journal_doc.transaction_type,
            business_date=journal_doc.business_date,
            open_counter=journal_doc.open_counter,
            business_counter=journal_doc.business_counter,
            generate_date_time=journal_doc.generate_date_time,
            receipt_no=journal_doc.receipt_no,
            amount=journal_doc.amount,
            quantity=journal_doc.quantity,
            staff_id=journal_doc.staff_id,
            user_id=journal_doc.user_id,
            content="please refer to receipt_text field",
            journal_text=journal_doc.journal_text,
            receipt_text=journal_doc.receipt_text,
        )
