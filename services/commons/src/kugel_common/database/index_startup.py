# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Bring existing tenants up to the declared collections and indexes at startup.

## Why

`database_setup.execute()` ran only from `POST /api/v1/tenants`. A fixed or new
index declaration therefore never reached a tenant that already existed, and
nothing said so: a write keyed on a field whose index never arrived turns into a
collection scan per request. The stpos fork lost a dev environment for ten hours
to exactly that (`log_tran` keyed on `cart_id`, the index left behind).

## Why additive

Startup runs the same `execute()` inside ``additive_index_ensure()``: missing
indexes are created, nothing is dropped or changed in place, and what could not
be applied is logged rather than raised. A drop followed by a failed rebuild
would leave a collection with no unique index; an unattended start must never
open that window. Migrations that drop or change an index keep going through
`POST /api/v1/tenants`, which an operator runs knowingly.

## Which tenants

The service's own databases are listed and the tenant is read from the name
(``{DB_NAME_PREFIX}_{tenant_id}``). Only databases that already exist are
touched, so no tenant is created and no other service's data is reached. The
shared ``{DB_NAME_PREFIX}_commons`` database is not a tenant; `execute()`
already provisions it alongside each tenant.

## Never blocks startup

It runs as a background task. A tenant that fails is logged and the next one is
tried; the service keeps serving throughout.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from logging import getLogger

from kugel_common.database.database import additive_index_ensure, get_client_async

logger = getLogger(__name__)

# The suffix every service uses for its shared, tenant-less database.
COMMONS_SUFFIX = "commons"

# Strong references to the running tasks: the event loop keeps only a weak one,
# so an unreferenced task can be collected before it finishes.
_background_tasks: set = set()


def tenants_from_db_names(db_names: Iterable[str], db_name_prefix: str) -> list[str]:
    """
    Read tenant ids out of ``{prefix}_{tenant_id}`` database names.

    The separator is part of the match (``db_cartx_T1`` is no ``db_cart`` tenant).
    Tenant ids are free-form, so this relies on no service prefix being another
    one followed by ``_``; the defaults are not. The shared commons database is
    left out.

    Args:
        db_names: Database names on the server
        db_name_prefix: The service's ``DB_NAME_PREFIX``

    Returns:
        The tenant ids, sorted and de-duplicated
    """
    head = f"{db_name_prefix}_"
    found = set()
    for name in db_names:
        if not name.startswith(head):
            continue
        tenant_id = name[len(head) :]
        if tenant_id and tenant_id != COMMONS_SUFFIX:
            found.add(tenant_id)
    return sorted(found)


async def ensure_declared_indexes_async(
    *,
    service_name: str,
    db_name_prefix: str,
    execute: Callable[[str], Awaitable[None]],
    client_getter: Callable[[], Awaitable] | None = None,
) -> int:
    """
    Run the service's tenant setup, additively, over every existing tenant.

    Args:
        service_name: For the log lines
        db_name_prefix: The service's ``DB_NAME_PREFIX``
        execute: The service's ``database_setup.execute``
        client_getter: Replaceable in tests; defaults to the shared Mongo client

    Returns:
        The number of tenants whose setup completed
    """
    getter = client_getter or get_client_async
    try:
        client = await getter()
        db_names = await client.list_database_names()
    except Exception as e:  # noqa: BLE001 - startup self-repair must never fail the service
        logger.error(
            f"[{service_name}] Index ensure at startup skipped: could not list databases "
            f"({type(e).__name__}: {e}). Existing indexes are unchanged."
        )
        return 0

    tenants = tenants_from_db_names(db_names, db_name_prefix)
    if not tenants:
        logger.info(f"[{service_name}] Index ensure at startup: no {db_name_prefix}_<tenant> database yet")
        return 0

    done = 0
    for tenant_id in tenants:
        try:
            with additive_index_ensure():
                await execute(tenant_id)
            done += 1
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            # One tenant must not stop the others, and none may stop the service.
            logger.error(
                f"[{service_name}] Index ensure at startup failed for tenant {tenant_id} "
                f"({type(e).__name__}: {e}). The service keeps running; run "
                f"POST /api/v1/tenants for this tenant once the cause is resolved."
            )
    logger.info(f"[{service_name}] Index ensure at startup: additive setup done for {done}/{len(tenants)} tenant(s)")
    return done


def start_index_ensure_in_background(
    *,
    service_name: str,
    db_name_prefix: str,
    execute: Callable[[str], Awaitable[None]],
) -> asyncio.Task:
    """
    Schedule ``ensure_declared_indexes_async`` without holding up startup.

    Args:
        service_name: For the log lines
        db_name_prefix: The service's ``DB_NAME_PREFIX``
        execute: The service's ``database_setup.execute``

    Returns:
        The scheduled task
    """
    task = asyncio.create_task(
        ensure_declared_indexes_async(service_name=service_name, db_name_prefix=db_name_prefix, execute=execute),
        name=f"{service_name}-index-ensure",
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def stop_index_ensure_async() -> None:
    """
    Cancel a startup ensure that is still running, before the client is closed.

    Called from shutdown so a slow ensure ends quietly instead of failing against
    a closed connection. What it already created stays; the next start resumes.
    """
    tasks = [t for t in _background_tasks if not t.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
