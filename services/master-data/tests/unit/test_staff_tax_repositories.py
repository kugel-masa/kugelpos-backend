"""Unit tests split out from master-data test_repositories.py.

Same imports / parent-class mocking pattern as the original.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CategoryMasterRepository
# ---------------------------------------------------------------------------




class TestStaffMasterRepository:
    """Tests for StaffMasterRepository filter construction and shard key."""

    def _make_repo(self):
        from app.models.repositories.staff_master_repository import StaffMasterRepository

        mock_db = MagicMock()
        repo = StaffMasterRepository(mock_db, "T001")
        return repo

    # -- create_staff_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_staff_sets_tenant_and_shard_key(self):
        from app.models.documents.staff_master_document import StaffMasterDocument

        repo = self._make_repo()
        doc = StaffMasterDocument(id="ST01", staff_name="Alice")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_staff_async(doc)
            assert result.tenant_id == "T001"
            assert result.shard_key == "T001"

    @pytest.mark.asyncio
    async def test_create_staff_raises_on_failure(self):
        from app.models.documents.staff_master_document import StaffMasterDocument

        repo = self._make_repo()
        doc = StaffMasterDocument(id="ST01")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create staf"):
                await repo.create_staff_async(doc)

    # -- get_staff_by_id_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_get_staff_by_id_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_staff_by_id_async("ST01")
            expected = {"tenant_id": "T001", "id": "ST01"}
            mock_get.assert_awaited_once_with(expected)

    # -- get_staff_by_filter_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_get_staff_by_filter_adds_tenant(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_staff_by_filter_async({"staff_name": "Alice"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["staff_name"] == "Alice"

    # -- update_staff_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_staff_filter_and_success(self):
        from app.models.documents.staff_master_document import StaffMasterDocument

        repo = self._make_repo()
        updated_doc = StaffMasterDocument(tenant_id="T001", id="ST01")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            result = await repo.update_staff_async("ST01", {"staff_name": "Bob"})
            expected_filter = {"tenant_id": "T001", "id": "ST01"}
            mock_upd.assert_awaited_once_with(expected_filter, {"staff_name": "Bob"})
            assert result == updated_doc

    @pytest.mark.asyncio
    async def test_update_staff_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update staff"):
                await repo.update_staff_async("ST01", {"staff_name": "x"})

    # -- replace_staff_async -------------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_staff_success(self):
        from app.models.documents.staff_master_document import StaffMasterDocument

        repo = self._make_repo()
        new_doc = StaffMasterDocument(tenant_id="T001", id="ST01")
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_rep:
            result = await repo.replace_staff_async("ST01", new_doc)
            expected_filter = {"tenant_id": "T001", "id": "ST01"}
            mock_rep.assert_awaited_once_with(expected_filter, new_doc)
            assert result is new_doc

    @pytest.mark.asyncio
    async def test_replace_staff_raises_on_failure(self):
        from app.models.documents.staff_master_document import StaffMasterDocument

        repo = self._make_repo()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to replace staff"):
                await repo.replace_staff_async("ST01", StaffMasterDocument())

    # -- delete_staff_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_staff_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_staff_async("ST01")
            expected = {"tenant_id": "T001", "id": "ST01"}
            mock_del.assert_awaited_once_with(expected)

    # -- get_staff_count_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_get_staff_count(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=3)
        repo.dbcollection = mock_collection

        count = await repo.get_staff_count_async()
        assert count == 3
        call_filter = mock_collection.count_documents.call_args[0][0]
        assert call_filter == {"tenant_id": "T001"}

    @pytest.mark.asyncio
    async def test_get_staff_count_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            async def side_effect():
                repo.dbcollection = mock_collection

            mock_init.side_effect = side_effect
            count = await repo.get_staff_count_async()
            mock_init.assert_awaited_once()
            assert count == 0


# ---------------------------------------------------------------------------
# TaxMasterRepository
# ---------------------------------------------------------------------------




class TestTaxMasterRepository:
    """Tests for TaxMasterRepository settings-based loading and caching."""

    def _make_repo(self, tax_docs=None):
        from app.models.repositories.tax_master_repository import TaxMasterRepository
        from app.models.documents.terminal_info_document import TerminalInfoDocument

        mock_db = MagicMock()
        terminal_info = TerminalInfoDocument(tenant_id="T001", store_code="S01", terminal_no=1)
        repo = TaxMasterRepository(mock_db, terminal_info, tax_master_documents=tax_docs)
        return repo

    # -- load_all_taxes ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_load_all_taxes_from_settings(self):
        repo = self._make_repo()
        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [
                {"tax_code": "TAX01", "tax_rate": 0.1, "description": "10%"},
            ]
            mock_settings.DB_COLLECTION_NAME_TAX_MASTER = "tax_master"
            result = await repo.load_all_taxes()
            assert len(result) == 1
            assert result[0].tax_code == "TAX01"

    @pytest.mark.asyncio
    async def test_load_all_taxes_none_settings(self):
        repo = self._make_repo()
        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = None
            mock_settings.DB_COLLECTION_NAME_TAX_MASTER = "tax_master"
            result = await repo.load_all_taxes()
            assert result == []

    @pytest.mark.asyncio
    async def test_load_all_taxes_clears_existing(self):
        """When tax_master_documents is not None, it should be cleared first."""
        from app.models.documents.tax_master_document import TaxMasterDocument

        existing = [TaxMasterDocument(tax_code="OLD")]
        repo = self._make_repo(tax_docs=existing)
        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [{"tax_code": "NEW", "tax_rate": 0.08}]
            mock_settings.DB_COLLECTION_NAME_TAX_MASTER = "tax_master"
            result = await repo.load_all_taxes()
            assert len(result) == 1
            assert result[0].tax_code == "NEW"

    # -- get_tax_by_code -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_tax_by_code_found(self):
        from app.models.documents.tax_master_document import TaxMasterDocument

        docs = [TaxMasterDocument(tax_code="TAX01", tax_rate=0.1)]
        repo = self._make_repo(tax_docs=docs)

        result = await repo.get_tax_by_code("TAX01")
        assert result.tax_code == "TAX01"

    @pytest.mark.asyncio
    async def test_get_tax_by_code_not_found_raises(self):
        from kugel_common.exceptions import NotFoundException
        from app.models.documents.tax_master_document import TaxMasterDocument

        docs = [TaxMasterDocument(tax_code="TAX01")]
        repo = self._make_repo(tax_docs=docs)

        with pytest.raises(NotFoundException):
            await repo.get_tax_by_code("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_tax_by_code_loads_if_none(self):
        """If tax_master_documents is None, load_all_taxes is called first."""
        repo = self._make_repo(tax_docs=None)
        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [{"tax_code": "TAX01", "tax_rate": 0.1}]
            mock_settings.DB_COLLECTION_NAME_TAX_MASTER = "tax_master"
            result = await repo.get_tax_by_code("TAX01")
            assert result.tax_code == "TAX01"

    # -- set_tax_master_documents --------------------------------------------

    def test_set_tax_master_documents(self):
        from app.models.documents.tax_master_document import TaxMasterDocument

        repo = self._make_repo()
        docs = [TaxMasterDocument(tax_code="X")]
        repo.set_tax_master_documents(docs)
        assert repo.tax_master_documents is docs


# ---------------------------------------------------------------------------
# ItemBookMasterRepository
# ---------------------------------------------------------------------------


