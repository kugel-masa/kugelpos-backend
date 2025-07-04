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
T = TypeVar('T')

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
                    logger.warning(f"Connection error in {func.__name__} (attempt {attempt + 1}): {e}. Resetting client...")
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
                logger.info(f"Connection pool settings: maxPoolSize={settings.DB_MAX_POOL_SIZE}, "
                           f"minPoolSize={settings.DB_MIN_POOL_SIZE}, "
                           f"maxIdleTimeMS={settings.DB_MAX_IDLE_TIME_MS}")
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

async def create_collection_with_indexes_async(
        db_name: str,
        collection_name: str, 
        index_keys_list: list, 
        index_name: str, 
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
            index_name_org = index_name
            for index_info in index_keys_list:
                keys_dict = index_info.get("keys", {})
                unique = index_info.get("unique", False)
                logger.info(f"keys_dict: {keys_dict}")
                index_name = index_name_org + "_" + "_".join([str(key) for key in keys_dict.keys()])
                logger.info(f"Creating index: {index_name} for collection: {collection_name}")
                command_json = create_indexes_command(
                    collection_name=collection_name, 
                    index_keys=keys_dict, 
                    index_name=index_name, 
                    unique=unique
                )
                await execute_command_async(command=command_json, db=db)
    except Exception as e:
        message = f"Failed to create collection with indexes: {collection_name} in {db_name}. Error: {str(e)}"
        logger.error(f"Collection with indexes creation error: {type(e).__name__}: {str(e)}")
        raise DatabaseException(message, logger, e) from e

async def create_collection_async(collection_name: str, db: AsyncIOMotorDatabase):
    """
    Create a collection asynchronously
    
    Creates a new collection in the specified database if it doesn't already exist.
    
    Args:
        collection_name: Name of the collection to create
        db: Database instance
        
    Returns:
        bool: True if collection was created, False if it already existed
        
    Raises:
        DatabaseException: If creating the collection fails
    """
    try:
        if collection_name in await db.list_collection_names():
            logger.info(f"Collection {collection_name} already exists")
            return False # return false if collection already exists
        await db.create_collection(collection_name)
        logger.info(f"Collection {collection_name} created")
    except Exception as e:
        message = f"Failed to create collection: {collection_name}. Error: {str(e)}"
        logger.error(f"Collection creation error details: {type(e).__name__}: {str(e)}")
        raise DatabaseException(message, logger, e) from e
    return True

async def drop_collection_async(collection_name: str, db: AsyncIOMotorDatabase):
    """
    Drop a collection asynchronously
    
    Removes a collection from the database if it exists.
    
    Args:
        collection_name: Name of the collection to drop
        db: Database instance
        
    Returns:
        bool: True if the operation was successful
        
    Raises:
        DatabaseException: If dropping the collection fails
    """
    try:
        if collection_name not in await db.list_collection_names():
            logger.info(f"Collection {collection_name} does not exist")
            return True
        await db.drop_collection(collection_name)
        logger.info(f"Collection {collection_name} dropped")
    except Exception as e:
        message = f"Failed to drop collection: {collection_name}"
        raise DatabaseException(message, logger, e) from e
    return True

async def execute_command_async(command: dict, db: AsyncIOMotorDatabase):
    """
    Execute a MongoDB command asynchronously
    
    Executes an arbitrary MongoDB command against the specified database.
    
    Args:
        command: MongoDB command as a dictionary
        db: Database instance
        
    Returns:
        bool: True if the command was executed successfully
        
    Raises:
        DatabaseException: If executing the command fails
    """
    logger.debug(f"Executing command: {command}")
    try:
        await db.command(command)
        logger.info(f"Command executed: {command}")
    except Exception as e:
        message = f"Failed to execute command: {command}"
        raise DatabaseException(message, logger, e) from e
    return True

def create_indexes_command(collection_name: str, index_keys: dict, index_name: str, unique: Optional[bool] = None):
    """
    Create a MongoDB command for creating indexes
    
    Generates a MongoDB command dictionary for creating indexes on a collection.
    
    Args:
        collection_name: Name of the collection
        index_keys: Dictionary of field names and index directions
        index_name: Name for the index
        unique: Whether the index should enforce uniqueness
        
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

    indexes.append(index)

    return {
        "createIndexes": collection_name,
        "indexes": indexes
    }

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
