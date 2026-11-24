# Copyright 2026 masa@kugel
"""
Internal settlement endpoints for service-to-service calls (#343).

Only terminal calls these, at close and before it. A service-account token is
the only credential accepted: a terminal token, a user token or an API key is
refused, and the tenant in the path must be the token's.
"""

import inspect
from logging import getLogger
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_service_account_info, verify_tenant_id
from kugel_common.status_codes import StatusCodes

from app.api.v1.settlement_schemas import (
    SettlementConfirmRequest,
    SettlementConfirmResponse,
    SettlementPreviewResponse,
    figures_of,
)
from app.dependencies.get_settlement_service import get_settlement_service_async
from app.services.settlement_service import SettlementRequest

router = APIRouter(prefix="/internal")

logger = getLogger(__name__)

# The only caller: terminal settles at close and previews before it.
SETTLING_SERVICE = "terminal"


def _require_terminal(auth_info: dict, tenant_id: str) -> None:
    """A service account of the path's tenant, and of terminal (least privilege)."""
    verify_tenant_id(tenant_id, auth_info.get("tenant_id"), logger)
    if auth_info.get("service") != SETTLING_SERVICE:
        logger.warning(f"Settlement endpoint refused for service {auth_info.get('service')!r}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only terminal may settle a session")


_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
    status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
    status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
    status.HTTP_422_UNPROCESSABLE_CONTENT: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_CONTENT),
    status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
}


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlements",
    response_model=ApiResponse[SettlementConfirmResponse],
    status_code=status.HTTP_200_OK,
    responses=_RESPONSES,
)
async def confirm_settlement(
    request: SettlementConfirmRequest,
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    auth_info: dict = Depends(get_service_account_info),
):
    """
    Confirm a terminal session's settlement from the logs that have arrived.

    A provisional settlement is recomputed and replaced; a final one is returned
    as stored. Missing or duplicate transactions never refuse the settlement;
    they are recorded.
    """
    _require_terminal(auth_info, tenant_id)
    service = await get_settlement_service_async(tenant_id)
    record, created = await service.confirm_async(
        SettlementRequest(store_code=store_code, terminal_no=terminal_no, **request.model_dump())
    )
    response = SettlementConfirmResponse(**figures_of(record), created=created)
    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Settlement {'confirmed' if created else 'already final'}. settlement_id: {record.settlement_id}",
        data=response.model_dump(by_alias=True),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlement-preview",
    response_model=ApiResponse[SettlementPreviewResponse],
    status_code=status.HTTP_200_OK,
    responses=_RESPONSES,
)
async def preview_settlement(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    business_counter: int = Query(..., ge=1),
    business_date: str = Query(..., pattern=r"^\d{8}$"),
    open_counter: int = Query(..., ge=1),
    seq: Optional[int] = Query(None, ge=0),
    cash_log_count: Optional[int] = Query(None, ge=0),
    physical_amount: Optional[float] = Query(None),
    auth_info: dict = Depends(get_service_account_info),
):
    """What confirming would record now, without storing anything."""
    _require_terminal(auth_info, tenant_id)
    service = await get_settlement_service_async(tenant_id)
    figures, settled = await service.preview_async(
        SettlementRequest(
            store_code=store_code,
            terminal_no=terminal_no,
            business_counter=business_counter,
            business_date=business_date,
            open_counter=open_counter,
            settled_at="",
            seq=seq,
            cash_log_count=cash_log_count,
            physical_amount=physical_amount,
        )
    )
    response = SettlementPreviewResponse(**figures_of(figures), settled=settled)
    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Settlement preview",
        data=response.model_dump(by_alias=True),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
