# Copyright 2026 masa@kugel
"""Startup self-repair: existing tenants are brought up to the declared indexes.

Tenant setup used to run only from POST /tenants, so a new index never reached a
tenant that already existed. Each service now runs its setup at startup, in the
background and inside ``additive_index_ensure()``.
"""

import asyncio

import pytest

from kugel_common.database import database as db_helper
from kugel_common.database.index_startup import (
    ensure_declared_indexes_async,
    start_index_ensure_in_background,
    stop_index_ensure_async,
    tenants_from_db_names,
)


class TestTenantsFromDbNames:
    def test_tenants_are_read_from_the_service_prefix(self):
        names = ["db_cart_T0001", "db_cart_T0002", "admin", "db_report_T0001"]
        assert tenants_from_db_names(names, "db_cart") == ["T0001", "T0002"]

    def test_the_shared_commons_database_is_not_a_tenant(self):
        # execute() already provisions it alongside every tenant.
        assert tenants_from_db_names(["db_cart_commons", "db_cart_T1"], "db_cart") == ["T1"]

    def test_the_separator_is_part_of_the_match(self):
        # db_cartx_T1 belongs to no "db_cart" tenant.
        assert tenants_from_db_names(["db_cartx_T1", "db_cart_T2"], "db_cart") == ["T2"]

    def test_the_default_prefixes_do_not_overlap(self):
        # Tenant ids are free-form, so a prefix that is itself the start of
        # another followed by "_" (db_master / db_master_data) could not be told
        # apart. None of the services' defaults is.
        prefixes = ["db_account", "db_terminal", "db_master_data", "db_cart", "db_report", "db_journal", "db_stock"]
        for a in prefixes:
            for b in prefixes:
                if a != b:
                    assert not b.startswith(f"{a}_"), f"{b} would be read as a {a} tenant"

    def test_the_bare_prefix_is_not_a_tenant(self):
        assert tenants_from_db_names(["db_cart_", "db_cart"], "db_cart") == []


class _Client:
    def __init__(self, names=None, error=None):
        self._names = names or []
        self._error = error

    async def list_database_names(self):
        if self._error:
            raise self._error
        return self._names


def _getter(client):
    async def get():
        return client

    return get


class TestEnsure:
    @pytest.mark.asyncio
    async def test_every_tenant_is_set_up_inside_the_additive_context(self):
        seen = []

        async def execute(tenant_id):
            seen.append((tenant_id, db_helper.is_additive_index_ensure()))

        done = await ensure_declared_indexes_async(
            service_name="cart",
            db_name_prefix="db_cart",
            execute=execute,
            client_getter=_getter(_Client(["db_cart_T1", "db_cart_T2", "db_cart_commons"])),
        )

        assert done == 2
        assert seen == [("T1", True), ("T2", True)]
        # The context does not leak past the ensure.
        assert db_helper.is_additive_index_ensure() is False

    @pytest.mark.asyncio
    async def test_one_failing_tenant_does_not_stop_the_others(self, caplog):
        seen = []

        async def execute(tenant_id):
            if tenant_id == "T1":
                raise RuntimeError("duplicates in the way")
            seen.append(tenant_id)

        with caplog.at_level("ERROR"):
            done = await ensure_declared_indexes_async(
                service_name="cart",
                db_name_prefix="db_cart",
                execute=execute,
                client_getter=_getter(_Client(["db_cart_T1", "db_cart_T2"])),
            )

        assert done == 1
        assert seen == ["T2"]
        assert "T1" in caplog.text and "POST /api/v1/tenants" in caplog.text

    @pytest.mark.asyncio
    async def test_an_unreachable_server_is_logged_not_raised(self, caplog):
        async def execute(tenant_id):
            raise AssertionError("must not run")

        with caplog.at_level("ERROR"):
            done = await ensure_declared_indexes_async(
                service_name="cart",
                db_name_prefix="db_cart",
                execute=execute,
                client_getter=_getter(_Client(error=ConnectionError("down"))),
            )

        assert done == 0
        assert "could not list databases" in caplog.text

    @pytest.mark.asyncio
    async def test_no_tenant_yet_is_nothing_to_do(self):
        async def execute(tenant_id):
            raise AssertionError("must not run")

        done = await ensure_declared_indexes_async(
            service_name="cart",
            db_name_prefix="db_cart",
            execute=execute,
            client_getter=_getter(_Client(["admin", "local"])),
        )
        assert done == 0


class TestBackground:
    @pytest.mark.asyncio
    async def test_startup_is_not_held_up_and_shutdown_cancels(self, monkeypatch):
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_ensure(**kwargs):
            started.set()
            await release.wait()

        monkeypatch.setattr("kugel_common.database.index_startup.ensure_declared_indexes_async", slow_ensure)

        async def execute(tenant_id):
            pass

        task = start_index_ensure_in_background(service_name="cart", db_name_prefix="db_cart", execute=execute)
        await asyncio.wait_for(started.wait(), timeout=1)
        assert not task.done(), "the ensure has to run alongside startup, not before it"

        await stop_index_ensure_async()

        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_stopping_with_nothing_running_is_harmless(self):
        await stop_index_ensure_async()
