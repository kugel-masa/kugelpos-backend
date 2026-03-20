# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)

from app.services.promotion_master_service import PromotionMasterService
from app.models.documents.promotion_master_document import PromotionMasterDocument
from app.models.repositories.promotion_master_repository import PromotionMasterRepository


def make_category_detail(
    target_category_codes=None,
    target_store_codes=None,
    discount_rate=10.0,
):
    return PromotionMasterDocument.CategoryPromoDetail(
        target_category_codes=target_category_codes or ["001"],
        target_store_codes=target_store_codes or [],
        discount_rate=discount_rate,
    )


def make_promotion_doc(
    promotion_code="PROMO-01",
    promotion_type="category_discount",
    name="Test Promo",
    start_datetime=None,
    end_datetime=None,
    is_active=True,
    detail=None,
):
    start = start_datetime or datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = end_datetime or datetime(2024, 12, 31, tzinfo=timezone.utc)
    return PromotionMasterDocument(
        promotion_code=promotion_code,
        promotion_type=promotion_type,
        name=name,
        start_datetime=start,
        end_datetime=end,
        is_active=is_active,
        detail=detail or make_category_detail(),
    )


START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2024, 12, 31, tzinfo=timezone.utc)


class TestPromotionMasterServiceCreate:
    """Tests for PromotionMasterService.create_promotion_async."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=PromotionMasterRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return PromotionMasterService(promotion_master_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, mock_repo):
        """Valid promotion is created and returned."""
        mock_repo.get_promotion_by_code_async.return_value = None
        expected = make_promotion_doc()
        mock_repo.create_promotion_async.return_value = expected

        result = await service.create_promotion_async(
            promotion_code="PROMO-01",
            promotion_type="category_discount",
            name="Test Promo",
            start_datetime=START,
            end_datetime=END,
            detail=make_category_detail(),
        )

        assert result == expected
        mock_repo.create_promotion_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, mock_repo):
        """Duplicate promotion code raises DocumentAlreadyExistsException."""
        mock_repo.get_promotion_by_code_async.return_value = make_promotion_doc()

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_promotion_async(
                promotion_code="PROMO-01",
                promotion_type="category_discount",
                name="Dup",
                start_datetime=START,
                end_datetime=END,
                detail=make_category_detail(),
            )

    @pytest.mark.asyncio
    async def test_create_invalid_date_range_raises(self, service, mock_repo):
        """end_datetime <= start_datetime raises InvalidRequestDataException."""
        mock_repo.get_promotion_by_code_async.return_value = None

        with pytest.raises(InvalidRequestDataException):
            await service.create_promotion_async(
                promotion_code="PROMO-01",
                promotion_type="category_discount",
                name="Bad Dates",
                start_datetime=END,
                end_datetime=START,
                detail=make_category_detail(),
            )

    @pytest.mark.asyncio
    async def test_create_category_discount_without_detail_raises(self, service, mock_repo):
        """category_discount without detail raises InvalidRequestDataException."""
        mock_repo.get_promotion_by_code_async.return_value = None

        with pytest.raises(InvalidRequestDataException):
            await service.create_promotion_async(
                promotion_code="PROMO-01",
                promotion_type="category_discount",
                name="No Detail",
                start_datetime=START,
                end_datetime=END,
                detail=None,
            )

    @pytest.mark.asyncio
    async def test_create_category_discount_empty_categories_raises(self, service, mock_repo):
        """category_discount with empty target_category_codes raises InvalidRequestDataException.
        Note: CategoryPromoDetail.field_validator raises ValueError for empty list,
        so this test verifies the service-level check via a manually constructed detail."""
        mock_repo.get_promotion_by_code_async.return_value = None

        # Bypass Pydantic model validation by patching the detail object
        detail = MagicMock(spec=PromotionMasterDocument.CategoryPromoDetail)
        detail.target_category_codes = []
        detail.discount_rate = 10.0

        with pytest.raises(InvalidRequestDataException):
            await service.create_promotion_async(
                promotion_code="PROMO-01",
                promotion_type="category_discount",
                name="Empty Cat",
                start_datetime=START,
                end_datetime=END,
                detail=detail,
            )

    @pytest.mark.asyncio
    async def test_create_category_discount_invalid_rate_raises(self, service, mock_repo):
        """discount_rate > 100 raises InvalidRequestDataException.
        Note: CategoryPromoDetail has le=100 Pydantic constraint, so we bypass model
        construction and test the service-level validation directly."""
        mock_repo.get_promotion_by_code_async.return_value = None

        detail = MagicMock(spec=PromotionMasterDocument.CategoryPromoDetail)
        detail.target_category_codes = ["001"]
        detail.discount_rate = 150.0

        with pytest.raises(InvalidRequestDataException):
            await service.create_promotion_async(
                promotion_code="PROMO-01",
                promotion_type="category_discount",
                name="Bad Rate",
                start_datetime=START,
                end_datetime=END,
                detail=detail,
            )


class TestPromotionMasterServiceGet:
    """Tests for get_promotion_by_code_async, get_promotions_async, get_promotions_paginated_async."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=PromotionMasterRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return PromotionMasterService(promotion_master_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_get_by_code_success(self, service, mock_repo):
        """Returns promotion when found."""
        expected = make_promotion_doc()
        mock_repo.get_promotion_by_code_async.return_value = expected

        result = await service.get_promotion_by_code_async("PROMO-01")

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_by_code_not_found_raises(self, service, mock_repo):
        """Raises DocumentNotFoundException when not found."""
        mock_repo.get_promotion_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_promotion_by_code_async("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_promotions_no_filter(self, service, mock_repo):
        """Returns all promotions with no filter."""
        promotions = [make_promotion_doc("P1"), make_promotion_doc("P2")]
        mock_repo.get_promotions_by_filter_async.return_value = promotions

        result = await service.get_promotions_async(limit=10, page=1, sort=[])

        assert result == promotions
        call_kwargs = mock_repo.get_promotions_by_filter_async.call_args[0]
        assert call_kwargs[0] == {}  # empty filter

    @pytest.mark.asyncio
    async def test_get_promotions_with_type_filter(self, service, mock_repo):
        """Passes promotion_type filter to repository."""
        mock_repo.get_promotions_by_filter_async.return_value = []

        await service.get_promotions_async(
            limit=10, page=1, sort=[], promotion_type="category_discount"
        )

        filter_arg = mock_repo.get_promotions_by_filter_async.call_args[0][0]
        assert filter_arg["promotion_type"] == "category_discount"

    @pytest.mark.asyncio
    async def test_get_promotions_with_active_filter(self, service, mock_repo):
        """Passes is_active filter to repository."""
        mock_repo.get_promotions_by_filter_async.return_value = []

        await service.get_promotions_async(
            limit=10, page=1, sort=[], is_active=True
        )

        filter_arg = mock_repo.get_promotions_by_filter_async.call_args[0][0]
        assert filter_arg["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_promotions_paginated(self, service, mock_repo):
        """Paginated result is returned."""
        mock_result = MagicMock()
        mock_repo.get_promotions_by_filter_paginated_async.return_value = mock_result

        result = await service.get_promotions_paginated_async(limit=5, page=2, sort=[])

        assert result == mock_result


class TestPromotionMasterServiceGetActive:
    """Tests for get_active_promotions_async with various filter combinations."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=PromotionMasterRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return PromotionMasterService(promotion_master_repo=mock_repo)

    def make_promo_with_category(self, code, category_codes, promotion_type="category_discount"):
        detail = make_category_detail(target_category_codes=category_codes)
        return make_promotion_doc(promotion_code=code, promotion_type=promotion_type, detail=detail)

    @pytest.mark.asyncio
    async def test_get_active_no_filter(self, service, mock_repo):
        """No filter → calls get_active_promotions_async."""
        promos = [make_promotion_doc()]
        mock_repo.get_active_promotions_async.return_value = promos

        result = await service.get_active_promotions_async()

        assert result == promos
        mock_repo.get_active_promotions_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_by_store_only(self, service, mock_repo):
        """store_code only → calls get_active_promotions_by_store_async."""
        promos = [make_promotion_doc()]
        mock_repo.get_active_promotions_by_store_async.return_value = promos

        result = await service.get_active_promotions_async(store_code="S001")

        assert result == promos
        mock_repo.get_active_promotions_by_store_async.assert_called_once_with("S001")

    @pytest.mark.asyncio
    async def test_get_active_by_category_only(self, service, mock_repo):
        """category_code only → calls get_active_promotions_by_category_async."""
        promos = [make_promotion_doc()]
        mock_repo.get_active_promotions_by_category_async.return_value = promos

        result = await service.get_active_promotions_async(category_code="001")

        assert result == promos
        mock_repo.get_active_promotions_by_category_async.assert_called_once_with("001")

    @pytest.mark.asyncio
    async def test_get_active_by_store_and_category(self, service, mock_repo):
        """store_code + category_code → filters store results by category."""
        promos = [
            self.make_promo_with_category("P1", ["001", "002"]),
            self.make_promo_with_category("P2", ["003"]),
        ]
        mock_repo.get_active_promotions_by_store_async.return_value = promos

        result = await service.get_active_promotions_async(store_code="S001", category_code="001")

        assert len(result) == 1
        assert result[0].promotion_code == "P1"

    @pytest.mark.asyncio
    async def test_get_active_with_promotion_type_filter(self, service, mock_repo):
        """promotion_type filter is applied to results."""
        promos = [
            make_promotion_doc("P1", promotion_type="category_discount"),
            make_promotion_doc("P2", promotion_type="flat_discount"),
        ]
        mock_repo.get_active_promotions_async.return_value = promos

        result = await service.get_active_promotions_async(promotion_type="category_discount")

        assert len(result) == 1
        assert result[0].promotion_code == "P1"

    @pytest.mark.asyncio
    async def test_get_active_by_store_and_category_with_type_filter(self, service, mock_repo):
        """store+category+type all filter correctly."""
        promos = [
            self.make_promo_with_category("P1", ["001"], promotion_type="category_discount"),
            self.make_promo_with_category("P2", ["001"], promotion_type="flat_discount"),
        ]
        mock_repo.get_active_promotions_by_store_async.return_value = promos

        result = await service.get_active_promotions_async(
            store_code="S001", category_code="001", promotion_type="category_discount"
        )

        assert len(result) == 1
        assert result[0].promotion_code == "P1"


class TestPromotionMasterServiceUpdate:
    """Tests for update_promotion_async."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=PromotionMasterRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return PromotionMasterService(promotion_master_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_update_success(self, service, mock_repo):
        """Existing promotion is updated and returned."""
        existing = make_promotion_doc()
        updated = make_promotion_doc(name="Updated Name")
        mock_repo.get_promotion_by_code_async.return_value = existing
        mock_repo.update_promotion_async.return_value = updated

        result = await service.update_promotion_async("PROMO-01", {"name": "Updated Name"})

        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, mock_repo):
        """Raises DocumentNotFoundException for unknown promotion code."""
        mock_repo.get_promotion_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_promotion_async("NONEXISTENT", {"name": "X"})

    @pytest.mark.asyncio
    async def test_update_invalid_date_range_raises(self, service, mock_repo):
        """end_datetime <= start_datetime raises InvalidRequestDataException."""
        existing = make_promotion_doc(start_datetime=START, end_datetime=END)
        mock_repo.get_promotion_by_code_async.return_value = existing

        with pytest.raises(InvalidRequestDataException):
            await service.update_promotion_async("PROMO-01", {
                "start_datetime": END,
                "end_datetime": START,
            })

    @pytest.mark.asyncio
    async def test_update_invalid_discount_rate_raises(self, service, mock_repo):
        """discount_rate <= 0 in detail raises InvalidRequestDataException."""
        existing = make_promotion_doc()
        mock_repo.get_promotion_by_code_async.return_value = existing

        with pytest.raises(InvalidRequestDataException):
            await service.update_promotion_async("PROMO-01", {
                "detail": {"discount_rate": -5.0}
            })


class TestPromotionMasterServiceDelete:
    """Tests for delete_promotion_async."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=PromotionMasterRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return PromotionMasterService(promotion_master_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_delete_success(self, service, mock_repo):
        """Existing promotion is deleted."""
        mock_repo.get_promotion_by_code_async.return_value = make_promotion_doc()

        await service.delete_promotion_async("PROMO-01")

        mock_repo.delete_promotion_async.assert_called_once_with("PROMO-01")

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, mock_repo):
        """Raises DocumentNotFoundException for unknown promotion code."""
        mock_repo.get_promotion_by_code_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_promotion_async("NONEXISTENT")
