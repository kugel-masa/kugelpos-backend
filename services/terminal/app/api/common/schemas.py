# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, TypeVar
from pydantic import BaseModel, ConfigDict

from kugel_common.utils.misc import to_lower_camel

T = TypeVar("T")

# Base Schema Model


class BaseSchemmaModel(BaseModel):
    """
    Base Schema Model

    The foundation class for all API schema models in the terminal service.
    Provides configuration for JSON serialization in camelCase format.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)


#  # for Tenant  #
# store
class BaseStore(BaseSchemmaModel):
    """
    Base Store Information Model

    Represents store information in API responses.
    Contains store code, name, status, business date and other essential store details.
    """

    store_code: str
    store_name: str
    status: Optional[str] = None
    business_date: Optional[str] = None
    tags: Optional[list[str]] = None
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseStoreCreateRequest(BaseSchemmaModel):
    """
    Store Creation Request Model

    Used for API requests to create a new store.
    """

    store_code: str
    store_name: str
    status: Optional[str] = None
    business_date: Optional[str] = None
    tags: Optional[list[str]] = None


class BaseStoreUpdateRequest(BaseSchemmaModel):
    """
    Store Update Request Model

    Used for API requests to update an existing store's information.
    """

    store_name: str
    status: Optional[str] = None
    business_date: Optional[str] = None
    tags: Optional[list[str]] = None


class BaseStoreDeleteResponse(BaseSchemmaModel):
    """
    Store Deletion Response Model

    Used for API responses when deleting a store.
    """

    store_code: str


# tenant
class BaseTenant(BaseSchemmaModel):
    """
    Base Tenant Information Model

    Represents tenant information in API responses.
    Contains tenant ID, name, list of stores, and creation timestamps.
    """

    tenant_id: str
    tenant_name: str
    tags: list[str]
    stores: list[BaseStore]
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseTenantCreateReqest(BaseSchemmaModel):
    """
    Tenant Creation Request Model

    Used for API requests to create a new tenant.
    """

    tenant_id: str
    tenant_name: str
    tags: list[str]


class BaseTenantUpdateRequest(BaseSchemmaModel):
    """
    Tenant Update Request Model

    Used for API requests to update an existing tenant's information.
    """

    tenant_name: str
    tags: list[str]


class BaseTenantDeleteResponse(BaseSchemmaModel):
    """
    Tenant Deletion Response Model

    Used for API responses when deleting a tenant.
    """

    tenant_id: str


#  # for Terminal  #
# staff
class BaseStaff(BaseSchemmaModel):
    """
    Base Staff Information Model

    Represents staff information in API responses.
    """

    staff_id: str
    staff_name: str
    staff_pin: Optional[str] = None


# terminal


class BaseTerminal(BaseSchemmaModel):
    """
    Base Terminal Information Model

    Represents terminal information in API responses.
    Contains terminal ID, tenant ID, store code, terminal number, function mode,
    status, business date and other essential terminal details.
    """

    terminal_id: str
    tenant_id: str
    store_code: str
    terminal_no: int
    description: str
    function_mode: str
    status: str
    business_date: Optional[str] = None
    open_counter: int
    business_counter: int
    initial_amount: Optional[float] = None
    physical_amount: Optional[float] = None
    staff: Optional[BaseStaff] = None
    api_key: Optional[str] = None
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseTerminalCreateRequest(BaseSchemmaModel):
    """
    Terminal Creation Request Model

    Used for API requests to create a new terminal.
    """

    store_code: str
    terminal_no: int
    description: str


class BaseTerminalUpdateRequest(BaseSchemmaModel):
    """
    Terminal Update Request Model

    Used for API requests to update an existing terminal's information.
    """

    description: str


class BaseTerminalSignInRequest(BaseSchemmaModel):
    """
    Terminal Sign-In Request Model

    Used for API requests for staff sign-in operations on a terminal.
    """

    staff_id: str


class BaseTerminalOpenRequest(BaseSchemmaModel):
    """
    Terminal Opening Request Model

    Used for API requests to open a terminal for business.
    """

    initial_amount: Optional[float] = None


class BaseTerminalCloseRequest(BaseSchemmaModel):
    """
    Terminal Closing Request Model

    Used for API requests to close a terminal at the end of business.
    """

    physical_amount: Optional[float] = None


class BaseTerminalDeleteResponse(BaseSchemmaModel):
    """
    Terminal Deletion Response Model

    Used for API responses when deleting a terminal.
    """

    terminal_id: str


class BaseUpdateFunctionModeRequest(BaseSchemmaModel):
    """
    Function Mode Update Request Model

    Used for API requests to update a terminal's function mode.
    """

    function_mode: str


class BaseCashInOutRequest(BaseSchemmaModel):
    """
    Cash In/Out Request Model

    Used for API requests for cash deposit or withdrawal operations.
    """

    amount: float
    description: Optional[str] = None


class BaseCashInOutResponse(BaseSchemmaModel):
    """
    Cash In/Out Response Model

    Used for API responses for cash deposit or withdrawal operations.
    Includes receipt and journal text strings.
    """

    terminal_id: str
    amount: float
    description: str
    receipt_text: str
    journal_text: str


class BaseTerminalOpenResponse(BaseSchemmaModel):
    """
    Terminal Opening Response Model

    Used for API responses when opening a terminal for business.
    Includes terminal information, receipt text, and journal text after opening.
    """

    terminal_id: str
    business_date: str
    open_counter: int
    business_counter: int
    initial_amount: Optional[float] = None
    terminal_info: BaseTerminal
    receipt_text: str
    journal_text: str


class BaseTerminalCloseResponse(BaseTerminalOpenResponse):
    """
    Terminal Closing Response Model

    Used for API responses when closing a terminal at end of business.
    Extends the opening response with physical cash amount information.
    """

    physical_amount: Optional[float] = None
