# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic import BaseModel, ConfigDict
from typing import Generic, TypeVar
from datetime import datetime

from kugel_common.utils.misc import to_lower_camel


# Base Schema Model with camelCase JSON field conversion
class BaseSchemaModel(BaseModel):
    """
    Base schema model that all other schema models should inherit from.
    Converts snake_case Python fields to camelCase JSON fields for API consistency.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_lower_camel,
        json_encoder={datetime: lambda v: v.isoformat()} if "datetime" in locals() else None,
    )


# Generic type for use in generic models
T = TypeVar("T")


class BaseTenantCreateRequest(BaseSchemaModel):
    """
    Base schema for tenant creation request.

    Used to initialize a new tenant in the stock service.
    """

    tenant_id: str  # Tenant identifier to create


class BaseTenantCreateResponse(BaseSchemaModel):
    """
    Base schema for tenant creation response.

    Confirms the tenant was successfully created.
    """

    tenant_id: str  # Created tenant identifier
