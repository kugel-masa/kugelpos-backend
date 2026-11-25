# Copyright 2026 masa@kugel
"""
Settlement records of a store, for back-office review (#343, US4).

A user or service JWT of the tenant only: a terminal's API key or JWT is
refused. The list leaves out the frozen daily reports.
"""

import inspect
from logging import getLogger
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.base_schemas import Metadata
from kugel_common.security import get_tenant_id_with_token, verify_tenant_id
from kugel_common.status_codes import StatusCodes

from app.api.v1.settlement_schemas import SettlementRecordResponse, figures_of
from app.dependencies.get_settlement_service import get_settlement_service_async
from app.exceptions import ReportDateException

router = APIRouter()

logger = getLogger(__name__)


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/settlements",
    response_model=ApiResponse[list[SettlementRecordResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_CONTENT: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_CONTENT),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def list_settlements(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: Optional[int] = Query(None),
    business_counter: Optional[int] = Query(None),
    business_date_from: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    business_date_to: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    state: Optional[str] = Query(None, pattern=r"^(provisional|final)$"),
    limit: int = Query(100, ge=1, le=1000),
    page: int = Query(1, ge=1),
    tenant_id_in_token: str = Depends(get_tenant_id_with_token),
):
    """The store's settlement records, by business date, terminal and session."""
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    if bool(business_date_from) != bool(business_date_to):
        raise ReportDateException(
            f"A business date range needs both ends: from->{business_date_from}, to->{business_date_to}", logger
        )
    service = await get_settlement_service_async(tenant_id)
    result = await service.settlement_repository.list_async(
        store_code,
        terminal_no=terminal_no,
        business_counter=business_counter,
        business_date_from=business_date_from,
        business_date_to=business_date_to,
        state=state,
        limit=limit,
        page=page,
    )
    data = [SettlementRecordResponse(**figures_of(r)).model_dump(by_alias=True) for r in result.data]
    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"{result.metadata.total} settlement(s)",
        data=data,
        metadata=Metadata(total=result.metadata.total, page=page, limit=limit, sort=None, filter=None),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )

