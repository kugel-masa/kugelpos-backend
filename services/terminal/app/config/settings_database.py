# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal Service Database Collection Settings Module

This module defines the collection names used by the Terminal service in MongoDB.
These settings are used to ensure consistent naming across the application.
"""

from pydantic_settings import BaseSettings


class DBCollectionSettings(BaseSettings):
    """
    Terminal Service Collection Names

    This class defines the MongoDB collection names specific to the Terminal service.
    These collection names are used when creating database structures and when
    performing database operations throughout the application.
    """

    DB_COLLECTION_NAME_TENANT_INFO: str = "info_tenant"  # Collection for tenant information
    DB_COLLECTION_NAME_CASH_IN_OUT_LOG: str = "log_cash_in_out"  # Collection for cash drawer transaction logs
    DB_COLLECTION_NAME_OPEN_CLOSE_LOG: str = "log_open_close"  # Collection for terminal opening/closing logs
    DB_COLLECTION_NAME_TERMINALLOG_DELIVERY_STATUS: str = (
        "status_terminal_delivery"  # Collection for terminal log delivery status
    )
