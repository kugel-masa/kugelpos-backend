# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.config.settings import settings
from logging import getLogger

from kugel_common.config.settings_app import AppSettings
from kugel_common.database import database as db_helper

from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.repositories.settings_master_repository import SettingsMasterRepository

# setup logger
logger = getLogger(__name__)


# create some collection
async def create_some_collection(
    tenant_id: str,
    collection_name: str,
    index_keys_list: list,
    index_name: str,
    drop_indexes_by_keys: list = None,
):
    # `None` addresses the shared commons database, the convention cart and
    # terminal already used for the collections written there (issue #221).
    # Without this it produced a database literally named "<prefix>_None",
    # which nothing reads and nothing would ever have noticed.
    db_name = f"{settings.DB_NAME_PREFIX}_commons" if tenant_id is None else f"{settings.DB_NAME_PREFIX}_{tenant_id}"
    await db_helper.create_collection_with_indexes_async(
        db_name=db_name,
        collection_name=collection_name,
        index_keys_list=index_keys_list,
        index_name=index_name,
        drop_indexes_by_keys=drop_indexes_by_keys,
    )


# create master item common collection
async def create_master_item_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_ITEM_COMMON_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "item_code": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master item store collection
async def create_master_item_store_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_ITEM_STORE_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "store_code": 1, "item_code": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master item book collection
async def create_master_item_book_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_ITEM_BOOK_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "item_book_id": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master category collection
async def create_master_category_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_CATEGORY_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "category_code": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master payment collection
async def create_master_payment_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_PAYMENT_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "payment_code": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master settings collection
async def create_master_settings_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_SETTINGS_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "name": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master staff collection
async def create_master_staff_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_STAFF_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "id": 1}, "unique": True},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create master promotion collection
async def create_master_promotion_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_PROMOTION_MASTER
    index_keys_list = [
        {"keys": {"tenant_id": 1, "promotion_code": 1}, "unique": True},
        {"keys": {"tenant_id": 1, "promotion_type": 1, "is_active": 1}, "unique": False},
        {"keys": {"tenant_id": 1, "is_active": 1, "start_datetime": 1, "end_datetime": 1}, "unique": False},
    ]
    await create_some_collection(
        tenant_id=tenant_id, collection_name=name, index_keys_list=index_keys_list, index_name=name + "_index"
    )


# create request log collection
async def create_request_log_collection(tenant_id: str):
    name = settings.DB_COLLECTION_NAME_REQUEST_LOG
    index_key_list = [
        # Issue #182: the key columns were `store_code` and `terminal_no` at the
        # top level, where a request log document does not have them - they live
        # under `terminal_info`. So the index resolved to
        # (tenant_id, null, null, accept_time) and the constraint it enforced was
        # one request per tenant per timestamp, never the per-terminal separation
        # it was written for.
        #
        # Corrected to the paths that exist, and no longer unique. What a unique
        # index here could protect against - the same request written twice - does
        # not happen: insert_many stamps `_id` into the documents in place, so a
        # retried batch is refused by `_id` (issue #183). What it did do was
        # reject audit records that legitimately happened, silently; measured at
        # 66 rows across this environment.
        {
            "keys": {
                "tenant_id": 1,
                "terminal_info.store_code": 1,
                "terminal_info.terminal_no": 1,
                "request_info.accept_time": 1,
            },
            "unique": False,
        },
    ]
    # Retention (issue #221). Nothing in this tree reads the request log and
    # nothing removed one either: measured downstream at 6.4M documents /
    # 23.8 GiB, 97% of the database, on a store PC. Keyed on `created_at` alone -
    # deliberately a different key pattern from the index(es) above, because
    # MongoDB will not swap options on an existing key pattern, and
    # `request_info.accept_time` is a string, which a TTL never expires.
    #
    # Declared only when retention is positive: `expireAfterSeconds: 0` is not
    # "no expiry" to MongoDB, it means "expire AT the stored date", which would
    # delete each request log almost as soon as it is written. 0 therefore means
    # "do not declare it" - an index already created stays until it is dropped by
    # hand, which is the conservative direction for a switch that only ever
    # removes data.
    if settings.REQUEST_LOG_TTL_SECONDS > 0:
        index_key_list.append(
            {
                "keys": {"created_at": 1},
                "unique": False,
                "expireAfterSeconds": settings.REQUEST_LOG_TTL_SECONDS,
            }
        )
    # Both copies (issue #221). The buffer writes every request log twice - to the
    # tenant database and to `{prefix}_commons` - but provisioning only ever ran
    # for the tenant, so the commons copy had no index at all beyond `_id_`, and
    # no way to shrink, while receiving exactly the same volume. `tenant_id=None`
    # is how create_some_collection addresses the commons database.
    for target in (tenant_id, None):
        # Pre-#221 documents carry no date, and a TTL index never expires those.
        # Before the index, so the rows the index exists for are already covered
        # by the time it starts running - and only when there is an index to
        # cover them for. With retention off the pass would walk the whole
        # collection to prepare for an expiry that is never declared.
        if settings.REQUEST_LOG_TTL_SECONDS > 0:
            await db_helper.backfill_created_at_from_id_async(
                db_name=(
                    f"{settings.DB_NAME_PREFIX}_commons"
                    if target is None
                    else f"{settings.DB_NAME_PREFIX}_{target}"
                ),
                collection_name=name,
            )
        await create_some_collection(
            tenant_id=target,
            collection_name=name,
            index_keys_list=index_key_list,
            index_name=name + "_index",
            # Retire the index keyed on fields that do not exist (issue #182).
            drop_indexes_by_keys=[{"tenant_id": 1, "store_code": 1, "terminal_no": 1, "request_info.accept_time": 1}],
        )


