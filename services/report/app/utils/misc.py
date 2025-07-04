# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime
from app.config.settings import settings
import pytz


def get_app_time(datetime_param: datetime = None) -> datetime:
    """
    Get the current time in the application's timezone
    The timezone is set in the settings.py file
    """
    if datetime_param is not None:
        return datetime_param.astimezone(pytz.timezone(settings.TIMEZONE))
    else:
        return datetime.now(pytz.timezone(settings.TIMEZONE))


def to_lower_camel(string: str) -> str:
    """
    Convert a string to lower camel case
    This function is used to convert the field names in the documents to camel case
    The function is used in the Config class of the Pydantic models
    """
    leading_underscores = ""
    while string.startswith("_"):
        leading_underscores += "_"
        string = string[1:]

    words = string.split("_")
    camel_case_string = words[0] + "".join(word.capitalize() for word in words[1:])
    return leading_underscores + camel_case_string
