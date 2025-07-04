# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Query, Path
from logging import getLogger
import inspect

from kugel_common.status_codes import StatusCodes
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.schemas.api_response import ApiResponse
from app.api.common.pagination import PaginationMetadata
from kugel_common.exceptions import (
    InvalidRequestDataException,
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    RepositoryException,
)

from app.api.v1.schemas import (
    SettingsMasterCreateRequest,
    SettingsMasterUpdateRequest,
    SettingsMasterResponse,
    SettingsMasterDeleteResponse,
    SettingsMasterValueResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_settings_master_service_async
from app.dependencies.common import parse_sort

# Create a router instance for settings master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/settings",
    response_model=ApiResponse[SettingsMasterResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_settings_master_async(
    settings: SettingsMasterCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new system settings record.

    This endpoint allows creating a new settings entry with a name, default value,
    and specific values for different store/terminal combinations. System settings
    control the behavior of various aspects of the POS system.

    Each settings entry can have different values for different stores or terminals,
    allowing for fine-grained configuration of the system behavior.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        settings: The settings details to create, including name, default value and specific values
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[SettingsMasterResponse]: Standard API response with the created settings data

    Raises:
        DocumentAlreadyExistsException: If a settings with the same name already exists
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Create settings request received for settings name: {settings.name}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_settings_master_service_async(tenant_id)
    try:
        settings_doc = await master_service.create_settings_async(
            settings.name, settings.default_value, [value.model_dump() for value in settings.values]
        )
        transformer = SchemasTransformerV1()
        return_settings = transformer.transform_settings_master(settings_doc)
    except Exception as e:
        logger.error(f"Error creating settings: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Settings created successfully. settings_id: {return_settings.name}",
        data=return_settings,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/settings",
    response_model=ApiResponse[list[SettingsMasterResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_settings_master_async(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all system settings for a tenant.

    This endpoint returns a paginated list of all settings for the specified tenant.
    The results can be sorted and paginated as needed. This is typically used by
    administrative interfaces to view and manage all system settings.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        limit: Maximum number of settings to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: name ascending)
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[list[SettingsMasterResponse]]: Standard API response with a list of settings data and pagination metadata

    Raises:
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get settings request received. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_settings_master_service_async(tenant_id)
    try:
        settings_doc_list, total_count = await master_service.get_settings_all_paginated_async(limit, page, sort)
        transformer = SchemasTransformerV1()
        return_settings_list = [
            transformer.transform_settings_master(settings_doc) for settings_doc in settings_doc_list
        ]
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Settings retrieved successfully. Total count: {total_count}",
        data=return_settings_list,
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/settings/{name}",
    response_model=ApiResponse[SettingsMasterResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_settings_master_by_name_async(
    name: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific system setting by its name.

    This endpoint retrieves the details of a setting identified by its unique name.
    It returns the complete setting information including default value and all specific
    values configured for different store/terminal combinations.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        name: The unique name of the setting to retrieve
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[SettingsMasterResponse]: Standard API response with the setting data

    Raises:
        DocumentNotFoundException: If the setting with the given name is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get settings request received for settings name: {name}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_settings_master_service_async(tenant_id)
    try:
        settings_doc = await master_service.get_settings_by_name_async(name)
        if settings_doc is None:
            message = f"Settings not found. settings name: {name}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        return_settings = transformer.transform_settings_master(settings_doc)
    except Exception as e:
        logger.error(f"Error getting settings by name: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Settings found. settings_id: {return_settings.name}",
        data=return_settings,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/settings/{name}/value",
    response_model=ApiResponse[SettingsMasterValueResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_settings_value_by_name_async(
    name: str,
    store_code: str = Query(...),
    terminal_no: int = Query(...),
    tenant_id: str = Path(...),
    tenant_id_in_token=Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve the effective value of a setting for a specific store and terminal.

    This endpoint is critical for runtime configuration, as it resolves the effective
    value of a setting for a specific store/terminal combination. It first looks for
    a value specific to the store and terminal, then for a store-wide value, and finally
    falls back to the default value.

    This is typically used by the POS terminals to get their configuration values at startup
    or when refreshing settings.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        name: The name of the setting to retrieve
        store_code: The store code to get the setting value for
        terminal_no: The terminal number to get the setting value for
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[SettingsMasterValueResponse]: Standard API response with the resolved setting value

    Raises:
        DocumentNotFoundException: If the setting with the given name is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Get settings value request received for settings name: {name}. tenant_id: {tenant_id}. store_code: {store_code}. terminal_no: {terminal_no}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_settings_master_service_async(tenant_id)
    try:
        value = await master_service.get_settings_value_by_name_async(name, store_code, terminal_no)
        if value is None:
            message = f"Settings value not found. settings_name: {name}"
            raise DocumentNotFoundException(message, logger)

        logger.debug(f"Settings value found. settings_name: {name}. value: {value}")

    except Exception as e:
        logger.error(f"Error getting settings value: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Settings value found. settings_name: {name}",
        data=SettingsMasterValueResponse(value=value),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/settings/{name}",
    response_model=ApiResponse[SettingsMasterResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_settings_master_async(
    name: str,
    settings: SettingsMasterUpdateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing system setting.

    This endpoint allows updating the default value and specific values of an existing setting.
    It can be used to modify the behavior of the system without requiring code changes.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        name: The unique name of the setting to update
        settings: The updated setting details
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[SettingsMasterResponse]: Standard API response with the updated setting data

    Raises:
        DocumentNotFoundException: If the setting with the given name is not found
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Update settings request received for settings name: {name}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_settings_master_service_async(tenant_id)
    try:
        settings_doc = await master_service.update_settings_async(name, settings.model_dump())
        transformer = SchemasTransformerV1()
        return_settings = transformer.transform_settings_master(settings_doc)
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Settings updated successfully. settings_id: {return_settings.name}",
        data=return_settings,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/settings/{name}",
    response_model=ApiResponse[SettingsMasterDeleteResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_settings_master_async(
    name: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a system setting.

    This endpoint allows removing a setting completely from the system.
    Caution should be exercised as removing critical settings may cause
    system malfunctions if the code expects those settings to exist.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        name: The unique name of the setting to delete
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[SettingsMasterDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        DocumentNotFoundException: If the setting with the given name is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Delete settings request received for settings name: {name}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_settings_master_service_async(tenant_id)
    try:
        await master_service.delete_settings_async(name)
    except Exception as e:
        logger.error(f"Error deleting settings: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Settings deleted successfully. settings_id: {name}",
        data=SettingsMasterDeleteResponse(name=name),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
