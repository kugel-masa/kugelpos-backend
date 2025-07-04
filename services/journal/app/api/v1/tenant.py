# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends
from logging import getLogger
import inspect

from kugel_common.status_codes import StatusCodes
from kugel_common.security import get_tenant_id_with_token
from kugel_common.schemas.api_response import ApiResponse

from app.database import database_setup
from app.api.v1.schemas import (
    TenantCreateRequest,
    TenantCreateResponse,
)

# create a router instance
router = APIRouter()

# get an instance of the logger
logger = getLogger(__name__)


@router.post("/tenants", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: TenantCreateRequest,
    tenant_id: str = Depends(get_tenant_id_with_token),
):
    """
    Setup the database for the tenant. This will create the required collections and indexes.
    """
    logger.info(f"Setting up database for tenant: {tenant_id}")

    # check if tenant_id is equal to the tenant_id in the request bad request
    if tenant_id != req.tenant_id:
        message = f"Tenant ID in request does not match the tenant ID in the URL : req.tenant_id->{req.tenant_id}, tenant_id->{tenant_id}"
        logger.error(message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        # create the required collections
        await database_setup.execute(tenant_id=tenant_id)

    except Exception as e:
        message = f"Error creating tenant: {tenant_id}"
        logger.error(message)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    return ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Creating tenant has completed: {tenant_id}",
        data=TenantCreateResponse(tenant_id=tenant_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
