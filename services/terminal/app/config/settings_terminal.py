# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal Service Settings Module - Terminal Specific Settings

This module defines terminal-specific configuration settings for the Terminal service.
These settings are focused on terminal operations, message republishing, and other
terminal-specific functionalities.
"""

from pydantic_settings import BaseSettings


class TerminalSettings(BaseSettings):
    """
    Terminal-specific settings

    This class defines settings that are specific to terminal operations,
    including undelivered message republishing settings.
    """

    # Debugging configuration
    DEBUG: str = "false"  # Enable/disable debug mode ("true"/"false")
    DEBUG_PORT: int = 5678  # Port for debugpy remote debugging

    # Undelivered message republish settings
    UNDELIVERED_CHECK_INTERVAL_IN_MINUTES: int = 5  # How often to check for undelivered messages (in minutes)
    UNDELIVERED_CHECK_PERIOD_IN_HOURS: int = 24  # How far back to look for undelivered messages (in hours)
    UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES: int = (
        15  # How long to wait before failed undelivered messages (in minutes)
    )
