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
Date and time configuration settings

This module defines settings for timezone and date/time formatting used consistently
throughout the application for display and storage of temporal data.
"""
from pydantic_settings import BaseSettings

class DatetimeSettings(BaseSettings):
    """
    Date and time settings class
    
    Contains configuration for time zone and date/time format strings used for
    consistent handling of temporal data across the application.
    
    Attributes:
        TIMEZONE: Default timezone for the application (e.g., "Asia/Tokyo")
        DATE_FORMAT: Format string for date-only representations
        TIME_FORMAT: Format string for time-only representations
        DATETIME_FORMAT: Combined format string for complete date and time
    """
    TIMEZONE: str = "Asia/Tokyo"
    DATE_FORMAT: str = "%Y-%m-%d"
    TIME_FORMAT: str = "%H:%M:%S"
    DATETIME_FORMAT: str = f"{DATE_FORMAT} {TIME_FORMAT}"