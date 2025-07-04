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
from pydantic import BaseModel, ConfigDict
from typing import Optional, TypeVar
from datetime import datetime

from kugel_common.utils.misc import to_lower_camel

# Base Schema Model with camelCase JSON field conversion


class BaseSchemaModel(BaseModel):
    """
    Base schema model that all other schema models should inherit from.
    Converts snake_case Python fields to camelCase JSON fields for API consistency.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)


# Generic type for use in generic models
T = TypeVar("T")


# User account models
class BaseUserAccount(BaseSchemaModel):
    """
    Base model for user account creation requests.
    Contains the minimum required fields to create a new user.
    """

    username: str  # Username for authentication
    password: str  # Plain text password (will be hashed before storage)
    tenant_id: Optional[str] = None  # Optional tenant ID, can be auto-generated


class BaseUserAccountInDB(BaseUserAccount):
    """
    Extended user account model for database storage.
    Includes all user metadata and security information.
    """

    hashed_password: str  # BCrypt hashed password
    tenant_id: str  # Tenant identifier (not optional for stored users)
    is_superuser: bool = False  # Whether the user has administrative privileges
    is_active: bool = True  # Whether the account is active
    created_at: datetime  # When the account was created
    updated_at: Optional[datetime] = None  # When the account was last updated
    last_login: Optional[datetime] = None  # When the user last logged in


class BaseLoginResponse(BaseModel):  # Use BaseModel because no camelCase conversion needed
    """
    Response model for successful authentication.
    Contains the JWT token and its type for client authorization.
    """

    access_token: str  # JWT token for authentication
    token_type: str  # Token type (usually 'bearer')


# Sample model for demonstration/testing purposes
class BaseSample(BaseSchemaModel):
    """
    Example schema for demonstration purposes.
    Shows the typical fields that might be used in a resource model.
    """

    tenant_id: str  # Tenant identifier
    store_code: str  # Store identifier
    sample_id: str  # Unique sample identifier
    sample_name: str  # Display name of the sample
