# Copyright 2025 masa@kugel
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
MongoDB database utility module for async operations

This module provides a set of asynchronous utilities for interacting with MongoDB
using the Motor driver. It handles connection management, database and collection
operations, and provides unified error handling.
"""

# database.py
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from logging import getLogger
from typing import Optional, TypeVar, Callable
import asyncio
from functools import wraps
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from kugel_common.database.database_exceptions import DatabaseException
from kugel_common.config.settings import settings

# Get logger instance
logger = getLogger(__name__)

# Get MongoDB connection details from settings
MONGODB_URI: str = settings.MONGODB_URI

# Initialize global variables
client: AsyncIOMotorClient = None
_client_lock = asyncio.Lock()

# Type variable for generic return type
T = TypeVar("T")


def with_connection_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that handles connection errors and retries the operation
    after resetting the client connection.

    The number of retry attempts is controlled by the DB_CONNECTION_RETRY_COUNT
    setting (default: 1).

    Args:
        func: The async function to wrap

    Returns:
        The wrapped function with retry logic
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        last_exception = None
        retry_count = settings.DB_CONNECTION_RETRY_COUNT

        # Try once, then retry up to retry_count times
        for attempt in range(1 + retry_count):
            try:
                return await func(*args, **kwargs)
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                last_exception = e
                if attempt < retry_count:
                    logger.warning(
                        f"Connection error in {func.__name__} (attempt {attempt + 1}): {e}. Resetting client..."
                    )
                    await reset_client_async()
                    # Continue to next retry attempt
                else:
                    # Final attempt failed
                    error_context = f"{func.__name__}"
                    if args:
                        error_context += f" with args: {args[:2]}"  # Log first 2 args for context
                    message = f"Failed to execute {error_context} after {retry_count} retry attempt(s)"
                    raise DatabaseException(message, logger, e) from e
            except Exception as e:
                # Re-raise non-connection errors immediately
                raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    return wrapper


async def get_client_async() -> AsyncIOMotorClient:
    """
    Create and get MongoDB client instance asynchronously

    Creates a singleton client instance connecting to MongoDB or returns
    the existing client if already connected. Connection validation is
    done lazily when actual operations are performed.

    Returns:
        AsyncIOMotorClient: MongoDB client instance

    Raises:
        DatabaseException: If connection to MongoDB fails
    """
    global client
    async with _client_lock:
        if client is None:
            try:
                client = AsyncIOMotorClient(
                    # Connection string
                    host=MONGODB_URI,
                    # Connection pool management
                    maxPoolSize=settings.DB_MAX_POOL_SIZE,
                    minPoolSize=settings.DB_MIN_POOL_SIZE,
                    maxIdleTimeMS=settings.DB_MAX_IDLE_TIME_MS,
                    # Timeout settings
                    serverSelectionTimeoutMS=settings.DB_SERVER_SELECTION_TIMEOUT_MS,
                    connectTimeoutMS=settings.DB_CONNECT_TIMEOUT_MS,
                    socketTimeoutMS=settings.DB_SOCKET_TIMEOUT_MS,
                )
                # Initial connection test
                info = await client.server_info()
                logger.info(f"Connected to MongoDB {info}")
                logger.info(
                    f"Connection pool settings: maxPoolSize={settings.DB_MAX_POOL_SIZE}, "
                    f"minPoolSize={settings.DB_MIN_POOL_SIZE}, "
                    f"maxIdleTimeMS={settings.DB_MAX_IDLE_TIME_MS}"
                )
            except Exception as e:
                client = None
                message = f"Failed to connect to MongoDB: uri->{MONGODB_URI}"
                raise DatabaseException(message, logger, e) from e
        return client


async def close_client_async():
    """
    Close the MongoDB client connection asynchronously

    Properly closes the MongoDB client connection to release resources.

    Raises:
        DatabaseException: If closing the connection fails
    """
    global client
    try:
        if client is not None:
            client.close()
            logger.info("Database connection closed")
    except Exception as e:
        message = "Failed to close database connection"
        raise DatabaseException(message, logger, e) from e
    finally:
        client = None
        logger.info("MongoDB client set to None")


async def reset_client_async():
    """
    Reset the MongoDB client connection

    Closes the existing client connection and resets it to None,
    forcing a new connection to be created on the next access.
    """
    global client
    async with _client_lock:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            client = None
            logger.info("MongoDB client reset")


@with_connection_retry
async def get_db_async(db_name: str) -> AsyncIOMotorDatabase:
    """
    Get MongoDB database instance asynchronously

    Connects to a specific database using the MongoDB client.
    Automatically resets the client on connection errors.

    Args:
        db_name: Name of the database to connect to

    Returns:
        AsyncIOMotorDatabase: MongoDB database instance

    Raises:
        DatabaseException: If getting the database instance fails
    """
    try:
        client = await get_client_async()
        db = client[db_name]
        logger.info(f"Connected to database {db_name}")
        return db
    except Exception as e:
        message = f"Failed to get database: uri->{MONGODB_URI} db->{db_name}"
        raise DatabaseException(message, logger, e) from e


@with_connection_retry
async def check_db_exists_async(db_name: str) -> bool:
    """
    Check if a database exists asynchronously

    Args:
        db_name: Name of the database to check

    Returns:
        bool: True if the database exists, False otherwise

    Raises:
        DatabaseException: If checking for database existence fails
    """
    try:
        client = await get_client_async()
        db_list = await client.list_database_names()
        return db_name in db_list
    except Exception as e:
        message = f"Failed to check if database exists: {db_name}"
        raise DatabaseException(message, logger, e) from e


@with_connection_retry
async def drop_db_async(db_name: str) -> bool:
    """
    Drop a database asynchronously

    Completely removes a database and all its collections.

    Args:
        db_name: Name of the database to drop

    Returns:
        bool: True if the operation was successful

    Raises:
        DatabaseException: If dropping the database fails
    """
    try:
        client = await get_client_async()
        await client.drop_database(db_name)
        logger.info(f"Database {db_name} dropped")
        return True
    except Exception as e:
        message = f"Failed to drop database: {db_name}"
        raise DatabaseException(message, logger, e) from e


# How many colliding key values to name when a unique index cannot be built.
# Enough to see the shape of the problem; not so many that the message becomes
# the data dump it is describing.
BLOCKING_DUPLICATE_SAMPLE = 5

# Ceiling on the diagnostic aggregation. It runs on a collection with no usable
# index for the grouping - a full scan - and the collection it runs on is a
# production log that may hold millions of documents. Better to return a failure
# without the sample than to spend the database on explaining one.
BLOCKING_DUPLICATE_TIMEOUT_MS = 10_000


async def find_blocking_duplicates_async(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    index_keys: dict,
    partial_filter_expression: Optional[dict] = None,
    limit: int = BLOCKING_DUPLICATE_SAMPLE,
) -> list:
    """
    Key values that already appear more than once, and so block a unique index.

    Called when a required unique index turns out to be missing after the attempt
    to build it. Without this the caller can only say the build failed and guess
    at why; with it, the failure names the documents that have to be resolved.

    Best-effort by design: an aggregation that fails here must not replace the
    failure it was called to explain - including when it exceeds
    BLOCKING_DUPLICATE_TIMEOUT_MS on a collection too large to scan.

    Does not resolve a unique index on an array field: `$group` groups on the
    array as a value, while the index collides on the elements, so `[1, 2]` and
    `[2, 3]` read as distinct here and clash in the index. No unique index in
    this system is on an array field; if one is added, this needs `$unwind`.

    Args:
        db: Database instance
        collection_name: Collection the index belongs to
        index_keys: The index key specification, e.g. {"tenant_id": 1, ...}
        partial_filter_expression: The index's partial filter, when it has one -
            documents outside it are not indexed and so cannot be blocking
        limit: Maximum number of colliding key values to return

    Returns:
        List of {"_id": {...key values...}, "n": count}, most-duplicated first,
        or an empty list if nothing was found or the lookup itself failed
    """
    try:
        pipeline = []
        if partial_filter_expression:
            pipeline.append({"$match": partial_filter_expression})
        pipeline += [
            # A $group _id may not contain dots in its field names, and index
            # keys can be nested paths.
            {"$group": {"_id": {k.replace(".", "\uff0e"): f"${k}" for k in index_keys}, "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": limit},
        ]
        cursor = db[collection_name].aggregate(
            pipeline,
            allowDiskUse=True,
            maxTimeMS=BLOCKING_DUPLICATE_TIMEOUT_MS,
        )
        return await cursor.to_list(length=limit)
    except Exception as e:
        logger.warning(f"Could not identify the documents blocking an index on {collection_name}: {e}")
        return []


async def run_setup_steps_async(tenant_id: str, steps: list) -> None:
    """
    Run every setup step, then report all the failures rather than only the first.

    Stopping at the first failure is worse than it looks: the collections after it
    are never created either, so one blocked collection leaves the rest of the
    tenant unset up - and the operator learns about the blocked ones one restart
    at a time. Running them all leaves every healthy collection ready and names
    every blocked one at once (issue #185).

    A backend that cannot be reached is different in kind and still stops
    everything: the remaining steps would only fail the same way.

    Args:
        tenant_id: Passed to each step
        steps: Setup coroutine functions taking a single tenant_id argument

    Raises:
        DatabaseException: If any step failed, naming all of them
        ConnectionFailure / ServerSelectionTimeoutError: propagated immediately
    """
    failures = []
    for step in steps:
        try:
            await step(tenant_id)
        except (ConnectionFailure, ServerSelectionTimeoutError):
            raise
        except Exception as e:
            failures.append(str(e))
            logger.error(f"Tenant setup step {getattr(step, '__name__', step)} failed: {e}")

    if failures:
        raise DatabaseException(
            f"Tenant setup for {tenant_id} could not complete {len(failures)} of {len(steps)} steps: "
            + " | ".join(failures),
            logger,
        )


@with_connection_retry
async def create_collection_with_indexes_async(
    db_name: str,
    collection_name: str,
    index_keys_list: list,
    index_name: str,
    drop_indexes_by_keys: list = None,
):
    """
    Create a collection with specified indexes asynchronously

    Creates a new collection in the specified database and adds the specified
    indexes to optimize query performance.

    Args:
        db_name: Name of the database
        collection_name: Name of the collection to create
        index_keys_list: List of index specifications
        index_name: Base name for the indexes

    Raises:
        DatabaseException: If creating the collection or indexes fails
    """
    try:
        db = await get_db_async(db_name)
        created = await create_collection_async(collection_name=collection_name, db=db)
        if created:
            logger.info(f"Collection created: {collection_name}")

        # Migration support: drop stale indexes whose key pattern no longer
        # matches the desired set (matched by key pattern, not name, so it is
        # robust to naming). Used to retire a unique index whose key columns
        # changed (e.g. issue #156 reworked the tranlog/stock uniqueness).
        if drop_indexes_by_keys:
            try:
                existing = await db[collection_name].index_information()
                for drop_keys in drop_indexes_by_keys:
                    want = [(k, v) for k, v in drop_keys.items()]
                    for idx_name, info in existing.items():
                        if idx_name == "_id_":
                            continue
                        if [(k, v) for k, v in info.get("key", [])] == want:
                            await db[collection_name].drop_index(idx_name)
                            logger.info(f"Dropped stale index {idx_name} ({drop_keys}) on {collection_name}")
            except (ConnectionFailure, ServerSelectionTimeoutError):
                raise
            except Exception as e:  # best-effort migration; do not block startup
                logger.warning(f"Stale-index drop skipped on {collection_name}: {e}")

        # Ensure the desired indexes on BOTH new and existing collections
        # (createIndexes is idempotent for an identical name+spec). This is what
        # applies the issue #156 cart_id / business_counter indexes to already
        # existing tenant collections.
        index_name_org = index_name
        for index_info in index_keys_list:
            keys_dict = index_info.get("keys", {})
            unique = index_info.get("unique", False)
            partial_filter = index_info.get("partialFilterExpression")
            expire_after_seconds = index_info.get("expireAfterSeconds")
            idx_name = index_name_org + "_" + "_".join([str(key) for key in keys_dict.keys()])
            command_json = create_indexes_command(
                collection_name=collection_name,
                index_keys=keys_dict,
                index_name=idx_name,
                unique=unique,
                partial_filter_expression=partial_filter,
                expire_after_seconds=expire_after_seconds,
            )
            try:
                await execute_command_async(command=command_json, db=db)
            except (ConnectionFailure, ServerSelectionTimeoutError):
                raise
            except Exception as e:  # an already-present/conflicting index must not block startup
                logger.warning(f"Index {idx_name} ensure skipped on {collection_name}: {e}")

        # Migration verification (issue #156 / bug_007): on an EXISTING collection a
        # silently-skipped drop or ensure can leave a stale unique index that blocks
        # finalize inserts, or leave a newly-required unique index (e.g. the cart_id
        # dedupe) missing — both fail OPEN and look healthy. So verify the end-state
        # by index key pattern (name-agnostic) and hard-fail if it was not achieved.
        # New collections skip this: there is nothing to migrate and a brand-new
        # collection always reflects index_keys_list exactly.
        # Verified whether or not the collection was just created. A new
        # collection is expected to reflect index_keys_list exactly, but the
        # ensure loop above swallows its failures with a warning - so without
        # this, an index that never got built reports success (issue #185).
        final_info = await db[collection_name].index_information()
        # Grouped, not keyed: MongoDB lets a unique and a non-unique index share
        # a key pattern under different names, so collapsing them into a dict
        # keeps whichever came last and makes the check below order-dependent.
        by_keys = {}
        for info in final_info.values():
            by_keys.setdefault(tuple((k, v) for k, v in info.get("key", [])), []).append(info)
        present = list(by_keys)

        for index_info in index_keys_list:
            keys_dict = index_info.get("keys", {})
            want = tuple((k, v) for k, v in keys_dict.items())

            # An index with the right keys but the wrong options is the same
            # failure wearing a disguise: createIndexes refuses to change them
            # (IndexOptionsConflict), the ensure loop above logs a warning, and a
            # keys-only check then reports success over a constraint that is not
            # being enforced.
            if want in present and index_info.get("unique") and not any(i.get("unique") for i in by_keys[want]):
                # The keys are there and the uniqueness is not. Left to the check
                # below, this reads as satisfied - a constraint the system relies
                # on, reported as present while nothing enforces it.
                blocking = ""
                duplicates = await find_blocking_duplicates_async(
                    db, collection_name, keys_dict, index_info.get("partialFilterExpression")
                )
                if duplicates:
                    listed = "; ".join(f"{d.get('_id')} x{d.get('n')}" for d in duplicates)
                    blocking = f" Documents sharing this key (showing up to {BLOCKING_DUPLICATE_SAMPLE}): {listed}"
                raise DatabaseException(
                    f"Index {want} on {collection_name} exists but no index on those keys is unique, "
                    f"so the uniqueness relied on here is not enforced.{blocking}",
                    logger,
                )

            # A TTL whose retention changed is the one option `createIndexes`
            # will not update: it answers IndexOptionsConflict, the ensure loop
            # above logs a warning, and the keys-only check below then reports
            # success over the value the index was FIRST created with. An
            # operator who shortens retention because a disk is filling gets no
            # error and no effect (issue #221). `collMod` is the documented way
            # to change it in place, so it is issued here when the live value
            # differs from the declared one.
            wanted_ttl = index_info.get("expireAfterSeconds")
            if wanted_ttl is not None and want in present:
                for info in by_keys[want]:
                    live_ttl = info.get("expireAfterSeconds")
                    if live_ttl is not None and int(live_ttl) != int(wanted_ttl):
                        idx_name = next(
                            (n for n, i in final_info.items() if i is info),
                            None,
                        )
                        if idx_name is None:
                            continue
                        try:
                            await db.command(
                                {
                                    "collMod": collection_name,
                                    "index": {"name": idx_name, "expireAfterSeconds": int(wanted_ttl)},
                                }
                            )
                            logger.info(
                                f"Retention on {collection_name}.{idx_name} changed from {live_ttl}s to {wanted_ttl}s"
                            )
                        except (ConnectionFailure, ServerSelectionTimeoutError):
                            raise
                        except Exception as e:
                            # Not fatal: the collection still expires, at the old
                            # value. Said loudly because the setting the operator
                            # changed is not the one in force.
                            logger.error(
                                f"Retention on {collection_name}.{idx_name} is still {live_ttl}s; "
                                f"the declared {wanted_ttl}s could not be applied: {e}"
                            )

            if want not in present:
                # Say what is actually in the way. "Likely existing data
                # violates a new unique constraint" was a guess, and left the
                # operator with a collection name and nothing to act on.
                blocking = ""
                if index_info.get("unique"):
                    duplicates = await find_blocking_duplicates_async(
                        db, collection_name, keys_dict, index_info.get("partialFilterExpression")
                    )
                    if duplicates:
                        listed = "; ".join(f"{d.get('_id')} x{d.get('n')}" for d in duplicates)
                        blocking = (
                            f" Documents already in the collection share this key and have to be "
                            f"resolved before it can be built (showing up to "
                            f"{BLOCKING_DUPLICATE_SAMPLE}): {listed}"
                        )
                raise DatabaseException(
                    f"Required index {want} missing on {collection_name} after migration "
                    f"(index ensure failed).{blocking}",
                    logger,
                )

            if drop_indexes_by_keys:
                for drop_keys in drop_indexes_by_keys:
                    stale = tuple((k, v) for k, v in drop_keys.items())
                    if stale in present:
                        raise DatabaseException(
                            f"Stale index {stale} still present on {collection_name} after migration "
                            "(drop failed — it may block finalize inserts)",
                            logger,
                        )
    except (ConnectionFailure, ServerSelectionTimeoutError):
        # Re-raise so the @with_connection_retry decorator can retry the
        # whole operation (including re-acquiring the db handle).
        raise
    except Exception as e:
        message = f"Failed to create collection with indexes: {collection_name} in {db_name}. Error: {str(e)}"
        logger.error(f"Collection with indexes creation error: {type(e).__name__}: {str(e)}")
        raise DatabaseException(message, logger, e) from e


async def create_collection_async(collection_name: str, db: AsyncIOMotorDatabase):
    """
    Create a collection asynchronously

    Creates a new collection in the specified database if it doesn't already exist.

    Note: This function takes a `db` handle as input. On a connection error
    (AutoReconnect / ConnectionFailure), retrying here is unsafe because the
    caller's `db` handle becomes stale once the client is reset. We therefore
    re-raise ConnectionFailure so a caller decorated with
    @with_connection_retry can retry by re-acquiring the db handle.

    Args:
        collection_name: Name of the collection to create
        db: Database instance

    Returns:
        bool: True if collection was created, False if it already existed

    Raises:
        ConnectionFailure / ServerSelectionTimeoutError: propagated for retry by callers
        DatabaseException: If creating the collection fails for any other reason
    """
    try:
        if collection_name in await db.list_collection_names():
            logger.info(f"Collection {collection_name} already exists")
            return False  # return false if collection already exists
        await db.create_collection(collection_name)
        logger.info(f"Collection {collection_name} created")
    except (ConnectionFailure, ServerSelectionTimeoutError):
        raise
    except Exception as e:
        message = f"Failed to create collection: {collection_name}. Error: {str(e)}"
        logger.error(f"Collection creation error details: {type(e).__name__}: {str(e)}")
        raise DatabaseException(message, logger, e) from e
    return True


async def drop_collection_async(collection_name: str, db: AsyncIOMotorDatabase):
    """
    Drop a collection asynchronously

    Removes a collection from the database if it exists.

    Note: see `create_collection_async` — connection-error retry must happen
    in a caller that owns the db handle.

    Args:
        collection_name: Name of the collection to drop
        db: Database instance

    Returns:
        bool: True if the operation was successful

    Raises:
        ConnectionFailure / ServerSelectionTimeoutError: propagated for retry by callers
        DatabaseException: If dropping the collection fails for any other reason
    """
    try:
        if collection_name not in await db.list_collection_names():
            logger.info(f"Collection {collection_name} does not exist")
            return True
        await db.drop_collection(collection_name)
        logger.info(f"Collection {collection_name} dropped")
    except (ConnectionFailure, ServerSelectionTimeoutError):
        raise
    except Exception as e:
        message = f"Failed to drop collection: {collection_name}"
        raise DatabaseException(message, logger, e) from e
    return True


async def execute_command_async(command: dict, db: AsyncIOMotorDatabase):
    """
    Execute a MongoDB command asynchronously

    Executes an arbitrary MongoDB command against the specified database.

    Note: see `create_collection_async` — connection-error retry must happen
    in a caller that owns the db handle.

    Args:
        command: MongoDB command as a dictionary
        db: Database instance

    Returns:
        bool: True if the command was executed successfully

    Raises:
        ConnectionFailure / ServerSelectionTimeoutError: propagated for retry by callers
        DatabaseException: If executing the command fails for any other reason
    """
    logger.debug(f"Executing command: {command}")
    try:
        await db.command(command)
        logger.info(f"Command executed: {command}")
    except (ConnectionFailure, ServerSelectionTimeoutError):
        raise
    except Exception as e:
        message = f"Failed to execute command: {command}"
        raise DatabaseException(message, logger, e) from e
    return True


def create_indexes_command(
    collection_name: str,
    index_keys: dict,
    index_name: str,
    unique: Optional[bool] = None,
    partial_filter_expression: Optional[dict] = None,
    expire_after_seconds: Optional[int] = None,
):
    """
    Create a MongoDB command for creating indexes

    Generates a MongoDB command dictionary for creating indexes on a collection.

    Args:
        collection_name: Name of the collection
        index_keys: Dictionary of field names and index directions
        index_name: Name for the index
        unique: Whether the index should enforce uniqueness
        partial_filter_expression: Optional MongoDB partial-filter expression.
            When set together with `unique=True`, the uniqueness constraint
            applies only to documents matching the filter (e.g., only when
            an optional field is present). Useful when a unique key would
            otherwise collide on documents whose key fields are missing/null.
        expire_after_seconds: Optional TTL in seconds. When set, MongoDB treats
            the index as a TTL index and removes documents whose indexed datetime
            field is older than this many seconds. The index key must be a single
            field holding a BSON date; documents missing the field never expire.

    Returns:
        dict: MongoDB command for creating the specified indexes
    """
    indexes = []

    index = {
        "key": index_keys,
        "name": index_name,
    }

    if unique is not None:
        index["unique"] = unique

    if partial_filter_expression is not None:
        index["partialFilterExpression"] = partial_filter_expression

    if expire_after_seconds is not None:
        index["expireAfterSeconds"] = expire_after_seconds

    indexes.append(index)

    return {"createIndexes": collection_name, "indexes": indexes}


async def get_collection_async(collection_name: str, db: AsyncIOMotorDatabase):
    """
    Get a MongoDB collection instance asynchronously

    Args:
        collection_name: Name of the collection to retrieve
        db: Database instance

    Returns:
        AsyncIOMotorCollection: Collection instance

    Raises:
        DatabaseException: If getting the collection fails
    """
    try:
        return db[collection_name]
    except Exception as e:
        message = f"Failed to get collection: {collection_name}"
        raise DatabaseException(message, logger, e) from e


async def get_collection_names_async(db: AsyncIOMotorDatabase):
    """
    Get a list of collection names in a database asynchronously

    Args:
        db: Database instance

    Returns:
        list: List of collection names

    Raises:
        DatabaseException: If getting the collection names fails
    """
    try:
        return await db.list_collection_names()
    except Exception as e:
        message = f"Failed to get collection names"
        raise DatabaseException(message, logger, e) from e
