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
from pydantic import Field

from kugel_common.schemas.base_schemas import BaseSchemmaModel

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.base_schemas import Metadata
from kugel_common.security import get_current_user, get_tenant_id_with_token, verify_tenant_id
from kugel_common.status_codes import StatusCodes

from app.api.v1.settlement_schemas import SettlementConfirmResponse, SettlementRecordResponse, figures_of
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


class AdminSettlementRequest(BaseSchemmaModel):
    """Back office settling a session its terminal will never close (#343)."""

    business_counter: int = Field(..., ge=1)
    # Why: recorded on the settlement and in the log
    reason: str = Field(..., min_length=1, max_length=500)
    physical_amount: Optional[float] = None


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlements",
    response_model=ApiResponse[SettlementConfirmResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_CONTENT: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_CONTENT),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def settle_session_by_admin(
    request: AdminSettlementRequest,
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_token),
    user: dict = Depends(get_current_user),
):
    """
    Settle a session whose terminal will never close it: a terminal deleted
    while open, an offline session, a close log that never arrived.

    The settlement is made from the logs that have reached report and is final
    at once, so the daily reports that cover the session can be produced. A
    session already settled is returned as stored. Do not use it for a terminal
    that is still selling: its later sales would be left out of the daily report.
    User or service JWT of the tenant only.
    """
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_settlement_service_async(tenant_id)
    record, created = await service.settle_by_admin_async(
        store_code,
        terminal_no,
        request.business_counter,
        reason=request.reason,
        settled_by=f"admin:{user.get('sub')}",
        physical_amount=request.physical_amount,
    )
    response = SettlementConfirmResponse(**figures_of(record), created=created)
    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Session {'settled by back office' if created else 'already settled'}. settlement_id: {record.settlement_id}",
        data=response.model_dump(by_alias=True),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
