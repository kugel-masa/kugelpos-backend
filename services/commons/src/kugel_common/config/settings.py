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
Settings configuration module

This module combines all specialized settings components into a single Settings class,
providing a unified configuration interface for the entire application. It leverages
Pydantic's settings management with environment variable support.
"""
from pydantic_settings import SettingsConfigDict

from kugel_common.config.settings_app import AppSettings
from kugel_common.config.settings_auth import AuthSettings
from kugel_common.config.settings_datetime import DatetimeSettings
from kugel_common.config.settings_tax import TaxSettings
from kugel_common.config.settings_stamp_duty import StampDutySettings
from kugel_common.config.settings_web import WebServiceSettings
from kugel_common.config.settings_database import DBCollectionCommonSettings, DBSettings

class Settings(
    AppSettings,
    DatetimeSettings,
    TaxSettings,
    StampDutySettings,
    AuthSettings,
    WebServiceSettings,
    DBCollectionCommonSettings,
    DBSettings
):
    """
    Combined settings class that inherits from all specific settings components.
    
    This class provides a single access point for all configuration settings,
    with values loaded from environment variables or .env files.
    Each specialized settings component handles a specific aspect of the application:
    
    - AppSettings: General application configuration
    - DatetimeSettings: Date and time formatting and timezone settings
    - TaxSettings: Tax calculation rules and rates
    - StampDutySettings: Stamp duty calculation settings
    - AuthSettings: Authentication and authorization settings
    - WebServiceSettings: Web service endpoints and connection parameters
    - DBCollectionCommonSettings: Database collection name standardization
    - DBSettings: Database connection and configuration
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,  # Ignore empty values from .env file
        extra="allow",  # Allow extra fields in the settings
    )

# Create a default settings instance for use within kugel_common
# Services should override this with their own settings instance
settings = Settings()