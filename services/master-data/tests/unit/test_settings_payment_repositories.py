"""Unit tests split out from master-data test_repositories.py.

Same imports / parent-class mocking pattern as the original.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CategoryMasterRepository
# ---------------------------------------------------------------------------




class TestSettingsMasterRepository:
    """Tests for settings filter construction and shard key."""

    def _make_repo(self):
        from app.models.repositories.settings_master_repository import SettingsMasterRepository

        mock_db = MagicMock()
        repo = SettingsMasterRepository(mock_db, "T001")
        return repo

    # -- create_settings_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_settings_sets_tenant_and_shard_key(self):
        from app.models.documents.settings_master_document import SettingsMasterDocument

        repo = self._make_repo()
        doc = SettingsMasterDocument(name="tax_rounding", default_value="round_down")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_settings_async(doc)
            assert result.tenant_id == "T001"
            assert result.shard_key == "T001"

    @pytest.mark.asyncio
    async def test_create_settings_raises_on_failure(self):
        from app.models.documents.settings_master_document import SettingsMasterDocument

        repo = self._make_repo()
        doc = SettingsMasterDocument(name="x")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create settings"):
                await repo.create_settings_async(doc)

    # -- get_settings_all_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_get_settings_all_filter(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_settings_all_async(limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg == {"tenant_id": "T001"}

    # -- get_settings_by_name_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_get_settings_by_name_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_settings_by_name_async("tax_rounding")
            expected = {"tenant_id": "T001", "name": "tax_rounding"}
            mock_get.assert_awaited_once_with(expected)

    # -- update_settings_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_settings_filter(self):
        from app.models.documents.settings_master_document import SettingsMasterDocument

        repo = self._make_repo()
        updated_doc = SettingsMasterDocument(tenant_id="T001", name="tax_rounding")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            await repo.update_settings_async("tax_rounding", {"default_value": "round_up"})
            expected_filter = {"tenant_id": "T001", "name": "tax_rounding"}
            mock_upd.assert_awaited_once_with(expected_filter, {"default_value": "round_up"})

    @pytest.mark.asyncio
    async def test_update_settings_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update settings"):
                await repo.update_settings_async("tax_rounding", {"default_value": "x"})

    # -- delete_settings_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_settings_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_settings_async("tax_rounding")
            expected = {"tenant_id": "T001", "name": "tax_rounding"}
            mock_del.assert_awaited_once_with(expected)

    # -- get_settings_count_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_get_settings_count(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=7)
        repo.dbcollection = mock_collection

        count = await repo.get_settings_count_async()
        assert count == 7
        call_filter = mock_collection.count_documents.call_args[0][0]
        assert call_filter == {"tenant_id": "T001"}

    @pytest.mark.asyncio
    async def test_get_settings_count_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            async def side_effect():
                repo.dbcollection = mock_collection

            mock_init.side_effect = side_effect
            count = await repo.get_settings_count_async()
            mock_init.assert_awaited_once()
            assert count == 0


# ---------------------------------------------------------------------------
# PaymentMasterRepository
# ---------------------------------------------------------------------------




class TestPaymentMasterRepository:
    """Tests for PaymentMasterRepository filter construction and shard key."""

    def _make_repo(self):
        from app.models.repositories.payment_master_repository import PaymentMasterRepository

        mock_db = MagicMock()
        repo = PaymentMasterRepository(mock_db, "T001")
        return repo

    # -- create_payment_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_payment_sets_tenant_and_shard_key(self):
        from app.models.documents.payment_master_document import PaymentMasterDocument

        repo = self._make_repo()
        doc = PaymentMasterDocument(payment_code="PAY01", description="Cash")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_payment_async(doc)
            assert result.tenant_id == "T001"
            assert result.shard_key == "T001"

    @pytest.mark.asyncio
    async def test_create_payment_raises_on_failure(self):
        from app.models.documents.payment_master_document import PaymentMasterDocument

        repo = self._make_repo()
        doc = PaymentMasterDocument(payment_code="PAY01")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create payment"):
                await repo.create_payment_async(doc)

    # -- get_payment_by_code -------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_payment_by_code_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_payment_by_code("PAY01")
            expected = {"tenant_id": "T001", "payment_code": "PAY01"}
            mock_get.assert_awaited_once_with(expected)

    # -- get_payment_by_filter_async -----------------------------------------

    @pytest.mark.asyncio
    async def test_get_payment_by_filter_adds_tenant(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_payment_by_filter_async({"description": "Cash"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["description"] == "Cash"

    # -- update_payment_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_payment_filter_and_success(self):
        from app.models.documents.payment_master_document import PaymentMasterDocument

        repo = self._make_repo()
        updated_doc = PaymentMasterDocument(tenant_id="T001", payment_code="PAY01")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            result = await repo.update_payment_async("PAY01", {"description": "Updated"})
            expected_filter = {"tenant_id": "T001", "payment_code": "PAY01"}
            mock_upd.assert_awaited_once_with(expected_filter, {"description": "Updated"})
            assert result == updated_doc

    @pytest.mark.asyncio
    async def test_update_payment_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update payment"):
                await repo.update_payment_async("PAY01", {"description": "x"})

    # -- replace_payment_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_payment_success(self):
        from app.models.documents.payment_master_document import PaymentMasterDocument

        repo = self._make_repo()
        new_doc = PaymentMasterDocument(tenant_id="T001", payment_code="PAY01")
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_rep:
            result = await repo.replace_payment_async("PAY01", new_doc)
            expected_filter = {"tenant_id": "T001", "payment_code": "PAY01"}
            mock_rep.assert_awaited_once_with(expected_filter, new_doc)
            assert result is new_doc

    @pytest.mark.asyncio
    async def test_replace_payment_raises_on_failure(self):
        from app.models.documents.payment_master_document import PaymentMasterDocument

        repo = self._make_repo()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to replace payment"):
                await repo.replace_payment_async("PAY01", PaymentMasterDocument())

    # -- delete_payment_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_payment_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_payment_async("PAY01")
            expected = {"tenant_id": "T001", "payment_code": "PAY01"}
            mock_del.assert_awaited_once_with(expected)

    # -- get_payment_count_by_filter_async -----------------------------------

    @pytest.mark.asyncio
    async def test_get_payment_count_by_filter(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=5)
        repo.dbcollection = mock_collection

        count = await repo.get_payment_count_by_filter_async({"description": "Cash"})
        assert count == 5
        call_filter = mock_collection.count_documents.call_args[0][0]
        assert call_filter["tenant_id"] == "T001"

    @pytest.mark.asyncio
    async def test_get_payment_count_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            async def side_effect():
                repo.dbcollection = mock_collection

            mock_init.side_effect = side_effect
            count = await repo.get_payment_count_by_filter_async({})
            mock_init.assert_awaited_once()
            assert count == 0


# ---------------------------------------------------------------------------
# StaffMasterRepository
# ---------------------------------------------------------------------------




class TestPromotionMasterRepository:
    """Tests for complex query construction with $or, $lte, $gte, $size."""

    def _make_repo(self):
        from app.models.repositories.promotion_master_repository import PromotionMasterRepository

        mock_db = MagicMock()
        repo = PromotionMasterRepository(mock_db, "T001")
        return repo

    # -- create_promotion_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_create_promotion_sets_tenant_and_shard_key(self):
        from app.models.documents.promotion_master_document import PromotionMasterDocument

        repo = self._make_repo()
        doc = PromotionMasterDocument(
            promotion_code="P01",
            start_datetime=datetime(2025, 1, 1),
            end_datetime=datetime(2025, 12, 31),
        )
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_promotion_async(doc)
            assert result.tenant_id == "T001"
            # promotion uses "-".join for shard key
            assert result.shard_key == "T001"

    @pytest.mark.asyncio
    async def test_create_promotion_raises_on_failure(self):
        from app.models.documents.promotion_master_document import PromotionMasterDocument

        repo = self._make_repo()
        doc = PromotionMasterDocument(
            promotion_code="P01",
            start_datetime=datetime(2025, 1, 1),
            end_datetime=datetime(2025, 12, 31),
        )
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create promotion"):
                await repo.create_promotion_async(doc)

    # -- get_promotion_by_code_async ------------------------------------------

    @pytest.mark.asyncio
    async def test_get_promotion_by_code_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_promotion_by_code_async("P01")
            expected = {"tenant_id": "T001", "promotion_code": "P01", "is_deleted": False}
            mock_get.assert_awaited_once_with(expected)

    # -- get_promotions_by_filter_async ---------------------------------------

    @pytest.mark.asyncio
    async def test_get_promotions_by_filter_adds_tenant_and_is_deleted(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_promotions_by_filter_async({"name": "Sale"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["is_deleted"] is False
            assert filter_arg["name"] == "Sale"

    # -- get_promotions_by_filter_paginated_async -----------------------------

    @pytest.mark.asyncio
    async def test_get_promotions_by_filter_paginated(self):
        repo = self._make_repo()
        mock_result = MagicMock()
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=mock_result
        ) as mock_pag:
            result = await repo.get_promotions_by_filter_paginated_async(
                {"promotion_type": "category_discount"}, limit=5, page=1, sort=[]
            )
            filter_arg = mock_pag.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["is_deleted"] is False
            assert result is mock_result

    # -- get_active_promotions_async ------------------------------------------

    @pytest.mark.asyncio
    async def test_get_active_promotions_query(self):
        repo = self._make_repo()
        now = datetime(2025, 6, 15, 12, 0, 0)
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_list:
            await repo.get_active_promotions_async(current_time=now)
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["is_active"] is True
            assert filter_arg["is_deleted"] is False
            assert filter_arg["start_datetime"] == {"$lte": now}
            assert filter_arg["end_datetime"] == {"$gte": now}

    @pytest.mark.asyncio
    async def test_get_active_promotions_uses_app_time_when_none(self):
        repo = self._make_repo()
        fake_now = datetime(2025, 3, 1, 10, 0, 0)
        with (
            patch("app.models.repositories.promotion_master_repository.get_app_time", return_value=fake_now),
            patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_list,
        ):
            await repo.get_active_promotions_async(current_time=None)
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["start_datetime"] == {"$lte": fake_now}
            assert filter_arg["end_datetime"] == {"$gte": fake_now}

    # -- get_active_promotions_by_category_async ------------------------------

    @pytest.mark.asyncio
    async def test_get_active_promotions_by_category_query(self):
        repo = self._make_repo()
        now = datetime(2025, 6, 15, 12, 0, 0)
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_list:
            await repo.get_active_promotions_by_category_async("CAT01", current_time=now)
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["is_active"] is True
            assert filter_arg["is_deleted"] is False
            assert filter_arg["start_datetime"] == {"$lte": now}
            assert filter_arg["end_datetime"] == {"$gte": now}
            assert filter_arg["promotion_type"] == "category_discount"
            assert filter_arg["detail.target_category_codes"] == "CAT01"

    # -- get_active_promotions_by_store_async ---------------------------------

    @pytest.mark.asyncio
    async def test_get_active_promotions_by_store_query_with_or(self):
        repo = self._make_repo()
        now = datetime(2025, 6, 15, 12, 0, 0)
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_list:
            await repo.get_active_promotions_by_store_async("S01", current_time=now)
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["is_active"] is True
            assert filter_arg["is_deleted"] is False
            assert filter_arg["start_datetime"] == {"$lte": now}
            assert filter_arg["end_datetime"] == {"$gte": now}
            # Verify the $or clause for store matching
            or_clause = filter_arg["$or"]
            assert len(or_clause) == 2
            assert or_clause[0] == {"detail.target_store_codes": {"$size": 0}}
            assert or_clause[1] == {"detail.target_store_codes": "S01"}

    @pytest.mark.asyncio
    async def test_get_active_promotions_by_store_uses_app_time_when_none(self):
        repo = self._make_repo()
        fake_now = datetime(2025, 3, 1)
        with (
            patch("app.models.repositories.promotion_master_repository.get_app_time", return_value=fake_now),
            patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_list,
        ):
            await repo.get_active_promotions_by_store_async("S01", current_time=None)
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["start_datetime"] == {"$lte": fake_now}

    # -- update_promotion_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_update_promotion_filter(self):
        from app.models.documents.promotion_master_document import PromotionMasterDocument

        repo = self._make_repo()
        updated_doc = PromotionMasterDocument(
            tenant_id="T001",
            promotion_code="P01",
            start_datetime=datetime(2025, 1, 1),
            end_datetime=datetime(2025, 12, 31),
        )
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            await repo.update_promotion_async("P01", {"name": "New Sale"})
            expected_filter = {"tenant_id": "T001", "promotion_code": "P01", "is_deleted": False}
            mock_upd.assert_awaited_once_with(expected_filter, {"name": "New Sale"})

    @pytest.mark.asyncio
    async def test_update_promotion_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update promotion"):
                await repo.update_promotion_async("P01", {"name": "x"})

    # -- delete_promotion_async (soft delete) ---------------------------------

    @pytest.mark.asyncio
    async def test_delete_promotion_soft_delete(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd:
            result = await repo.delete_promotion_async("P01")
            assert result is True
            filter_arg = mock_upd.call_args[0][0]
            update_arg = mock_upd.call_args[0][1]
            assert filter_arg == {"tenant_id": "T001", "promotion_code": "P01", "is_deleted": False}
            assert update_arg["is_deleted"] is True
            assert "updated_at" in update_arg


# ---------------------------------------------------------------------------
# ItemStoreMasterRepository
# ---------------------------------------------------------------------------


