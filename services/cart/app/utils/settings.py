# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.config.settings import settings
from app.models.documents.settings_master_document import SettingsMasterDocument
from logging import getLogger

logger = getLogger(__name__)


def get_setting_value(name: str, store_code: str, terminal_no: int, setting: SettingsMasterDocument = None):
    """
    Get a setting value based on hierarchical fallback rules.

    This function tries to get the setting value from the settings dictionary.
    If it doesn't exist, it falls back to the settings module.

    Args:
        name: Setting name to retrieve
        store_code: Store code to match
        terminal_no: Terminal number to match
        setting: Settings master document to look up values in

    Returns:
        The value of the requested setting or None if not found
    """
    logger.debug(
        f"get_setting_value: name->{name}, store_code->{store_code}, terminal_no->{terminal_no}, setting->{setting}"
    )

    if setting is not None:
        # Try to find setting specific to this store and terminal
        value = next((v for v in setting.values if v.store_code == store_code and v.terminal_no == terminal_no), None)
        if value is not None:
            return value.value

        # Try to find setting specific to this store (any terminal)
        value = next((v for v in setting.values if v.store_code == store_code and v.terminal_no is None), None)
        if value is not None:
            return value.value

        # Try to find global setting (any store, any terminal)
        value = next((v for v in setting.values if v.store_code is None and v.terminal_no is None), None)
        if value is not None:
            return value.value

        # Fall back to default value defined in the settings document
        if setting.default_value is not None:
            return setting.default_value
    else:
        logger.debug("get_setting_value: get value from settings because db setting is None.")
        # Fall back to settings module default
        return getattr(settings, name, None)  # Use default value from settings_app.py
