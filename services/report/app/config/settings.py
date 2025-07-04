# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any

from kugel_common.config.settings import (
    DBCollectionCommonSettings,
    DBSettings,
    AuthSettings,
    DatetimeSettings,
    WebServiceSettings,
)
from app.config.settings_database import DBCollectionSettings

"""
This is the settings module for the application environment settings.

if you want to add a new setting for user company or store or terminal,
please use the settings master
"""


class Settings(
    DBSettings, DBCollectionSettings, DBCollectionCommonSettings, DatetimeSettings, AuthSettings, WebServiceSettings
):
    # Override required fields with defaults
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_report")

    DEBUG: str = "false"
    DEBUG_PORT: int = 5678

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,  # Ignore empty values from .env file
        extra="allow",  # ← allow unknown fields
    )


settings = Settings()
