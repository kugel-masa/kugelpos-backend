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
# Cache hit/miss/TTL/invalidate behaviour is owned by the shared base class
# and verified in test_abstract_master_data_repository.py. The tests below
# focus on what the Web subclass is uniquely responsible for: building the
# upstream URL/auth correctly and mapping responses & errors.

from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend


def _make_item_web_repo(**overrides):
    terminal = overrides.pop("terminal_info", _make_terminal_info())
    return ItemMasterWebRepository(
        tenant_id=overrides.pop("tenant_id", "T001"),
        store_code=overrides.pop("store_code", "S001"),
        terminal_info=terminal,
        cache_backend=overrides.pop("cache_backend", InMemoryCacheBackend()),
    )


class TestItemMasterWebRepositoryFetch:
    """HTTP request construction and response mapping."""

    @pytest.mark.asyncio
    async def test_fetch_hits_expected_endpoint(self):
        repo = _make_item_web_repo()
        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-02", "description": "From API", "unit_price": 100.0}
        }
        with patch(
            "app.models.repositories.item_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_item_by_code_async("ITEM-02")

        assert result.item_code == "ITEM-02"
        assert result.description == "From API"
        endpoint = mock_client.get.call_args[0][0]
        assert endpoint == "/tenants/T001/stores/S001/items/ITEM-02/details"

    @pytest.mark.asyncio
    async def test_fetch_with_jwt_uses_bearer_header(self):
        terminal = _make_terminal_info()
        # TerminalInfoDocument does not declare jwt_token but the repo reads it
        # via getattr; attach dynamically to exercise the JWT branch.
        object.__setattr__(terminal, "jwt_token", "TOKEN-XYZ")
        repo = _make_item_web_repo(terminal_info=terminal)

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-02", "description": "x"}
        }
        with patch(
            "app.models.repositories.item_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            await repo.get_item_by_code_async("ITEM-02")

        kwargs = mock_client.get.call_args.kwargs
        assert kwargs["headers"] == {"Authorization": "Bearer TOKEN-XYZ"}
        # JWT path should not send terminal_id as a query parameter.
        assert kwargs["params"] == {}

    @pytest.mark.asyncio
    async def test_fetch_without_jwt_falls_back_to_api_key(self):
        repo = _make_item_web_repo()

        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "data": {"item_code": "ITEM-02", "description": "x"}
        }
        with patch(
            "app.models.repositories.item_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            await repo.get_item_by_code_async("ITEM-02")

        kwargs = mock_client.get.call_args.kwargs
        assert kwargs["headers"] == {"X-API-KEY": "test-api-key"}
        assert kwargs["params"] == {"terminal_id": "T001-S001-1"}
        mock_client.get.assert_awaited_once()


class TestItemMasterWebRepositoryErrors:
    """Error mapping from upstream failures to repository exceptions."""

    @pytest.mark.asyncio
    async def test_404_raises_not_found_exception(self):
        repo = _make_item_web_repo()
        error = Exception("Not found")
        error.status_code = 404
        mock_client = AsyncMock()
        mock_client.get.side_effect = error
        with patch(
            "app.models.repositories.item_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(NotFoundException):
                await repo.get_item_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_other_error_raises_repository_exception(self):
        repo = _make_item_web_repo()
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        with patch(
            "app.models.repositories.item_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            with pytest.raises(RepositoryException):
                await repo.get_item_by_code_async("ITEM-ERR")


# =========================================================================
# PaymentMasterWebRepository tests
# =========================================================================


class TestPaymentMasterWebRepository:
    """PaymentMasterWebRepository — fetch and error mapping.

    Caching behaviour is owned by AbstractMasterDataRepository and tested in
    test_abstract_master_data_repository.py.
    """

    def _make_repo(self):
        terminal = _make_terminal_info()
        return PaymentMasterWebRepository(
            tenant_id="T001",
            terminal_info=terminal,
            cache_backend=InMemoryCacheBackend(),
        )

    @pytest.mark.asyncio
    async def test_fetch_returns_payment_from_api(self):
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
        endpoint = mock_client.get.call_args[0][0]
        assert endpoint == "/tenants/T001/payments/CARD"

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


# =========================================================================
# SettingsMasterWebRepository tests
# =========================================================================


class TestSettingsMasterWebRepositoryGetAll:
    """SettingsMaster — bulk fetch via _fetch_list."""

    def _make_repo(self):
        terminal = _make_terminal_info()
        return SettingsMasterWebRepository(
            tenant_id="T001",
            terminal_info=terminal,
            cache_backend=InMemoryCacheBackend(),
            store_code="S001",
            terminal_no=1,
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

    @pytest.mark.asyncio
    async def test_get_all_settings_empty_on_no_data(self):
        repo = self._make_repo()
        mock_client = AsyncMock()
        mock_client.get.return_value = {"success": True, "data": None}
        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            assert await repo.get_all_settings_async() == []

    @pytest.mark.asyncio
    async def test_get_all_settings_empty_on_success_false(self):
        repo = self._make_repo()
        mock_client = AsyncMock()
        mock_client.get.return_value = {"success": False, "data": []}
        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            assert await repo.get_all_settings_async() == []

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
            # _fetch_list converts 404 to [] (legacy behaviour).
            assert await repo.get_all_settings_async() == []

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
    """SettingsMaster — per-name fetch via _fetch_one."""

    def _make_repo(self):
        terminal = _make_terminal_info()
        return SettingsMasterWebRepository(
            tenant_id="T001",
            terminal_info=terminal,
            cache_backend=InMemoryCacheBackend(),
            store_code="S001",
            terminal_no=1,
        )

    @pytest.mark.asyncio
    async def test_returns_setting_with_value_mapped_to_default_value(self):
        repo = self._make_repo()
        mock_client = AsyncMock()
        mock_client.get.return_value = {"data": {"value": "exclusive"}}
        with patch(
            "app.models.repositories.settings_master_web_repository.get_pooled_client",
            return_value=mock_client,
        ):
            result = await repo.get_settings_value_by_name_async("tax_mode")
        assert result.name == "tax_mode"
        # The /settings/{name}/value endpoint returns data.value; the repo
        # maps it into default_value to keep get_setting_value()'s fallback path
        # working (SettingsMasterDocument has no `value` field).
        assert result.default_value == "exclusive"

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
            # Legacy contract: per-name 404 surfaces as None, not an exception.
            assert await repo.get_settings_value_by_name_async("missing") is None

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

    def test_is_store_scoped_property_reflects_store_code(self):
        # With store_code → per-store scoping; without → tenant-wide.
        terminal = _make_terminal_info()
        cache = InMemoryCacheBackend()
        store_repo = SettingsMasterWebRepository(
            tenant_id="T001", terminal_info=terminal, cache_backend=cache,
            store_code="S001", terminal_no=1,
        )
        tenant_repo = SettingsMasterWebRepository(
            tenant_id="T001", terminal_info=terminal, cache_backend=cache,
        )
        assert store_repo.is_store_scoped is True
        assert tenant_repo.is_store_scoped is False


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
            cache_backend=InMemoryCacheBackend(),
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
