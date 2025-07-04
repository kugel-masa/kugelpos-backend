# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Union
from app.api.common.schemas import *


class TranResponse(BaseTranResponse):
    """
    Transaction response model for API version 1.

    Extends the base transaction response model with version-specific fields
    if needed. Currently inherits all functionality from BaseTranResponse.
    Used to provide transaction confirmation information to clients.
    """

    pass


class SalesReportResponse(BaseSalesReportResponse):
    """
    Sales report response model for API version 1.

    Extends the base sales report response model with version-specific fields
    if needed. Currently inherits all functionality from BaseSalesReportResponse.
    Used to provide comprehensive sales data for terminals or stores.
    """

    pass


class TenantCreateRequest(BaseTenantCreateRequest):
    """
    Tenant creation request model for API version 1.

    Extends the base tenant creation request model with version-specific fields
    if needed. Currently inherits all functionality from BaseTenantCreateRequest.
    Used to initialize the report service for a new tenant.
    """

    pass


class TenantCreateResponse(BaseTenantCreateResponse):
    """
    Tenant creation response model for API version 1.

    Extends the base tenant creation response model with version-specific fields
    if needed. Currently inherits all functionality from BaseTenantCreateResponse.
    Confirms successful tenant initialization in the report service.
    """

    pass
