# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Any

from kugel_common.exceptions import DocumentNotFoundException
from app.models.documents.tax_master_document import TaxMasterDocument
from app.models.repositories.tax_master_repository import TaxMasterRepository

logger = getLogger(__name__)


class TaxMasterService:
    """
    Service class for managing tax master data operations.

    This service provides business logic for retrieving tax information
    from the master data database. Tax records define different tax rates
    and configurations used for sales calculations.
    """

    def __init__(self, tax_master_repo: TaxMasterRepository):
        """
        Initialize the TaxMasterService with a repository.

        Args:
            tax_master_repo: Repository for tax master data operations
        """
        self.tax_master_repo = tax_master_repo

    async def get_tax_by_code_async(self, tax_code: str) -> TaxMasterDocument:
        """
        Retrieve a tax record by its unique code.

        Args:
            tax_code: Unique identifier for the tax record

        Returns:
            TaxMasterDocument with the specified code

        Raises:
            DocumentNotFoundException: If no tax record with the given code exists
        """
        logger.debug(f"get_tax_by_code_async: tax_code->{tax_code}")
        tax_doc = await self.tax_master_repo.get_tax_by_code(tax_code)
        if tax_doc is None:
            message = f"tax with code {tax_code} not found"
            raise DocumentNotFoundException(message, logger)
        return tax_doc

    async def get_all_taxes_async(self) -> list[TaxMasterDocument]:
        """
        Retrieve all tax records in the database.

        Returns:
            List of all TaxMasterDocument objects
        """
        logger.debug("get_all_taxes_async")
        return await self.tax_master_repo.load_all_taxes()

    async def get_all_taxes_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[TaxMasterDocument], int]:
        """
        Retrieve all tax records with pagination metadata.

        Since tax data is loaded from settings, this method simulates pagination
        on the complete dataset.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of TaxMasterDocument objects for the page, total count)
        """
        logger.debug(f"get_all_taxes_paginated_async: limit={limit}, page={page}, sort={sort}")
        all_taxes = await self.tax_master_repo.load_all_taxes()

        # Apply sorting if specified
        if sort:
            for field, direction in reversed(sort):
                reverse = direction == -1
                all_taxes.sort(key=lambda x: getattr(x, field, ""), reverse=reverse)

        # Calculate pagination
        total_count = len(all_taxes)
        start_index = (page - 1) * limit if page > 0 else 0
        end_index = start_index + limit
        paginated_taxes = all_taxes[start_index:end_index]

        return paginated_taxes, total_count
