# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from pydantic import ConfigDict

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel


class SettingsValue(BaseDocumentModel):
    """
    Model representing a specific settings value.

    This class defines a settings value that can be specific to a store and/or terminal.
    """

    store_code: Optional[str] = None  # Code identifying the store this setting applies to
    terminal_no: Optional[int] = None  # Terminal number this setting applies to
    value: str  # The actual setting value


class SettingsMasterDocument(AbstractDocument):
    """
    Document model representing system settings.

    This class defines the structure for storing configuration settings with
    default values and specific overrides for stores and terminals.
    """

    tenant_id: Optional[str] = None  # Identifier for the tenant
    name: Optional[str] = None  # Name of the setting
    default_value: Optional[str] = None  # Default value for the setting
    values: Optional[list[SettingsValue]] = None  # List of specific value overrides

    # Configuration for Pydantic model to use camelCase field names in JSON
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)
