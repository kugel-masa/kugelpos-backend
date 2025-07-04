# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import LoadDataNoExistException, NotFoundException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.tax_master_document import TaxMasterDocument
from app.config.settings import settings

logger = getLogger(__name__)


class TaxMasterRepository(AbstractRepository[TaxMasterDocument]):
    """
    Repository class for accessing tax configuration data.

    This class provides methods to load tax configurations from settings
    and retrieve specific tax information by tax code.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        terminal_info: TerminalInfoDocument,
        tax_master_documents: list[TaxMasterDocument] = None,
    ):
        """
        Initialize the repository with database connection and terminal information.

        Args:
            db: Database connection object
            terminal_info: Terminal information (not used in this class but required for future use)
            tax_master_documents: Optional list of pre-loaded tax documents for caching
        """
        super().__init__(settings.DB_COLLECTION_NAME_TAX_MASTER, TaxMasterDocument, db)
        self.terminal_info = terminal_info
        self.tax_master_documents = tax_master_documents

    def set_tax_master_documents(self, tax_master_documents: list[TaxMasterDocument]):
        """
        Set the cached tax master documents.

        Args:
            tax_master_documents: List of tax master documents to cache
        """
        self.tax_master_documents = tax_master_documents

    async def load_all_taxes(self) -> list[TaxMasterDocument]:
        """
        Load all tax configurations from application settings.

        Clears any existing cached tax documents and loads fresh data from settings.

        Returns:
            list[TaxMasterDocument]: A list of all tax configurations
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
        Get a tax configuration by its code from the cache.

        Args:
            tax_code: The code of the tax configuration to retrieve

        Returns:
            TaxMasterDocument: The requested tax configuration

        Raises:
            NotFoundException: If the tax code is not found in the cache
            LoadDataNoExistException: If taxes have not been loaded yet
        """
        if self.tax_master_documents is not None:
            for tax in self.tax_master_documents:
                if tax.tax_code == tax_code:
                    return tax
            # return default tax if not found
            message = f"TaxMasterRepository.get_tax_by_code: tax_code->{tax_code} not found in the list of tax_master_documents"
            raise NotFoundException(message, tax_code, logger)
        else:
            message = "you must load taxes before calling get_tax_by_code"
            raise LoadDataNoExistException(message, "tax_master_documents", logger)

    def __get_shard_key(self, tax: TaxMasterDocument) -> str:
        """
        Generate a shard key for the tax document.

        Args:
            tax: Tax master document

        Returns:
            str: The shard key (currently not needed for this repository)
        """
        return "no_need"
