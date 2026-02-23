# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, Depends, Path, Query
from logging import getLogger
from typing import List, Optional
from datetime import datetime
import inspect

from kugel_common.status_codes import StatusCodes
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.schemas.api_response import ApiResponse

from app.api.v1.schemas import (
    PromotionCreateRequest,
    PromotionUpdateRequest,
    PromotionResponse,
    PromotionDeleteResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_promotion_master_service_async
from app.dependencies.common import parse_sort
from app.models.documents.promotion_master_document import PromotionMasterDocument

router = APIRouter()
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/promotions",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[PromotionResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_promotion(
    promotion: PromotionCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new promotion record.

    This endpoint allows creating a new promotion with its code, type, name,
    datetime range, and type-specific details (e.g., category promotion details).

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.
    """
    logger.info(f"create_promotion: promotion->{promotion}, tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_promotion_master_service_async(tenant_id)

    try:
        # Parse datetime strings
        start_dt = datetime.fromisoformat(promotion.start_datetime)
        end_dt = datetime.fromisoformat(promotion.end_datetime)

        # Build detail if provided
        detail = None
        if promotion.detail:
            detail = PromotionMasterDocument.CategoryPromoDetail(
                target_store_codes=promotion.detail.target_store_codes or [],
                target_category_codes=promotion.detail.target_category_codes,
                discount_rate=promotion.detail.discount_rate,
            )

        new_promotion = await service.create_promotion_async(
            promotion_code=promotion.promotion_code,
            promotion_type=promotion.promotion_type,
            name=promotion.name,
            start_datetime=start_dt,
            end_datetime=end_dt,
            description=promotion.description,
            is_active=promotion.is_active,
            detail=detail,
        )
        transformer = SchemasTransformerV1()
        return_promotion = transformer.transform_promotion(new_promotion)
    except Exception as e:
        logger.error(f"Error creating promotion: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Promotion {promotion.promotion_code} created successfully",
        data=return_promotion.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/promotions",
    response_model=ApiResponse[List[PromotionResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_promotions(
    tenant_id: str = Path(...),
    limit: int = Query(20),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    promotion_type: Optional[str] = Query(None, alias="promotionType"),
    is_active: Optional[bool] = Query(None, alias="isActive"),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all promotions for a tenant with pagination.

    This endpoint returns a paginated list of all promotions for the specified tenant.
    The results can be filtered by promotion type and active status.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.
    """
    logger.info(f"get_promotions: tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_promotion_master_service_async(tenant_id)

    try:
        paginated_result = await service.get_promotions_paginated_async(
            limit, page, sort, promotion_type, is_active
        )
        transformer = SchemasTransformerV1()
        return_promotions = [
            transformer.transform_promotion(promo) for promo in paginated_result.data
        ]
    except Exception as e:
        logger.error(f"Error getting promotions: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Promotions retrieved successfully for tenant_id: {tenant_id}",
        data=[promo.model_dump() for promo in return_promotions],
        metadata=paginated_result.metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/promotions/active",
    response_model=ApiResponse[List[PromotionResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_active_promotions(
    tenant_id: str = Path(...),
    store_code: Optional[str] = Query(None, alias="storeCode"),
    category_code: Optional[str] = Query(None, alias="categoryCode"),
    promotion_type: Optional[str] = Query(None, alias="promotionType"),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve currently active promotions.

    This endpoint returns promotions that are currently active based on:
    - is_active = True
    - is_deleted = False
    - Current time is within start_datetime and end_datetime

    Optional filters:
    - storeCode: Filter by store (returns promotions targeting that store or all stores)
    - categoryCode: Filter by category
    - promotionType: Filter by promotion type

    Authentication is required via token or API key.
    """
    logger.info(f"get_active_promotions: tenant_id->{tenant_id}, store_code->{store_code}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_promotion_master_service_async(tenant_id)

    try:
        promotions = await service.get_active_promotions_async(
            store_code=store_code,
            category_code=category_code,
            promotion_type=promotion_type,
        )
        transformer = SchemasTransformerV1()
        return_promotions = [transformer.transform_promotion(promo) for promo in promotions]
    except Exception as e:
        logger.error(f"Error getting active promotions: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Active promotions retrieved successfully for tenant_id: {tenant_id}",
        data=[promo.model_dump() for promo in return_promotions],
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/promotions/{promotion_code}",
    response_model=ApiResponse[PromotionResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_promotion(
    promotion_code: str,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific promotion by its code.

    This endpoint retrieves the details of a promotion identified by its unique code.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.
    """
    logger.info(f"get_promotion: promotion_code->{promotion_code}, tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_promotion_master_service_async(tenant_id)

    try:
        promotion = await service.get_promotion_by_code_async(promotion_code)
        transformer = SchemasTransformerV1()
        return_promotion = transformer.transform_promotion(promotion)
    except Exception as e:
        logger.error(f"Error getting promotion: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Promotion {promotion_code} found successfully for tenant_id: {tenant_id}",
        data=return_promotion.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/promotions/{promotion_code}",
    response_model=ApiResponse[PromotionResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_promotion(
    promotion_code: str,
    promotion: PromotionUpdateRequest,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing promotion.

    This endpoint allows updating the details of an existing promotion identified
    by its code. The promotion_code and promotion_type cannot be changed.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.
    """
    logger.info(f"update_promotion: promotion->{promotion}, tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_promotion_master_service_async(tenant_id)

    try:
        # Build update data, excluding None values
        update_data = {}
        if promotion.name is not None:
            update_data["name"] = promotion.name
        if promotion.description is not None:
            update_data["description"] = promotion.description
        if promotion.start_datetime is not None:
            update_data["start_datetime"] = datetime.fromisoformat(promotion.start_datetime)
        if promotion.end_datetime is not None:
            update_data["end_datetime"] = datetime.fromisoformat(promotion.end_datetime)
        if promotion.is_active is not None:
            update_data["is_active"] = promotion.is_active
        if promotion.detail is not None:
            detail = PromotionMasterDocument.CategoryPromoDetail(
                target_store_codes=promotion.detail.target_store_codes or [],
                target_category_codes=promotion.detail.target_category_codes,
                discount_rate=promotion.detail.discount_rate,
            )
            update_data["detail"] = detail.model_dump()

        updated_promotion = await service.update_promotion_async(
            promotion_code=promotion_code, update_data=update_data
        )
        transformer = SchemasTransformerV1()
        return_promotion = transformer.transform_promotion(updated_promotion)
    except Exception as e:
        logger.error(f"Error updating promotion: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Promotion {promotion_code} updated successfully for tenant_id: {tenant_id}",
        data=return_promotion.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/promotions/{promotion_code}",
    response_model=ApiResponse[PromotionDeleteResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_promotion(
    promotion_code: str,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a promotion (logical deletion).

    This endpoint performs a soft delete by setting is_deleted = True.
    The promotion will no longer appear in active or general listings.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.
    """
    logger.info(f"delete_promotion: promotion_code->{promotion_code}, tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_promotion_master_service_async(tenant_id)

    try:
        await service.delete_promotion_async(promotion_code)
    except Exception as e:
        logger.error(f"Error deleting promotion: {e} for tenant_id: {tenant_id}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Promotion {promotion_code} deleted successfully for tenant_id: {tenant_id}",
        data=PromotionDeleteResponse(promotion_code=promotion_code).model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
