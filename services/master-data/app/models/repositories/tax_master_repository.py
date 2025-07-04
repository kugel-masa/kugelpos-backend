# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.exceptions import RepositoryException, NotFoundException

from app.config.settings import settings
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.tax_master_document import TaxMasterDocument
from app.models.documents.terminal_info_document import TerminalInfoDocument

logger = getLogger(__name__)


class TaxMasterRepository(AbstractRepository[TaxMasterDocument]):
    """
    Repository for managing tax master data in the database.

    This class provides specific implementation for tax data operations,
    extending the generic functionality provided by AbstractRepository.
    Unlike other repositories, tax data is typically loaded from application
    settings rather than stored directly in MongoDB, as tax rates are often
    configured at the system level.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        terminal_info: TerminalInfoDocument,
        tax_master_documents: list[TaxMasterDocument] = None,
    ):
        """
        Initialize a new TaxMasterRepository instance.

        Args:
            db: MongoDB database instance
            terminal_info: Terminal information document (preserved for future use)
            tax_master_documents: Optional list of tax documents for caching
        """
        super().__init__(settings.DB_COLLECTION_NAME_TAX_MASTER, TaxMasterDocument, db)
        self.terminal_info = terminal_info
        self.tax_master_documents = tax_master_documents

    def set_tax_master_documents(self, tax_master_documents: list[TaxMasterDocument]):
        """
        Set the cached tax master documents list.

        This method allows updating the cached tax documents for faster lookups.

        Args:
            tax_master_documents: List of tax documents to cache
        """
        self.tax_master_documents = tax_master_documents

    async def load_all_taxes(self) -> list[TaxMasterDocument]:
        """
        Load all tax definitions from application settings.

        This method differs from other repositories as it loads data from
        configuration settings rather than the database. Tax rates are often
        configured at the system level rather than stored in the database.

        Returns:
            List of tax documents loaded from settings

        Raises:
            RepositoryException: If there is an error during loading
        """
        if self.tax_master_documents is None:
            self.tax_master_documents = []
        else:
            self.tax_master_documents.clear()

        all_tax = settings.TAX_MASTER
        if all_tax is not None:
            logger.debug(f"TaxMasterRepository.load_all_taxes: all_tax->{all_tax}")
            [self.tax_master_documents.append(TaxMasterDocument(**tax)) for tax in all_tax]
        return self.tax_master_documents

    async def get_tax_by_code(self, tax_code: str) -> TaxMasterDocument:
        """
        Retrieve a specific tax definition by its code.

        If the tax documents are not already loaded, this method will
        load them first from application settings.

        Args:
            tax_code: Unique identifier for the tax

        Returns:
            The matching tax document

        Raises:
            NotFoundException: If no tax with the specified code is found
            RepositoryException: If there is an error during retrieval
        """
        if self.tax_master_documents is None:
            await self.load_all_taxes()

        for tax in self.tax_master_documents:
            if tax.tax_code == tax_code:
                return tax

        message = (
            f"TaxMasterRepository.get_tax_by_code: tax_code->{tax_code} not found in the list of tax_master_documents"
        )
        raise NotFoundException(message, tax_code, logger)

    def __get_shard_key(self, tax: TaxMasterDocument) -> str:
        """
        Generate a shard key for the tax document.

        This method is implemented to satisfy the abstract base class requirement,
        but since tax data is not typically sharded, it returns a fixed value.

        Args:
            tax: Tax document for which to generate a shard key

        Returns:
            A fixed string indicating that sharding is not needed for tax documents
        """
        return "no_need"
