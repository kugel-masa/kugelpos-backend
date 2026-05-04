# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
import pytest
from unittest.mock import AsyncMock

from kugel_common.exceptions import DocumentNotFoundException

from app.services.tax_master_service import TaxMasterService
from app.models.documents.tax_master_document import TaxMasterDocument



# ---------------------------------------------------------------------------
# TaxMasterService
# ---------------------------------------------------------------------------

class TestTaxMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return TaxMasterService(tax_master_repo=repo)

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, repo):
        doc = TaxMasterDocument()
        repo.get_tax_by_code.return_value = doc

        result = await service.get_tax_by_code_async("TAX-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_code_not_found_raises(self, service, repo):
        repo.get_tax_by_code.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_tax_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_all_taxes(self, service, repo):
        repo.load_all_taxes.return_value = []
        await service.get_all_taxes_async()
        repo.load_all_taxes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_taxes_paginated(self, service, repo):
        """Returns (paginated_list, total_count) tuple."""
        taxes = [TaxMasterDocument(), TaxMasterDocument(), TaxMasterDocument()]
        repo.load_all_taxes.return_value = taxes

        result, total = await service.get_all_taxes_paginated_async(limit=2, page=1, sort=[])
        assert total == 3
        assert len(result) == 2


# ---------------------------------------------------------------------------
# SettingsMasterService
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# TaxMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestTaxMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return TaxMasterService(tax_master_repo=repo)

    @pytest.mark.asyncio
    async def test_get_all_taxes_paginated_with_reverse_sort(self, service, repo):
        """Lines 82-84: sort with direction=-1 (reverse)."""
        tax1 = TaxMasterDocument()
        tax1.tax_code = "A"
        tax2 = TaxMasterDocument()
        tax2.tax_code = "B"
        tax3 = TaxMasterDocument()
        tax3.tax_code = "C"
        repo.load_all_taxes.return_value = [tax1, tax2, tax3]

        result, total = await service.get_all_taxes_paginated_async(
            limit=10, page=1, sort=[("tax_code", -1)]
        )

        assert total == 3
        # Should be sorted in reverse order by tax_code
        assert result[0].tax_code == "C"
        assert result[1].tax_code == "B"
        assert result[2].tax_code == "A"

    @pytest.mark.asyncio
    async def test_get_all_taxes_paginated_ascending_sort(self, service, repo):
        """Sort with direction=1 (ascending)."""
        tax1 = TaxMasterDocument()
        tax1.tax_code = "C"
        tax2 = TaxMasterDocument()
        tax2.tax_code = "A"
        repo.load_all_taxes.return_value = [tax1, tax2]

        result, total = await service.get_all_taxes_paginated_async(
            limit=10, page=1, sort=[("tax_code", 1)]
        )

        assert total == 2
        assert result[0].tax_code == "A"
        assert result[1].tax_code == "C"


# ---------------------------------------------------------------------------
# SettingsMasterService - additional coverage
# ---------------------------------------------------------------------------
