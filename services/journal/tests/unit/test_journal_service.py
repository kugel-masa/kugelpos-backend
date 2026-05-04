# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.journal_service import JournalService
from app.models.documents.jornal_document import JournalDocument
from app.models.repositories.journal_repository import JournalRepository
from app.exceptions.journal_exceptions import (
    JournalCreationException,
    JournalNotFoundException,
    JournalQueryException,
    JournalValidationException,
)


class TestJournalServiceReceive:
    """Test cases for JournalService.receive_journal_async."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=JournalRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return JournalService(journal_repository=mock_repo)

    @pytest.fixture
    def journal_dict(self):
        return {
            "tenant_id": "T001",
            "store_code": "S001",
            "terminal_no": 1,
            "transaction_no": 100,
            "transaction_type": 101,
            "business_date": "20240101",
            "open_counter": 1,
            "business_counter": 10,
            "generate_date_time": "2024-01-01T10:00:00",
            "receipt_no": 1001,
            "amount": 1100.0,
            "quantity": 2,
            "staff_id": "ST01",
            "user_id": "U01",
            "journal_text": "journal",
            "receipt_text": "receipt",
        }

    @pytest.mark.asyncio
    async def test_receive_journal_success(self, service, mock_repo, journal_dict):
        """Valid journal dict is stored and returned as JournalDocument."""
        mock_repo.create_journal_async.return_value = None

        result = await service.receive_journal_async(journal_dict)

        assert isinstance(result, JournalDocument)
        assert result.tenant_id == "T001"
        assert result.store_code == "S001"
        mock_repo.create_journal_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_journal_creation_error(self, service, mock_repo, journal_dict):
        """Repository error raises JournalCreationException."""
        mock_repo.create_journal_async.side_effect = Exception("DB error")

        with pytest.raises(JournalCreationException):
            await service.receive_journal_async(journal_dict)

    @pytest.mark.asyncio
    async def test_receive_journal_validation_error(self, service, mock_repo):
        """Invalid data that causes ValueError raises JournalValidationException."""
        # transaction_type must be int; passing an invalid nested structure
        # that triggers a ValueError during JournalDocument construction
        invalid_dict = {"transaction_type": "not-an-int-that-pydantic-rejects"}

        # Patch JournalDocument to raise ValueError
        import unittest.mock as mock
        with mock.patch(
            "app.services.journal_service.JournalDocument",
            side_effect=ValueError("validation failed"),
        ):
            with pytest.raises(JournalValidationException):
                await service.receive_journal_async(invalid_dict)


class TestJournalServiceGetJournals:
    """Test cases for JournalService.get_journals_async and get_journals_paginated_async."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock(spec=JournalRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return JournalService(journal_repository=mock_repo)

    @pytest.fixture
    def sample_journals(self):
        return [
            JournalDocument(
                tenant_id="T001",
                store_code="S001",
                terminal_no=1,
                transaction_no=i,
                transaction_type=101,
                business_date="20240101",
                open_counter=1,
                business_counter=10,
                generate_date_time="2024-01-01T10:00:00",
                journal_text="journal",
                receipt_text="receipt",
            )
            for i in range(3)
        ]

    @pytest.mark.asyncio
    async def test_get_journals_returns_results(self, service, mock_repo, sample_journals):
        """Returns list of journals when found."""
        mock_repo.get_journals_async.return_value = sample_journals

        result = await service.get_journals_async(store_code="S001")

        assert len(result) == 3
        assert result[0].store_code == "S001"

    @pytest.mark.asyncio
    async def test_get_journals_not_found(self, service, mock_repo):
        """Empty result raises JournalNotFoundException."""
        mock_repo.get_journals_async.return_value = []

        with pytest.raises(JournalNotFoundException):
            await service.get_journals_async(store_code="S001")

    @pytest.mark.asyncio
    async def test_get_journals_query_error(self, service, mock_repo):
        """Repository error (non-NotFound) raises JournalQueryException."""
        mock_repo.get_journals_async.side_effect = Exception("DB error")

        with pytest.raises(JournalQueryException):
            await service.get_journals_async(store_code="S001")

    @pytest.mark.asyncio
    async def test_get_journals_with_filters(self, service, mock_repo, sample_journals):
        """Filters are forwarded to the repository."""
        mock_repo.get_journals_async.return_value = sample_journals

        await service.get_journals_async(
            store_code="S001",
            terminals=[1, 2],
            transaction_types=[101],
            business_date_from="20240101",
            business_date_to="20240131",
            receipt_no_from=1,
            receipt_no_to=999,
            keywords=["keyword"],
            limit=50,
            page=2,
        )

        call_kwargs = mock_repo.get_journals_async.call_args[1]
        assert call_kwargs["store_code"] == "S001"
        assert call_kwargs["terminals"] == [1, 2]
        assert call_kwargs["transaction_types"] == [101]
        assert call_kwargs["limit"] == 50
        assert call_kwargs["page"] == 2

    @pytest.mark.asyncio
    async def test_get_journals_not_found_propagates(self, service, mock_repo):
        """JournalNotFoundException propagates through, not wrapped in JournalQueryException."""
        mock_repo.get_journals_async.return_value = []

        with pytest.raises(JournalNotFoundException):
            await service.get_journals_async(store_code="S001")

    @pytest.mark.asyncio
    async def test_get_journals_paginated_success(self, service, mock_repo):
        """Paginated result is returned from the repository."""
        mock_paginated = MagicMock()
        mock_repo.get_journals_paginated_async.return_value = mock_paginated

        result = await service.get_journals_paginated_async(store_code="S001", limit=10, page=1)

        assert result == mock_paginated
        mock_repo.get_journals_paginated_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_journals_paginated_query_error(self, service, mock_repo):
        """Repository error raises JournalQueryException."""
        mock_repo.get_journals_paginated_async.side_effect = Exception("DB error")

        with pytest.raises(JournalQueryException):
            await service.get_journals_paginated_async(store_code="S001")

    @pytest.mark.asyncio
    async def test_get_journals_paginated_filters_forwarded(self, service, mock_repo):
        """Filters are forwarded to the paginated repository method."""
        mock_repo.get_journals_paginated_async.return_value = MagicMock()

        await service.get_journals_paginated_async(
            store_code="S001",
            terminals=[1],
            transaction_types=[101, -101],
            business_date_from="20240101",
            business_date_to="20240131",
            limit=20,
            page=3,
        )

        call_kwargs = mock_repo.get_journals_paginated_async.call_args[1]
        assert call_kwargs["store_code"] == "S001"
        assert call_kwargs["terminals"] == [1]
        assert call_kwargs["limit"] == 20
        assert call_kwargs["page"] == 3
