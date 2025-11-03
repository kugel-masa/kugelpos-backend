# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.models.documents.base_tranlog import BaseTransaction

from app.api.common.schemas import BaseTranResponse
from app.api.common.schemas_transformer import SchemasTransformer
from app.api.v1.schemas import *
from app.models.documents.sales_report_document import SalesReportDocument
from app.models.documents.category_report_document import CategoryReportDocument
from app.models.documents.item_report_document import ItemReportDocument


class SchemasTransformerV1(SchemasTransformer):
    def __init__(self):
        super().__init__()

    def transform_tran_response(self, tran: BaseTransaction) -> BaseTranResponse:
        return super().transform_tran_response(tran)

    def transform_sales_report_response(self, report_doc: SalesReportDocument) -> SalesReportResponse:
        return super().transform_sales_report_response(report_doc)

    def transform_category_report_response(self, report_doc: CategoryReportDocument) -> CategoryReportResponse:
        return super().transform_category_report_response(report_doc)

    def transform_item_report_response(self, report_doc: ItemReportDocument) -> ItemReportResponse:
        return super().transform_item_report_response(report_doc)
