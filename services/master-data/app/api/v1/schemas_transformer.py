# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from app.models.documents.staff_master_document import StaffMasterDocument
from app.api.common.schemas import BasePaymentResponse, BaseStaffResponse
from app.api.common.schemas_transformer import SchemasTransformer
from app.models.documents.payment_master_document import PaymentMasterDocument

logger = getLogger(__name__)


class SchemasTransformerV1(SchemasTransformer):
    def __init__(self):
        super().__init__()

    def transform_staff(self, staff_doc: StaffMasterDocument) -> BaseStaffResponse:
        logger.debug(f"Transforming staff document: {staff_doc}")
        try:
            return super().transform_staff(staff_doc)
        except Exception as e:
            logger.error(f"Error transforming staff document: {e}")
            raise e

    def transform_payment(self, payment_doc: PaymentMasterDocument) -> BasePaymentResponse:
        logger.debug(f"Transforming payment document: {payment_doc}")
        try:
            return super().transform_payment(payment_doc)
        except Exception as e:
            logger.error(f"Error transforming payment document: {e}")
            raise e
