# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal Service Settings Module

This module defines configuration settings for the Terminal service using Pydantic.
It consolidates various configuration aspects including web service settings,
database settings, date/time formats, and authentication parameters.

The settings are loaded from environment variables and/or .env files at runtime.
"""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from kugel_common.config.settings_web import WebServiceSettings
from kugel_common.config.settings_database import DBSettings
from kugel_common.config.settings_database import DBCollectionCommonSettings
from kugel_common.config.settings_datetime import DatetimeSettings
from kugel_common.config.settings_auth import AuthSettings
from app.config.settings_database import DBCollectionSettings
from app.config.settings_terminal import TerminalSettings


class Settings(
    WebServiceSettings,
    DBSettings,
    DBCollectionSettings,
    DBCollectionCommonSettings,
    DatetimeSettings,
    AuthSettings,
    TerminalSettings,
):
    """
    Terminal Service Settings

    This class combines multiple setting base classes to provide a comprehensive
    configuration for the Terminal service. It includes:

    - WebServiceSettings: Web server configuration (host, port, etc.)
    - DBSettings: Database connection parameters
    - DBCollectionSettings: Terminal-specific collection names
    - DBCollectionCommonSettings: Common collection names across services    - DatetimeSettings: Date and time format configuration
    - AuthSettings: Authentication and security parameters
    - TerminalSettings: Terminal-specific configurations

    Additionally, it defines Terminal-specific settings like debugging options.

    Note: For tenant, store, or terminal specific settings, use the settings master
    rather than adding them here.
    """

    # Override required fields with defaults
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_terminal")

    model_config = SettingsConfigDict(
        env_file=".env",  # Load settings from .env file
        env_ignore_empty=True,  # Ignore empty values from .env file
        extra="allow",  # Allow extra fields in the settings
    )


# Create a singleton instance of the settings
settings = Settings()
