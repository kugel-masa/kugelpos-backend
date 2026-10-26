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
from kugel_common.config.settings_dapr_app_token import DaprAppTokenSettings
from kugel_common.config.settings_http import HttpRequestSettings
from app.config.settings_database import DBCollectionSettings

"""
This is the settings module for the application environment settings.

if you want to add a new setting for user company or store or terminal,
please use the settings master
"""


class Settings(
    DBSettings,
    DBCollectionSettings,
    DBCollectionCommonSettings,
    DatetimeSettings,
    AuthSettings,
    DaprAppTokenSettings,
    WebServiceSettings,
    HttpRequestSettings,
):
    # The Dapr pub/sub tranlog subscriber is served by this same app, and the
    # body ceiling runs ahead of it (issue #195). A refused event is retried and
    # then dead-lettered, so a ceiling set too low loses the sale silently. A
    # measured 999-line transaction publishes a 552 KB tranlog; 4 MB leaves room
    # for several times that.
    MAX_REQUEST_BODY_BYTES: int = Field(default=4 * 1024 * 1024)

    # Override required fields with defaults
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_report")

    # How long an event_id is remembered as processed (issue #230). It has to
    # outlive every window in which the same event_id can arrive again: the
    # broker's redelivery (about 16-24 minutes, dapr/components/pubsub-resiliency.yaml)
    # and, much longer, the publisher's republish job, which re-sends the stored
    # event under its original event_id for UNDELIVERED_CHECK_PERIOD_IN_HOURS
    # (24 h in cart and terminal). The statestore component's own default
    # (ttlInSeconds, 1 h) was shorter than that.
    EVENT_IDEMPOTENCY_TTL_SECONDS: int = Field(default=48 * 60 * 60, gt=0)

    DEBUG: str = "false"
    DEBUG_PORT: int = 5678

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,  # Ignore empty values from .env file
        extra="allow",  # ← allow unknown fields
    )


settings = Settings()
