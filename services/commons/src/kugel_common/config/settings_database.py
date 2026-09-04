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
Database configuration settings

This module defines database connection settings and standardized collection names
used across the application for consistent data access.
"""
from pydantic_settings import BaseSettings

class DBSettings(BaseSettings):
    """
    Database connection settings class
    
    Contains configuration for MongoDB connection including URI and database naming.
    
    Attributes:
        MONGODB_URI: MongoDB connection string URI
        DB_NAME_PREFIX: Prefix used for all database names (e.g., "kugelpos")
        DB_CONNECTION_RETRY_COUNT: Number of retry attempts for database connection errors (default: 1)
        DB_MAX_POOL_SIZE: Maximum number of connections in the pool (default: 100)
        DB_MIN_POOL_SIZE: Minimum number of connections in the pool (default: 10)
        DB_MAX_IDLE_TIME_MS: Maximum idle time in milliseconds before closing a connection (default: 120000)
        DB_SERVER_SELECTION_TIMEOUT_MS: Server selection timeout in milliseconds (default: 5000)
        DB_CONNECT_TIMEOUT_MS: Connection timeout in milliseconds (default: 10000)
        DB_SOCKET_TIMEOUT_MS: Socket operation timeout in milliseconds (default: 30000)
    """
    MONGODB_URI: str = "mongodb://localhost:27017/?replicaSet=rs0"
    DB_NAME_PREFIX: str = "db_common"
    DB_CONNECTION_RETRY_COUNT: int = 1
    DB_MAX_POOL_SIZE: int = 100
    DB_MIN_POOL_SIZE: int = 10
    DB_MAX_IDLE_TIME_MS: int = 120000
    DB_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    DB_CONNECT_TIMEOUT_MS: int = 10000
    DB_SOCKET_TIMEOUT_MS: int = 30000

class DBCollectionCommonSettings(BaseSettings):
    """
    Common database collection names settings class
    
    Standardizes collection names used across the application to ensure
    consistent data storage and retrieval patterns.
    
    Attributes:
        DB_COLLECTION_NAME_REQUEST_LOG: Collection name for API request logs
        DB_COLLECTION_NAME_TERMINAL_INFO: Collection name for terminal information
        REQUEST_LOG_TTL_SECONDS: How long a request log is kept before MongoDB
            removes it (issue #221)
    """
    DB_COLLECTION_NAME_REQUEST_LOG: str = "log_request"
    DB_COLLECTION_NAME_TERMINAL_INFO: str = "info_terminal"
    # Request-log retention (issue #221). Every request writes a document, to the
    # tenant database AND to commons, and until now nothing ever removed one:
    # measured downstream at 6.4M documents / 23.8 GiB, 97% of the database, on a
    # store PC where there is nowhere for that to go. The volume itself slowed
    # checkout down.
    #
    # 30 days by default. The collection has no reader in the tree - it is an
    # audit trail somebody queries out of band - so retention is a disk decision,
    # not a correctness one. Raise it where the disk allows and the audit window
    # needs it; 0 turns expiry off and restores the old unbounded behaviour.
    # The downstream fork runs 7 days on store hardware, where the disk is the
    # binding constraint; upstream also serves server deployments, so the longer
    # window is the default here and the difference is deliberate.
    #
    # Changing this on a live deployment DOES take effect: the index is modified
    # in place (collMod) rather than silently keeping the value it was created
    # with - see create_collection_with_indexes_async.
    REQUEST_LOG_TTL_SECONDS: int = 30 * 24 * 60 * 60