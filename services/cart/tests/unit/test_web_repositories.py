"""
Unit tests for the web repository layer of the cart service.

Tests cover:
- ItemMasterWebRepository: cache hit, cache miss (HTTP call), cache expiration, 404 error, other error
- PaymentMasterWebRepository: cache hit, cache miss, 404, other error
- SettingsMasterWebRepository: get_all_settings success/404/error, get_settings_value_by_name cache/miss/404/error
- PromotionMasterWebRepository: success, error, parse failure
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.exceptions import RepositoryException, NotFoundException

from app.models.documents.item_master_document import ItemMasterDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.documents.promotion_master_document import PromotionMasterDocument

from app.models.repositories.item_master_web_repository import ItemMasterWebRepository
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from app.models.repositories.settings_master_web_repository import SettingsMasterWebRepository
from app.models.repositories.promotion_master_web_repository import PromotionMasterWebRepository


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_terminal_info(**overrides) -> TerminalInfoDocument:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        terminal_id="T001-S001-1",
        api_key="test-api-key",
        business_date="20240601",
        staff=StaffMasterDocument(id="staff01", name="Test Staff"),
    )
    defaults.update(overrides)
    return TerminalInfoDocument(**defaults)


# =========================================================================
# ItemMasterWebRepository tests
# =========================================================================


class TestItemMasterWebRepositoryCacheHit:
    """Tests for cache hit scenario."""

    @pytest.mark.asyncio
    async def test_get_item_by_code_returns_cached_item(self):
        terminal = _make_terminal_info()
        item = ItemMasterDocument(item_code="ITEM-01", description="Cached Item")
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
            item_master_documents=[item],
        )

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = True
            mock_cs.ITEM_CACHE_TTL_SECONDS = 300

            result = await repo.get_item_by_code_async("ITEM-01")

        assert result.item_code == "ITEM-01"
        assert result.description == "Cached Item"


class TestItemMasterWebRepositoryCacheMiss:
    """Tests for cache miss scenario - item fetched via HTTP."""

    @pytest.mark.asyncio
    async def test_get_item_by_code_fetches_from_api(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-02", "description": "From API", "unit_price": 100.0}
        }

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = True
            mock_cs.ITEM_CACHE_TTL_SECONDS = 300
            with patch(
                "app.models.repositories.item_master_web_repository.get_pooled_client",
                return_value=mock_client,
            ):
                result = await repo.get_item_by_code_async("ITEM-02")

        assert result.item_code == "ITEM-02"
        assert result.description == "From API"
        mock_client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_item_by_code_adds_to_cache_after_fetch(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-03", "description": "New"}
        }

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = True
            mock_cs.ITEM_CACHE_TTL_SECONDS = 300
            with patch(
                "app.models.repositories.item_master_web_repository.get_pooled_client",
                return_value=mock_client,
            ):
                await repo.get_item_by_code_async("ITEM-03")

        # The item should now be in the cache
        assert len(repo._item_cache) == 1
        assert repo._item_cache[0][0].item_code == "ITEM-03"


class TestItemMasterWebRepositoryCacheExpiration:
    """Tests for cache expiration."""

    @pytest.mark.asyncio
    async def test_expired_cache_entry_triggers_api_call(self):
        terminal = _make_terminal_info()
        item = ItemMasterDocument(item_code="ITEM-04", description="Old")
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )
        # Manually add an expired cache entry
        repo._item_cache = [(item, time.time() - 999)]

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-04", "description": "Refreshed"}
        }

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = True
            mock_cs.ITEM_CACHE_TTL_SECONDS = 300
            with patch(
                "app.models.repositories.item_master_web_repository.get_pooled_client",
                return_value=mock_client,
            ):
                result = await repo.get_item_by_code_async("ITEM-04")

        assert result.description == "Refreshed"
        mock_client.get.assert_awaited_once()


class TestItemMasterWebRepositoryCacheDisabled:
    """Tests when cache is disabled."""

    @pytest.mark.asyncio
    async def test_always_calls_api_when_cache_disabled(self):
        terminal = _make_terminal_info()
        item = ItemMasterDocument(item_code="ITEM-05", description="Cached")
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
            item_master_documents=[item],
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-05", "description": "From API"}
        }

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = False
            with patch(
                "app.models.repositories.item_master_web_repository.get_pooled_client",
                return_value=mock_client,
            ):
                result = await repo.get_item_by_code_async("ITEM-05")

        assert result.description == "From API"
        mock_client.get.assert_awaited_once()


class TestItemMasterWebRepositoryErrors:
    """Tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_404_raises_not_found_exception(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )

        error = Exception("Not found")
        error.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.side_effect = error

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = False
            with patch(
                "app.models.repositories.item_master_web_repository.get_pooled_client",
                return_value=mock_client,
            ):
                with pytest.raises(NotFoundException):
                    await repo.get_item_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_other_error_raises_repository_exception(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")

        with patch("app.models.repositories.item_master_web_repository.cart_settings") as mock_cs:
            mock_cs.USE_ITEM_CACHE = False
            with patch(
                "app.models.repositories.item_master_web_repository.get_pooled_client",
                return_value=mock_client,
            ):
                with pytest.raises(RepositoryException):
                    await repo.get_item_by_code_async("ITEM-ERR")


class TestItemMasterWebRepositoryProperties:
    """Tests for property accessors and setters."""

    def test_item_master_documents_property(self):
        terminal = _make_terminal_info()
        items = [
            ItemMasterDocument(item_code="A"),
            ItemMasterDocument(item_code="B"),
        ]
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
            item_master_documents=items,
        )
        result = repo.item_master_documents
        assert len(result) == 2
        assert result[0].item_code == "A"
        assert result[1].item_code == "B"

    def test_item_master_documents_setter(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )
        items = [ItemMasterDocument(item_code="C")]
        repo.item_master_documents = items
        assert len(repo._item_cache) == 1
        assert repo._item_cache[0][0].item_code == "C"

    def test_item_master_documents_setter_with_none(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
            item_master_documents=[ItemMasterDocument(item_code="X")],
        )
        # Setting None should not change the cache (guard in setter)
        repo.item_master_documents = None
        assert len(repo._item_cache) == 1

    def test_set_item_master_documents(self):
        terminal = _make_terminal_info()
        repo = ItemMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_info=terminal,
        )
        items = [ItemMasterDocument(item_code="D")]
        repo.set_item_master_documents(items)
        assert len(repo._item_cache) == 1
        assert repo._item_cache[0][0].item_code == "D"


