# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.exceptions import RepositoryException, NotFoundException
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.config.settings import settings


from logging import getLogger

logger = getLogger(__name__)


class PaymentMasterWebRepository:
    """
    Repository class for accessing payment method master data through web API.

    This class provides methods to retrieve payment method information from the master data service
    and caches retrieved payment methods to avoid redundant API calls.
    """

    def __init__(
        self,
        tenant_id: str,
        terminal_info: TerminalInfoDocument,
        payment_master_documents: list[PaymentMasterDocument] = None,
    ):
        """
        Initialize the repository with tenant and terminal information.

        Args:
            tenant_id: The tenant identifier
            terminal_info: Terminal information document
            payment_master_documents: Optional list of pre-loaded payment documents for caching
        """
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info
        self.payment_master_documents = payment_master_documents
        self.base_url = settings.BASE_URL_MASTER_DATA

    def set_payment_master_documents(self, payment_master_documents: list):
        """
        Set the cached payment master documents.

        Args:
            payment_master_documents: List of payment master documents to cache
        """
        self.payment_master_documents = payment_master_documents

    # get payment
    async def get_payment_by_code_async(self, payment_code: str) -> PaymentMasterDocument:
        """
        Get a payment method by its code from cache or from the web API.

        First checks if the payment method exists in the cache, and if not, fetches it from the API.

        Args:
            payment_code: The code of the payment method to retrieve

        Returns:
            PaymentMasterDocument: The requested payment method

        Raises:
            NotFoundException: If the payment method could not be found
            RepositoryException: If there's an error communicating with the API
        """
        if self.payment_master_documents is None:
            self.payment_master_documents = []

        # first check payment_code exist in the list of payment_master_documents
        payment = next(
            (payment for payment in self.payment_master_documents if payment.payment_code == payment_code), None
        )
        if payment is not None:
            logger.info(
                f"paymentMasterRepository.get_payment_by_code: payment_code->{payment_code} in the list of payment_master_documents"
            )
            return payment

        async with get_service_client("master-data") as client:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {"terminal_id": self.terminal_info.terminal_id}
            endpoint = f"/tenants/{self.tenant_id}/payments/{payment_code}"

            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    message = f"payment not found for id {payment_code}: {e.status_code}"
                    raise NotFoundException(message, payment_code, logger)
                else:
                    message = f"Request error for id {payment_code}: {e}"
                    raise RepositoryException(message, logger)

            logger.debug(f"response: {response_data}")
            return PaymentMasterDocument(**response_data.get("data"))
