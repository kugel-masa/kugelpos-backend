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
from datetime import datetime
import pytz

from kugel_common.config.settings import settings

"""
Miscellaneous utility functions used across the application.

This module provides common helper functions for time handling, string formatting,
and other general-purpose operations required by multiple components.
"""

def get_app_time(datetime_param: datetime = None) -> datetime:
    """
    Get the current time or convert a datetime object to the application's timezone.
    
    The application timezone is defined in the settings.py configuration file.
    This function ensures all datetime operations use a consistent timezone.
    
    Args:
        datetime_param: Optional datetime object to convert. If None, current time is used.
        
    Returns:
        Datetime object in the application's timezone.
    """
    if datetime_param is not None:
        return datetime_param.astimezone(pytz.timezone(settings.TIMEZONE))
    else:
        return datetime.now(pytz.timezone(settings.TIMEZONE))

def get_app_time_str(datetime_param: datetime = None) -> str:
    """
    Get a formatted ISO timestamp string in the application's timezone.
    
    This function is useful for generating consistent timestamp strings for logs,
    database records, and API responses.
    
    Args:
        datetime_param: Optional datetime object to convert. If None, current time is used.
        
    Returns:
        ISO format string representation of the datetime in the application's timezone.
    """
    app_time = get_app_time(datetime_param=datetime_param)
    return app_time.isoformat()

def to_lower_camel(string: str) -> str:
    """
    Convert a snake_case string to lowerCamelCase format.
    
    This function preserves leading underscores and follows standard camelCase conventions.
    It is primarily used for field name conversion in Pydantic models to ensure
    JSON serialization produces camelCase property names consistent with API standards.
    
    Args:
        string: A snake_case string to convert to lowerCamelCase.
        
    Returns:
        The string converted to lowerCamelCase format.
    """
    leading_underscores = ''
    while string.startswith('_'):
        leading_underscores += '_'
        string = string[1:]
        
    words = string.split('_')
    camel_case_string = words[0] + ''.join(word.capitalize() for word in words[1:])
    return leading_underscores + camel_case_string
