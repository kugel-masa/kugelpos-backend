# Copyright 2026 masa@kugel
"""
Internal endpoints for service-to-service calls (master-data, issue #323).

Nothing here is meant for a terminal or a client. A service-account token is
the only credential accepted: a terminal token, a user token or an API key is
refused. The tenant in the path must be the token's.

Staff verification is the one place the staff PIN is compared; the PIN never
leaves this service, in a response or a log line.
"""

import inspect
from logging import getLogger

from fastapi import APIRouter, Depends, Path, status

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_service_account_info, verify_tenant_id
from kugel_common.status_codes import StatusCodes

from app.api.v1.schemas import StaffVerifyRequest, StaffVerifyResponse
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_staff_master_service_async

router = APIRouter(prefix="/internal")

logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/staff/{staff_id}/verify",
    response_model=ApiResponse[StaffVerifyResponse],
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
async def verify_staff(
    request: StaffVerifyRequest,
    tenant_id: str = Path(...),
    staff_id: str = Path(...),
    auth_info: dict = Depends(get_service_account_info),
):
    """
    Verify a staff member for sign-in, without returning the PIN.

    The PIN is required only when the staff record has one; see
    StaffMasterService.verify_staff_async for the decision. Failures answer
    405701 (staff not found), 405702 (PIN required) or 405703 (PIN mismatch),
    with no details.

    Args:
        request: The body, carrying the optional PIN
        tenant_id: Tenant in the path; must be the token's
        staff_id: The staff member's ID
        auth_info: Claims of the service-account token

    Returns:
        ApiResponse[StaffVerifyResponse]: The staff ID and name
    """
    logger.info(
        f"Staff verification requested: tenant_id->{tenant_id}, staff_id->{staff_id}, "
        f"caller->{auth_info.get('service')}"
    )
    verify_tenant_id(tenant_id, auth_info.get("tenant_id"), logger)

    service = await get_staff_master_service_async(tenant_id)
    staff = await service.verify_staff_async(staff_id, request.pin)
    verified = SchemasTransformerV1().transform_staff_verification(staff)

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Staff verified. staff_id: {verified.id}",
        data=verified.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
