# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
import pytest
from unittest.mock import AsyncMock, MagicMock

from kugel_common.exceptions import DocumentNotFoundException, DocumentAlreadyExistsException, InvalidRequestDataException

from app.services.settings_master_service import SettingsMasterService
from app.models.documents.settings_master_document import SettingsMasterDocument



# ---------------------------------------------------------------------------
# SettingsMasterService
# ---------------------------------------------------------------------------

class TestSettingsMasterService:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return SettingsMasterService(settings_master_repo=repo)

    @pytest.mark.asyncio
    async def test_create_success(self, service, repo):
        repo.get_settings_by_name_async.return_value = None
        doc = SettingsMasterDocument()
        repo.create_settings_async.return_value = doc

        result = await service.create_settings_async("KEY-01", "value", [])
        assert result == doc

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, service, repo):
        repo.get_settings_by_name_async.return_value = MagicMock(tenant_id="T001")

        with pytest.raises(DocumentAlreadyExistsException):
            await service.create_settings_async("KEY-01", "value", [])

    @pytest.mark.asyncio
    async def test_get_by_name_success(self, service, repo):
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_by_name_async("KEY-01")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_by_name_returns_none_when_not_found(self, service, repo):
        """get_settings_by_name_async returns None (no raise) when not found."""
        repo.get_settings_by_name_async.return_value = None

        result = await service.get_settings_by_name_async("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_settings(self, service, repo):
        repo.get_settings_all_async.return_value = []
        await service.get_settings_all_async(limit=10, page=1, sort=[])
        repo.get_settings_all_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_settings_paginated(self, service, repo):
        """Returns (list, count) tuple from separate repo calls."""
        mock_list = [SettingsMasterDocument()]
        repo.get_settings_all_async.return_value = mock_list
        repo.get_settings_count_async.return_value = 5

        result, count = await service.get_settings_all_paginated_async(limit=10, page=1, sort=[])
        assert result == mock_list
        assert count == 5

    @pytest.mark.asyncio
    async def test_update_success(self, service, repo):
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        result = await service.update_settings_async("KEY-01", {"default_value": "new"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, service, repo):
        repo.get_settings_by_name_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_settings_async("NONEXISTENT", {})

    @pytest.mark.asyncio
    async def test_delete_success(self, service, repo):
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        repo.delete_settings_async.return_value = None

        await service.delete_settings_async("KEY-01")
        repo.delete_settings_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, service, repo):
        repo.get_settings_by_name_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_settings_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# ItemCommonMasterService
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# SettingsMasterService - additional coverage
# ---------------------------------------------------------------------------

class TestSettingsMasterServiceAdditional:
    @pytest.fixture
    def repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, repo):
        return SettingsMasterService(settings_master_repo=repo)

    @pytest.mark.asyncio
    async def test_get_settings_value_store_terminal_match(self, service, repo):
        """Lines 112-122: priority lookup - store+terminal specific match."""
        from app.models.documents.settings_master_document import SettingsValue

        doc = SettingsMasterDocument()
        doc.default_value = "default"
        doc.values = [
            SettingsValue(store_code="S1", terminal_no=1, value="store_terminal"),
            SettingsValue(store_code="S1", terminal_no=None, value="store_only"),
            SettingsValue(store_code=None, terminal_no=None, value="global"),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S1", 1)
        assert result == "store_terminal"

    @pytest.mark.asyncio
    async def test_get_settings_value_store_only_match(self, service, repo):
        """Priority lookup - store specific match (no terminal match)."""
        from app.models.documents.settings_master_document import SettingsValue

        doc = SettingsMasterDocument()
        doc.default_value = "default"
        doc.values = [
            SettingsValue(store_code="S1", terminal_no=None, value="store_only"),
            SettingsValue(store_code=None, terminal_no=None, value="global"),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S1", 99)
        assert result == "store_only"

    @pytest.mark.asyncio
    async def test_get_settings_value_global_match(self, service, repo):
        """Priority lookup - global match (no store/terminal match)."""
        from app.models.documents.settings_master_document import SettingsValue

        doc = SettingsMasterDocument()
        doc.default_value = "default"
        doc.values = [
            SettingsValue(store_code=None, terminal_no=None, value="global"),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S2", 1)
        assert result == "global"

    @pytest.mark.asyncio
    async def test_get_settings_value_falls_back_to_default(self, service, repo):
        """Lines 124-125: no values match, returns default_value."""
        doc = SettingsMasterDocument()
        doc.default_value = "fallback"
        doc.values = [
            MagicMock(
                model_dump=MagicMock(
                    return_value={"store_code": "OTHER", "terminal_no": 99, "value": "nope"}
                )
            ),
        ]
        repo.get_settings_by_name_async.return_value = doc

        result = await service.get_settings_value_by_name_async("KEY", "S1", 1)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_get_settings_value_not_found_raises(self, service, repo):
        """Lines 107-109: setting not found raises DocumentNotFoundException."""
        repo.get_settings_by_name_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_settings_value_by_name_async("MISSING", "S1", 1)

    @pytest.mark.asyncio
    async def test_update_name_mismatch_raises(self, service, repo):
        """Lines 176-178: name in update_data differs from path name."""
        with pytest.raises(InvalidRequestDataException):
            await service.update_settings_async(
                "KEY-01", {"name": "KEY-OTHER", "default_value": "new"}
            )

    @pytest.mark.asyncio
    async def test_update_removes_name_from_data(self, service, repo):
        """Lines 188-189: name is removed from update_data before repo call."""
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        data = {"name": "KEY-01", "default_value": "new"}
        result = await service.update_settings_async("KEY-01", data)

        assert result == updated
        call_args = repo.update_settings_async.call_args
        assert "name" not in call_args[0][1]

    @pytest.mark.asyncio
    async def test_update_processes_default_value_json(self, service, repo):
        """Lines 192-193: default_value is processed through ensure_json_format."""
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        data = {"default_value": "[{'a': 1}]"}
        await service.update_settings_async("KEY-01", data)

        call_args = repo.update_settings_async.call_args
        assert call_args[0][1]["default_value"] == '[{"a": 1}]'

    @pytest.mark.asyncio
    async def test_update_processes_values_list(self, service, repo):
        """Lines 196-197: values list is processed through process_setting_values."""
        doc = SettingsMasterDocument()
        repo.get_settings_by_name_async.return_value = doc
        updated = SettingsMasterDocument()
        repo.update_settings_async.return_value = updated

        data = {"values": [{"value": "[{'x': 1}]"}]}
        await service.update_settings_async("KEY-01", data)

        call_args = repo.update_settings_async.call_args
        assert call_args[0][1]["values"][0]["value"] == '[{"x": 1}]'


# ---------------------------------------------------------------------------
# ItemStoreMasterService - additional coverage
# ---------------------------------------------------------------------------
