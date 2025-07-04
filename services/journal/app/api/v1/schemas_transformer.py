# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.api.common.schemas import BaseJournalSchema
from app.api.common.schemas_transformer import SchemasTransformer
from app.api.v1.schemas import TranResponse
from app.models.documents.jornal_document import JournalDocument


class SchemasTransformerV1(SchemasTransformer):
    def __init__(self):
        super().__init__()

    def transform_journal_response(self, journal_doc: JournalDocument) -> BaseJournalSchema:
        return super().transform_journal_response(journal_doc)

    def transform_tran_response(self, tran: BaseTransaction) -> TranResponse:
        return TranResponse(
            tenant_id=tran.tenant_id,
            store_code=tran.store_code,
            terminal_no=tran.terminal_no,
            transaction_no=tran.transaction_no,
        )