# create all collections
async def create_collections(tenant_id: str):
    """Create every collection this service needs for a tenant.

    Through run_setup_steps_async so that one blocked collection does not stop
    the rest from being created, and so a failure names every blocked collection
    at once rather than one restart at a time (issue #185).
    """
    await db_helper.run_setup_steps_async(
        tenant_id,
        [
            create_master_item_collection,
            create_master_item_store_collection,
            create_master_item_book_collection,
            create_master_category_collection,
            create_master_payment_collection,
            create_master_settings_collection,
            create_master_staff_collection,
            create_request_log_collection,
            create_master_promotion_collection,
        ],
    )


# Settings a POS terminal must be able to read, seeded so the documented lookup
# (GET /tenants/{tenant_id}/settings/{name}/value) can answer for them (issue
# #174). Services resolve a missing setting from their own configuration, but
# that fallback is invisible over the API - and since #166 the terminal derives
# the printed receipt number from this range itself, so it has to be able to
# read the same values the backend uses.
# Read from commons rather than restated here: this service does not inherit
# AppSettings, and a second copy of the value would drift from the one the
# services actually number with.
TERMINAL_FACING_SETTING_NAMES = ("RECEIPT_NO_START_VALUE", "RECEIPT_NO_END_VALUE")


def _shared_default(name: str, resolved: AppSettings = None) -> str:
    """
    The value a service would fall back to for `name`, as a string.

    Resolved the way a service resolves its own configuration - environment
    first, then `.env` - not from the class default. A deployment that raises
    the receipt range by environment would otherwise be silently reverted: the
    seeded record outranks a service's own setting, so seeding the shipped
    default would take precedence over the configured one. Set the variable for
    this service too, or configure the tenant setting directly.

    Args:
        name: Setting name defined on kugel_common's AppSettings
        resolved: An already-resolved AppSettings, so a caller seeding several
            names does not rebuild it for each one

    Returns:
        The resolved value rendered as the string the settings master stores,
        or "" when the name is not an AppSettings field
    """
    if name not in AppSettings.model_fields:
        return ""
    if resolved is None:
        resolved = AppSettings(_env_file=".env")
    value = getattr(resolved, name, None)
    return "" if value is None else str(value)


async def seed_terminal_facing_settings(tenant_id: str):
    """
    Insert the terminal-facing settings a tenant does not already have.

    Insert-if-absent: tenant setup is re-runnable (it is how index migrations
    reach existing tenants), and an operator's own value must never be
    overwritten by a default.

    Args:
        tenant_id: Tenant to seed

    Returns:
        None
    """
    db_name = f"{settings.DB_NAME_PREFIX}_{tenant_id}"
    db = await db_helper.get_db_async(db_name)
    # Through the repository, not a raw insert: it stamps the fields the rest of
    # the service expects (created_at, which the response schema renders as
    # entry_datetime, and the shard key). A hand-built document listed fine in
    # Mongo and then failed the settings-list endpoint's response validation.
    repository = SettingsMasterRepository(db, tenant_id)

    try:
        # Resolved once for the whole run; reading the environment can fail, and
        # a tenant that cannot be seeded must still be created.
        resolved = AppSettings(_env_file=".env")
    except Exception as e:
        logger.warning(f"Could not resolve shared settings for tenant_id:{tenant_id}: {e}")
        return

    for name in TERMINAL_FACING_SETTING_NAMES:
        try:
            default_value = _shared_default(name, resolved)
            if not default_value:
                logger.warning(f"No shared default for setting {name}; not seeding it")
                continue
            if await repository.get_settings_by_name_async(name) is not None:
                continue
            await repository.create_settings_async(
                SettingsMasterDocument(name=name, default_value=default_value, values=[])
            )
            # Say where the value came from: a deployment that overrides the range
            # for one service and not this one gets the shipped default seeded, and
            # the seeded record then outranks the service's own setting.
            source = (
                "environment" if default_value != str(AppSettings.model_fields[name].default) else "shipped default"
            )
            logger.info(f"Seeded setting {name}={default_value} ({source}) for tenant_id:{tenant_id}")
        except Exception as e:
            # A tenant without its defaults still works (services fall back to
            # their own configuration); failing setup over it would be worse.
            logger.warning(f"Could not seed setting {name} for tenant_id:{tenant_id}: {e}")


# setup database
async def execute(tenant_id: str):
    logger.info(f"Setting up database for tenant_id:{tenant_id} execution started...")
    await create_collections(tenant_id)
    await seed_terminal_facing_settings(tenant_id)
    # add more setup tasks here
