# Copyright 2026 masa@kugel
"""Seeding of terminal-facing settings at tenant setup (issue #174).

Since #166 the terminal derives its printed receipt number from the configured
range, so it has to be able to read that range. Services resolve a missing
setting from their own configuration, but that fallback is invisible over the
API - the endpoint answers 404 - so the values are seeded into the settings
master where a client can actually see them.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.documents.settings_master_document import SettingsMasterDocument
from app.database.database_setup import (
    TERMINAL_FACING_SETTING_NAMES,
    _shared_default,
    seed_terminal_facing_settings,
)


def _repository(existing=None):
    """Stand in for SettingsMasterRepository; records what would be created."""
    repository = MagicMock()
    repository.get_settings_by_name_async = AsyncMock(side_effect=lambda name: (existing or {}).get(name))
    repository.create_settings_async = AsyncMock()
    repository.created = repository.create_settings_async
    return repository


def _patch(repository):
    """Patch the db handle and the repository the seeding builds from it."""
    return (
        patch("app.database.database_setup.db_helper.get_db_async", AsyncMock(return_value=MagicMock())),
        patch("app.database.database_setup.SettingsMasterRepository", return_value=repository),
    )


class _patch_db:
    """Context manager applying both patches."""

    def __init__(self, repository):
        self._patches = _patch(repository)

    def __enter__(self):
        for p in self._patches:
            p.start()

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False


class TestSharedDefault:
    def test_reads_the_value_services_number_with(self):
        # Not restated in this service: it does not inherit AppSettings, and a
        # second copy would drift from the one cart actually uses.
        assert _shared_default("RECEIPT_NO_START_VALUE") == "111111"
        assert _shared_default("RECEIPT_NO_END_VALUE") == "999999"

    def test_follows_an_environment_override(self, monkeypatch):
        # A seeded record outranks a service's own setting, so seeding the
        # shipped default would silently revert a deployment that raised the
        # range by environment.
        monkeypatch.setenv("RECEIPT_NO_START_VALUE", "200000")
        assert _shared_default("RECEIPT_NO_START_VALUE") == "200000"

    def test_unknown_name_yields_nothing(self):
        assert _shared_default("NOT_A_SETTING") == ""


class TestSeeding:
    @pytest.mark.asyncio
    async def test_seeds_what_the_deployment_configured(self, monkeypatch):
        monkeypatch.setenv("RECEIPT_NO_END_VALUE", "300000")
        repository = _repository()
        with _patch_db(repository):
            await seed_terminal_facing_settings("T0001")

        seeded = {c.args[0].name: c.args[0].default_value for c in repository.created.call_args_list}
        assert seeded["RECEIPT_NO_END_VALUE"] == "300000"

    @pytest.mark.asyncio
    async def test_seeds_both_ends_of_the_range(self):
        repository = _repository()
        with _patch_db(repository):
            await seed_terminal_facing_settings("T0001")

        seeded = {c.args[0].name: c.args[0] for c in repository.created.call_args_list}
        assert set(seeded) == set(TERMINAL_FACING_SETTING_NAMES)
        assert seeded["RECEIPT_NO_START_VALUE"].default_value == "111111"
        assert seeded["RECEIPT_NO_END_VALUE"].default_value == "999999"

    @pytest.mark.asyncio
    async def test_goes_through_the_repository(self):
        # The repository stamps created_at (rendered as entry_datetime) and the
        # shard key; a hand-built document fails the list endpoint's response
        # validation.
        repository = _repository()
        with _patch_db(repository):
            await seed_terminal_facing_settings("T0001")

        doc = repository.created.call_args_list[0].args[0]
        assert isinstance(doc, SettingsMasterDocument)
        assert doc.values == []

    @pytest.mark.asyncio
    async def test_an_operators_value_is_never_overwritten(self):
        # Tenant setup is re-runnable - it is how index migrations reach existing
        # tenants - so seeding has to be insert-if-absent.
        existing = {
            "RECEIPT_NO_START_VALUE": SettingsMasterDocument(name="RECEIPT_NO_START_VALUE", default_value="500000")
        }
        repository = _repository(existing)
        with _patch_db(repository):
            await seed_terminal_facing_settings("T0001")

        assert [c.args[0].name for c in repository.created.call_args_list] == ["RECEIPT_NO_END_VALUE"]

    @pytest.mark.asyncio
    async def test_rerunning_setup_seeds_nothing_new(self):
        existing = {name: SettingsMasterDocument(name=name) for name in TERMINAL_FACING_SETTING_NAMES}
        repository = _repository(existing)
        with _patch_db(repository):
            await seed_terminal_facing_settings("T0001")

        repository.created.assert_not_awaited()


class TestFailureIsNotFatal:
    @pytest.mark.asyncio
    async def test_a_failing_resolver_does_not_fail_tenant_setup(self):
        # Resolving the value reads the environment, so it can fail too - and a
        # tenant that cannot be seeded must still be created.
        repository = _repository()
        with (
            _patch_db(repository),
            patch("app.database.database_setup._shared_default", side_effect=RuntimeError("bad .env")),
        ):
            await seed_terminal_facing_settings("T0001")  # must not raise

        repository.created.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_seed_does_not_fail_tenant_setup(self):
        # A tenant without its defaults still works: services fall back to their
        # own configuration. Failing setup over it would be worse.
        repository = _repository()
        repository.create_settings_async = AsyncMock(side_effect=RuntimeError("mongo is unhappy"))
        repository.created = repository.create_settings_async
        with _patch_db(repository):
            await seed_terminal_facing_settings("T0001")  # must not raise
