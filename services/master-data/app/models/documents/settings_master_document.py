# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from enum import Enum

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from app.models.documents.abstract_document import AbstractDocument


class SettingsValue(BaseDocumentModel):
    """
    Represents a specific setting value with scope information.

    This class defines a setting value that can be scoped to different levels
    of the system hierarchy (global, store-specific, terminal-specific),
    allowing for hierarchical configuration management.
    """

    store_code: Optional[str] = None  # Store code for store-specific settings, or None for global settings
    terminal_no: Optional[int] = (
        None  # Terminal number for terminal-specific settings, or None for store-level/global settings
    )
    value: str  # The actual value of the setting in this scope


class SettingsMasterDocument(AbstractDocument):
    """
    Document class representing a system setting in the master data system.

    This class defines a named setting with a default value and a collection of
    scope-specific overrides. The hierarchical nature of settings allows for
    different values at global, store, and terminal levels, with more specific
    scopes taking precedence.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    name: Optional[str] = None  # Unique name identifying this setting
    default_value: Optional[str] = None  # Default value used when no specific override is found
    values: Optional[list[SettingsValue]] = None  # List of scope-specific setting values
