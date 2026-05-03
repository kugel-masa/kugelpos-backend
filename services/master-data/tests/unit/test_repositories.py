"""
Unit tests for the repository layer of the master-data service.

Tests focus on filter construction, shard key generation, caching logic,
complex query operators, and error handling by mocking AbstractRepository
parent class methods.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CategoryMasterRepository
# ---------------------------------------------------------------------------


class TestCategoryMasterRepository:
    """Tests for CategoryMasterRepository filter construction and shard key."""

    def _make_repo(self):
        from app.models.repositories.category_master_repository import CategoryMasterRepository

        mock_db = MagicMock()
        repo = CategoryMasterRepository(mock_db, "T001")
        return repo

    # -- create_category_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_category_sets_tenant_and_shard_key(self):
        from app.models.documents.category_master_document import CategoryMasterDocument

        repo = self._make_repo()
        doc = CategoryMasterDocument(category_code="C01", description="Cat 1")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            result = await repo.create_category_async(doc)
            assert result.tenant_id == "T001"
            assert result.shard_key == "T001"
            mock_create.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_create_category_raises_on_failure(self):
        from app.models.documents.category_master_document import CategoryMasterDocument

        repo = self._make_repo()
        doc = CategoryMasterDocument(category_code="C01")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create category"):
                await repo.create_category_async(doc)

    # -- get_category_by_code_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_get_category_by_code_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_category_by_code_async("C01")
            expected_filter = {"tenant_id": "T001", "category_code": "C01"}
            mock_get.assert_awaited_once_with(expected_filter)

    # -- get_category_by_filter_async -----------------------------------------

    @pytest.mark.asyncio
    async def test_get_category_by_filter_adds_tenant(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_category_by_filter_async({"category_code": "C01"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["category_code"] == "C01"

    # -- get_category_by_filter_paginated_async --------------------------------

    @pytest.mark.asyncio
    async def test_get_category_by_filter_paginated_adds_tenant(self):
        repo = self._make_repo()
        mock_result = MagicMock()
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=mock_result
        ) as mock_pag:
            result = await repo.get_category_by_filter_paginated_async(
                {"description": "test"}, limit=5, page=2, sort=[("created_at", -1)]
            )
            filter_arg = mock_pag.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["description"] == "test"
            assert result is mock_result

    # -- update_category_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_category_filter_and_success(self):
        from app.models.documents.category_master_document import CategoryMasterDocument

        repo = self._make_repo()
        updated_doc = CategoryMasterDocument(tenant_id="T001", category_code="C01", description="Updated")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            result = await repo.update_category_async("C01", {"description": "Updated"})
            expected_filter = {"tenant_id": "T001", "category_code": "C01"}
            mock_update.assert_awaited_once_with(expected_filter, {"description": "Updated"})
            assert result.description == "Updated"

    @pytest.mark.asyncio
    async def test_update_category_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update category"):
                await repo.update_category_async("C01", {"description": "x"})

    # -- replace_category_async -----------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_category_filter_and_success(self):
        from app.models.documents.category_master_document import CategoryMasterDocument

        repo = self._make_repo()
        new_doc = CategoryMasterDocument(tenant_id="T001", category_code="C01")
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_rep:
            result = await repo.replace_category_async("C01", new_doc)
            expected_filter = {"tenant_id": "T001", "category_code": "C01"}
            mock_rep.assert_awaited_once_with(expected_filter, new_doc)
            assert result is new_doc

    @pytest.mark.asyncio
    async def test_replace_category_raises_on_failure(self):
        from app.models.documents.category_master_document import CategoryMasterDocument

        repo = self._make_repo()
        new_doc = CategoryMasterDocument()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to replace category"):
                await repo.replace_category_async("C01", new_doc)

    # -- delete_category_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_category_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_category_async("C01")
            expected_filter = {"tenant_id": "T001", "category_code": "C01"}
            mock_del.assert_awaited_once_with(expected_filter)


# ---------------------------------------------------------------------------
# ItemCommonMasterRepository
# ---------------------------------------------------------------------------


class TestItemCommonMasterRepository:
    """Tests for ItemCommonMasterRepository caching, filter, and shard key."""

    def _make_repo(self, cached_docs=None):
        from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository

        mock_db = MagicMock()
        repo = ItemCommonMasterRepository(mock_db, "T001", item_master_documents=cached_docs)
        return repo

    # -- create_item_async ----------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_item_sets_tenant_and_shard_key(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        doc = ItemCommonMasterDocument(item_code="I01", description="Item 1")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_item_async(doc)
            assert result.tenant_id == "T001"
            # shard key uses make_shard_key with [tenant_id]
            assert result.shard_key == "T001"

    @pytest.mark.asyncio
    async def test_create_item_raises_on_failure(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        doc = ItemCommonMasterDocument(item_code="I01")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create item"):
                await repo.create_item_async(doc)

    # -- get_item_by_code_async: no cache -------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_by_code_no_cache(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        expected_doc = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=expected_doc) as mock_get:
            result = await repo.get_item_by_code_async("I01")
            expected_filter = {"tenant_id": "T001", "item_code": "I01", "is_deleted": False}
            mock_get.assert_awaited_once_with(expected_filter)
            assert result is expected_doc

    @pytest.mark.asyncio
    async def test_get_item_by_code_with_logical_deleted(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_item_by_code_async("I01", is_logical_deleted=True)
            expected_filter = {"tenant_id": "T001", "item_code": "I01", "is_deleted": True}
            mock_get.assert_awaited_once_with(expected_filter)

    # -- get_item_by_code_async: cache hit ------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_by_code_cache_hit(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument
        from app.models.documents.abstract_document import AbstractDocument

        cached_item = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        cached_item.cached_on = datetime.now()
        repo = self._make_repo(cached_docs=[cached_item])

        with patch.object(AbstractDocument, "is_expired", return_value=False):
            with patch.object(repo, "get_one_async", new_callable=AsyncMock) as mock_get:
                result = await repo.get_item_by_code_async("I01", use_cache=True)
                # Should return cached item without DB call
                mock_get.assert_not_awaited()
                assert result is cached_item

    # -- get_item_by_code_async: cache expired --------------------------------

    @pytest.mark.asyncio
    async def test_get_item_by_code_cache_expired(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument
        from app.models.documents.abstract_document import AbstractDocument

        cached_item = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        cached_item.cached_on = datetime.now() - timedelta(hours=1)
        repo = self._make_repo(cached_docs=[cached_item])

        fresh_item = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        with patch.object(AbstractDocument, "is_expired", return_value=True):
            with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=fresh_item):
                result = await repo.get_item_by_code_async("I01", use_cache=True)
                # Expired item should be removed, DB should be queried
                assert result is fresh_item
                assert cached_item not in repo.item_master_documents
                assert fresh_item in repo.item_master_documents

    # -- get_item_by_code_async: cache miss, stores result --------------------

    @pytest.mark.asyncio
    async def test_get_item_by_code_cache_miss_stores_result(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo(cached_docs=[])
        db_item = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=db_item):
            result = await repo.get_item_by_code_async("I01", use_cache=True)
            assert result is db_item
            assert db_item in repo.item_master_documents
            assert db_item.cached_on is not None

    # -- get_item_by_code_async: cache miss, not found, does not store --------

    @pytest.mark.asyncio
    async def test_get_item_by_code_cache_miss_not_found(self):
        repo = self._make_repo(cached_docs=[])
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            result = await repo.get_item_by_code_async("I01", use_cache=True)
            assert result is None
            assert len(repo.item_master_documents) == 0

    # -- get_item_by_code_async: None item_master_documents initializes -------

    @pytest.mark.asyncio
    async def test_get_item_by_code_initializes_cache_list(self):
        repo = self._make_repo(cached_docs=None)
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None):
            await repo.get_item_by_code_async("I01")
            assert repo.item_master_documents == []

    # -- set_item_master_documents --------------------------------------------

    def test_set_item_master_documents(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        docs = [ItemCommonMasterDocument(item_code="X")]
        repo.set_item_master_documents(docs)
        assert repo.item_master_documents is docs

    # -- get_item_by_filter_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_by_filter_adds_tenant(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_item_by_filter_async({"item_code": "I01"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["item_code"] == "I01"

    # -- update_item_async ----------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_item_filter(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        updated_doc = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            await repo.update_item_async("I01", {"unit_price": 100.0})
            expected_filter = {"tenant_id": "T001", "item_code": "I01"}
            mock_upd.assert_awaited_once_with(expected_filter, {"unit_price": 100.0})

    @pytest.mark.asyncio
    async def test_update_item_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update item"):
                await repo.update_item_async("I01", {"unit_price": 100.0})

    # -- replace_item_async ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_item_filter(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        new_doc = ItemCommonMasterDocument(tenant_id="T001", item_code="I01")
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_rep:
            result = await repo.replace_item_async("I01", new_doc)
            expected_filter = {"tenant_id": "T001", "item_code": "I01"}
            mock_rep.assert_awaited_once_with(expected_filter, new_doc)
            assert result is new_doc

    @pytest.mark.asyncio
    async def test_replace_item_raises_on_failure(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to replace item"):
                await repo.replace_item_async("I01", ItemCommonMasterDocument())

    # -- delete_item_async: physical ------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_item_physical(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_item_async("I01", is_logical=False)
            expected_filter = {"tenant_id": "T001", "item_code": "I01"}
            mock_del.assert_awaited_once_with(expected_filter)

    # -- delete_item_async: logical -------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_item_logical(self):
        from app.models.documents.item_common_master_document import ItemCommonMasterDocument

        repo = self._make_repo()
        deleted_doc = ItemCommonMasterDocument(tenant_id="T001", item_code="I01", is_deleted=True)
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=deleted_doc),
        ):
            result = await repo.delete_item_async("I01", is_logical=True)
            expected_filter = {"tenant_id": "T001", "item_code": "I01"}
            mock_upd.assert_awaited_once_with(expected_filter, {"is_deleted": True})
            assert result.is_deleted is True

    @pytest.mark.asyncio
    async def test_delete_item_logical_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to logically delete item"):
                await repo.delete_item_async("I01", is_logical=True)

    # -- get_item_count_by_filter_async ---------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_count_by_filter(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=5)
        repo.dbcollection = mock_collection

        count = await repo.get_item_count_by_filter_async({"category_code": "C01"})
        assert count == 5
        call_filter = mock_collection.count_documents.call_args[0][0]
        assert call_filter["tenant_id"] == "T001"
        assert call_filter["category_code"] == "C01"

    @pytest.mark.asyncio
    async def test_get_item_count_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            # After initialize, set the collection
            async def side_effect():
                repo.dbcollection = mock_collection

            mock_init.side_effect = side_effect
            count = await repo.get_item_count_by_filter_async({})
            mock_init.assert_awaited_once()
            assert count == 0


# ---------------------------------------------------------------------------
# PromotionMasterRepository
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


class TestItemStoreMasterRepository:
    """Tests for composite shard key and store-scoped filter construction."""

    def _make_repo(self):
        from app.models.repositories.item_store_master_repository import ItemStoreMasterRepository

        mock_db = MagicMock()
        repo = ItemStoreMasterRepository(mock_db, "T001", "S01")
        return repo

    # -- create_item_store_async ----------------------------------------------

    @pytest.mark.asyncio
    async def test_create_item_store_sets_fields_and_composite_shard_key(self):
        from app.models.documents.item_store_master_document import ItemStoreMasterDocument

        repo = self._make_repo()
        doc = ItemStoreMasterDocument(item_code="I01", store_price=9.99)
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_item_store_async(doc)
            assert result.tenant_id == "T001"
            assert result.store_code == "S01"
            # Composite shard key: tenant_id + store_code joined by "_"
            assert result.shard_key == "T001_S01"

    @pytest.mark.asyncio
    async def test_create_item_store_raises_on_failure(self):
        from app.models.documents.item_store_master_document import ItemStoreMasterDocument

        repo = self._make_repo()
        doc = ItemStoreMasterDocument(item_code="I01")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create item store"):
                await repo.create_item_store_async(doc)

    # -- get_item_store_by_code -----------------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_store_by_code_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_item_store_by_code("I01")
            expected = {"tenant_id": "T001", "store_code": "S01", "item_code": "I01"}
            mock_get.assert_awaited_once_with(expected)

    # -- get_item_store_by_filter_async ---------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_store_by_filter_adds_tenant_and_store(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_item_store_by_filter_async({"item_code": "I01"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["store_code"] == "S01"
            assert filter_arg["item_code"] == "I01"

    # -- update_item_store_async ----------------------------------------------

    @pytest.mark.asyncio
    async def test_update_item_store_filter(self):
        from app.models.documents.item_store_master_document import ItemStoreMasterDocument

        repo = self._make_repo()
        updated_doc = ItemStoreMasterDocument(tenant_id="T001", store_code="S01", item_code="I01")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            await repo.update_item_store_async("I01", {"store_price": 19.99})
            expected_filter = {"tenant_id": "T001", "store_code": "S01", "item_code": "I01"}
            mock_upd.assert_awaited_once_with(expected_filter, {"store_price": 19.99})

    @pytest.mark.asyncio
    async def test_update_item_store_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update item store"):
                await repo.update_item_store_async("I01", {"store_price": 1.0})

    # -- replace_item_store_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_item_store_filter(self):
        from app.models.documents.item_store_master_document import ItemStoreMasterDocument

        repo = self._make_repo()
        new_doc = ItemStoreMasterDocument(tenant_id="T001", store_code="S01", item_code="I01")
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_rep:
            result = await repo.replace_item_store_async("I01", new_doc)
            expected_filter = {"tenant_id": "T001", "store_code": "S01", "item_code": "I01"}
            mock_rep.assert_awaited_once_with(expected_filter, new_doc)
            assert result is new_doc

    @pytest.mark.asyncio
    async def test_replace_item_store_raises_on_failure(self):
        from app.models.documents.item_store_master_document import ItemStoreMasterDocument

        repo = self._make_repo()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to replace item store"):
                await repo.replace_item_store_async("I01", ItemStoreMasterDocument())

    # -- delete_item_store_async ----------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_item_store_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_item_store_async("I01")
            expected_filter = {"tenant_id": "T001", "store_code": "S01", "item_code": "I01"}
            mock_del.assert_awaited_once_with(expected_filter)

    # -- get_item_count_by_filter_async ---------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_count_by_filter_adds_tenant_and_store(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=3)
        repo.dbcollection = mock_collection

        count = await repo.get_item_count_by_filter_async({"item_code": "I01"})
        assert count == 3
        call_filter = mock_collection.count_documents.call_args[0][0]
        assert call_filter["tenant_id"] == "T001"
        assert call_filter["store_code"] == "S01"
        assert call_filter["item_code"] == "I01"


# ---------------------------------------------------------------------------
# SettingsMasterRepository
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


class TestItemBookMasterRepository:
    """Tests for ItemBookMasterRepository filter construction and shard key."""

    def _make_repo(self):
        from app.models.repositories.item_book_master_repository import ItemBookMasterRepository

        mock_db = MagicMock()
        repo = ItemBookMasterRepository(mock_db, "T001")
        return repo

    # -- create_item_book_async ----------------------------------------------

    @pytest.mark.asyncio
    async def test_create_item_book_sets_tenant_and_shard_key(self):
        from app.models.documents.item_book_master_document import ItemBookMasterDocument

        repo = self._make_repo()
        doc = ItemBookMasterDocument(item_book_id="BK-001", title="Book 1")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_item_book_async(doc)
            assert result.tenant_id == "T001"
            assert result.shard_key == "T001"

    @pytest.mark.asyncio
    async def test_create_item_book_raises_on_failure(self):
        from app.models.documents.item_book_master_document import ItemBookMasterDocument

        repo = self._make_repo()
        doc = ItemBookMasterDocument(item_book_id="BK-001")
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to create item book"):
                await repo.create_item_book_async(doc)

    # -- get_item_book_async -------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_book_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get:
            await repo.get_item_book_async("BK-001")
            expected = {"tenant_id": "T001", "item_book_id": "BK-001"}
            mock_get.assert_awaited_once_with(expected)

    # -- get_item_book_by_filter_async ---------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_book_by_filter_adds_tenant(self):
        repo = self._make_repo()
        with patch.object(
            repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            await repo.get_item_book_by_filter_async({"title": "Test"}, limit=10, page=1, sort=[])
            filter_arg = mock_list.call_args[0][0]
            assert filter_arg["tenant_id"] == "T001"
            assert filter_arg["title"] == "Test"

    # -- update_item_book_async ----------------------------------------------

    @pytest.mark.asyncio
    async def test_update_item_book_filter_and_success(self):
        from app.models.documents.item_book_master_document import ItemBookMasterDocument

        repo = self._make_repo()
        updated_doc = ItemBookMasterDocument(tenant_id="T001", item_book_id="BK-001")
        with (
            patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_upd,
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=updated_doc),
        ):
            result = await repo.update_item_book_async("BK-001", {"title": "Updated"})
            expected_filter = {"tenant_id": "T001", "item_book_id": "BK-001"}
            mock_upd.assert_awaited_once_with(expected_filter, {"title": "Updated"})
            assert result == updated_doc

    @pytest.mark.asyncio
    async def test_update_item_book_raises_on_failure(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to update item book"):
                await repo.update_item_book_async("BK-001", {"title": "x"})

    # -- replace_item_book_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_replace_item_book_success(self):
        from app.models.documents.item_book_master_document import ItemBookMasterDocument

        repo = self._make_repo()
        new_doc = ItemBookMasterDocument(tenant_id="T001", item_book_id="BK-001")
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_rep:
            result = await repo.replace_item_book_async("BK-001", new_doc)
            expected_filter = {"tenant_id": "T001", "item_book_id": "BK-001"}
            mock_rep.assert_awaited_once_with(expected_filter, new_doc)
            assert result is new_doc

    @pytest.mark.asyncio
    async def test_replace_item_book_raises_on_failure(self):
        from app.models.documents.item_book_master_document import ItemBookMasterDocument

        repo = self._make_repo()
        with patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(Exception, match="Failed to replace item book"):
                await repo.replace_item_book_async("BK-001", ItemBookMasterDocument())

    # -- delete_item_book_async ----------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_item_book_filter(self):
        repo = self._make_repo()
        with patch.object(repo, "delete_async", new_callable=AsyncMock, return_value=True) as mock_del:
            await repo.delete_item_book_async("BK-001")
            expected = {"tenant_id": "T001", "item_book_id": "BK-001"}
            mock_del.assert_awaited_once_with(expected)

    # -- get_item_book_count_by_filter_async ---------------------------------

    @pytest.mark.asyncio
    async def test_get_item_book_count_by_filter(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=4)
        repo.dbcollection = mock_collection

        count = await repo.get_item_book_count_by_filter_async({"title": "Test"})
        assert count == 4
        call_filter = mock_collection.count_documents.call_args[0][0]
        assert call_filter["tenant_id"] == "T001"

    @pytest.mark.asyncio
    async def test_get_item_book_count_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            async def side_effect():
                repo.dbcollection = mock_collection

            mock_init.side_effect = side_effect
            count = await repo.get_item_book_count_by_filter_async({})
            mock_init.assert_awaited_once()
            assert count == 0