# =========================================================================
# PaymentMasterWebRepository tests
# =========================================================================


class TestPaymentMasterWebRepository:
    """Tests for PaymentMasterWebRepository."""

    def _make_repo(self, payment_docs=None):
        terminal = _make_terminal_info()
        return PaymentMasterWebRepository(
            tenant_id="T001",
            terminal_info=terminal,
            payment_master_documents=payment_docs,
        )

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_payment(self):
        payment = PaymentMasterDocument(payment_code="CASH", description="Cash")
        repo = self._make_repo(payment_docs=[payment])

        result = await repo.get_payment_by_code_async("CASH")

        assert result.payment_code == "CASH"
        assert result.description == "Cash"

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_from_api(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"payment_code": "CARD", "description": "Credit Card"}
        }

        with patch(
            "app.models.repositories.payment_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_payment_by_code_async("CARD")

        assert result.payment_code == "CARD"
        assert result.description == "Credit Card"
        mock_client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initializes_empty_list_when_none(self):
        repo = self._make_repo(payment_docs=None)
        assert repo.payment_master_documents is None

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"payment_code": "P1", "description": "P1"}
        }

        with patch(
            "app.models.repositories.payment_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            await repo.get_payment_by_code_async("P1")

        assert repo.payment_master_documents == []

    @pytest.mark.asyncio
    async def test_404_raises_not_found_exception(self):
        repo = self._make_repo()

        error = Exception("Not found")
        error.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.side_effect = error

        with patch(
            "app.models.repositories.payment_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(NotFoundException):
                await repo.get_payment_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_other_error_raises_repository_exception(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Timeout")

        with patch(
            "app.models.repositories.payment_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(RepositoryException):
                await repo.get_payment_by_code_async("PAY-ERR")

    def test_set_payment_master_documents(self):
        repo = self._make_repo()
        docs = [PaymentMasterDocument(payment_code="X")]
        repo.set_payment_master_documents(docs)
        assert repo.payment_master_documents == docs


# =========================================================================
# SettingsMasterWebRepository tests
# =========================================================================


class TestSettingsMasterWebRepositoryGetAll:
    """Tests for get_all_settings_async."""

    def _make_repo(self, settings_docs=None):
        terminal = _make_terminal_info()
        return SettingsMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            terminal_info=terminal,
            settings_master_documents=settings_docs,
        )

    @pytest.mark.asyncio
    async def test_get_all_settings_success(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "success": True,
            "data": [
                {"name": "setting1", "default_value": "val1"},
                {"name": "setting2", "default_value": "val2"},
            ],
        }

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_all_settings_async()

        assert len(result) == 2
        assert result[0].name == "setting1"
        assert result[1].name == "setting2"
        assert repo.settings_master_documents == result

    @pytest.mark.asyncio
    async def test_get_all_settings_empty_on_no_data(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {"success": True, "data": None}

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_all_settings_async()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_settings_empty_on_success_false(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {"success": False, "data": []}

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_all_settings_async()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_settings_404_returns_empty(self):
        repo = self._make_repo()

        error = Exception("Not found")
        error.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.side_effect = error

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_all_settings_async()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_settings_other_error_raises(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(RepositoryException):
                await repo.get_all_settings_async()


class TestSettingsMasterWebRepositoryGetByName:
    """Tests for get_settings_value_by_name_async."""

    def _make_repo(self, settings_docs=None):
        terminal = _make_terminal_info()
        return SettingsMasterWebRepository(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            terminal_info=terminal,
            settings_master_documents=settings_docs,
        )

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_setting(self):
        setting = SettingsMasterDocument(name="tax_mode", default_value="inclusive")
        repo = self._make_repo(settings_docs=[setting])

        result = await repo.get_settings_value_by_name_async("tax_mode")

        assert result.name == "tax_mode"

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_from_api(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"value": "exclusive"}
        }

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_settings_value_by_name_async("tax_mode")

        assert result.name == "tax_mode"
        assert result.default_value is None  # Only name and value are set from API

    @pytest.mark.asyncio
    async def test_cache_miss_adds_to_cache(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"value": "val1"}
        }

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            await repo.get_settings_value_by_name_async("setting_x")

        assert len(repo.settings_master_documents) == 1
        assert repo.settings_master_documents[0].name == "setting_x"

    @pytest.mark.asyncio
    async def test_initializes_empty_list_when_none(self):
        repo = self._make_repo(settings_docs=None)

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"value": "v"}
        }

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            await repo.get_settings_value_by_name_async("s")

        assert isinstance(repo.settings_master_documents, list)

    @pytest.mark.asyncio
    async def test_404_returns_none(self):
        repo = self._make_repo()

        error = Exception("Not found")
        error.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.side_effect = error

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_settings_value_by_name_async("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_other_error_raises_repository_exception(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Server error")

        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(RepositoryException):
                await repo.get_settings_value_by_name_async("err_setting")

    def test_set_settings_master_documents(self):
        repo = self._make_repo()
        docs = [SettingsMasterDocument(name="s1")]
        repo.set_settings_master_documents(docs)
        assert repo.settings_master_documents == docs


# =========================================================================
# PromotionMasterWebRepository tests
# =========================================================================


class TestPromotionMasterWebRepository:
    """Tests for PromotionMasterWebRepository."""

    def _make_repo(self):
        terminal = _make_terminal_info()
        return PromotionMasterWebRepository(
            tenant_id="T001",
            terminal_info=terminal,
        )

    @pytest.mark.asyncio
    async def test_get_active_promotions_success(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": [
                {
                    "tenantId": "T001",
                    "promotionCode": "PROMO-01",
                    "promotionType": "category",
                    "name": "Summer Sale",
                    "description": "10% off",
                    "startDatetime": "2024-06-01T00:00:00Z",
                    "endDatetime": "2024-08-31T23:59:59Z",
                    "isActive": True,
                    "detail": {"discount_rate": 0.10},
                },
            ],
        }

        with patch(
            "app.models.repositories.promotion_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_active_promotions_by_store_async("S001")

        assert len(result) == 1
        assert result[0].promotion_code == "PROMO-01"
        assert result[0].promotion_type == "category"
        assert result[0].detail == {"discount_rate": 0.10}

    @pytest.mark.asyncio
    async def test_get_active_promotions_uses_terminal_store_when_none(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {"data": []}

        with patch(
            "app.models.repositories.promotion_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            await repo.get_active_promotions_by_store_async()

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["storeCode"] == "S001"

    @pytest.mark.asyncio
    async def test_get_active_promotions_empty_data(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {"data": []}

        with patch(
            "app.models.repositories.promotion_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_active_promotions_by_store_async("S001")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_active_promotions_error_raises_repository_exception(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Service unavailable")

        with patch(
            "app.models.repositories.promotion_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(RepositoryException):
                await repo.get_active_promotions_by_store_async("S001")

    @pytest.mark.asyncio
    async def test_get_active_promotions_skips_unparseable_entries(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": [
                {
                    "tenantId": "T001",
                    "promotionCode": "PROMO-OK",
                    "promotionType": "category",
                    "name": "Good Promo",
                    "isActive": True,
                },
                # This entry has bad datetime that will cause parse error
                "not_a_dict",
            ],
        }

        with patch(
            "app.models.repositories.promotion_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_active_promotions_by_store_async("S001")

        # Only the parseable entry should be returned
        assert len(result) == 1
        assert result[0].promotion_code == "PROMO-OK"

    @pytest.mark.asyncio
    async def test_get_active_promotions_missing_data_key(self):
        repo = self._make_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {"success": True}

        with patch(
            "app.models.repositories.promotion_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_active_promotions_by_store_async("S001")

        assert result == []
