"""
Terminal JWT token authentication endpoint.

Provides POST /auth/token to exchange an API key for a JWT token.
"""
from fastapi import APIRouter, HTTPException, Query, Security, status
from logging import getLogger
from typing import Optional
from pydantic import BaseModel

from kugel_common.security import api_key_header, get_terminal_info_for_terminal_service
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.utils.terminal_auth import create_terminal_token
from kugel_common.config.settings import settings

router = APIRouter()
logger = getLogger(__name__)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post(
    "/auth/token",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TokenResponse],
)
async def create_token(
    api_key: str = Security(api_key_header),
    terminal_id: Optional[str] = Query(None, description="Terminal ID for direct lookup (recommended)"),
):
    """
    Exchange an API key for a terminal JWT token.

    The returned JWT contains terminal state claims and can be used
    for authentication with all services without inter-service calls.

    When terminal_id is provided, lookup is O(1) against the tenant DB.
    When omitted, all tenant DBs are scanned (slower, for backward compatibility).

    Args:
        api_key: Terminal API key from X-API-KEY header
        terminal_id: Optional terminal ID for direct DB lookup

    Returns:
        ApiResponse containing access_token, token_type, and expires_in
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "API-Key"},
        )

    # Fast path: direct lookup by terminal_id + api_key
    if terminal_id:
        terminal_info = await _get_terminal_info_direct(terminal_id, api_key)
    else:
        # Slow path: scan all tenant DBs (backward compatibility)
        logger.debug("No terminal_id provided, scanning all tenant databases")
        terminal_info = await _get_terminal_info_by_api_key_scan(api_key)

    # Generate JWT token
    token = create_terminal_token(terminal_info)
    expires_in = settings.TERMINAL_TOKEN_EXPIRE_HOURS * 3600

    logger.info(f"Terminal token issued for {terminal_info.terminal_id}")

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Token issued for terminal {terminal_info.terminal_id}",
        data=TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
        ),
    )


async def _get_terminal_info_direct(terminal_id: str, api_key: str):
    """
    Look up terminal by terminal_id + api_key in the correct tenant DB.
    O(1) lookup using the existing get_terminal_info_for_terminal_service.

    Args:
        terminal_id: Terminal ID (format: {tenant_id}-{store_code}-{terminal_no})
        api_key: API key to verify

    Returns:
        TerminalInfoDocument

    Raises:
        HTTPException: If terminal not found or API key invalid
    """
    return await get_terminal_info_for_terminal_service(terminal_id, api_key)


async def _get_terminal_info_by_api_key_scan(api_key: str):
    """
    Scan all tenant databases to find a terminal by API key.
    O(n) where n = number of tenant databases. Use only when terminal_id is unknown.

    Args:
        api_key: The API key to search for

    Returns:
        TerminalInfoDocument

    Raises:
        HTTPException: If the API key is invalid or terminal not found
    """
    from kugel_common.database import database as db_helper
    from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
    from kugel_common.models.documents.staff_master_document import StaffMasterDocument
    from app.config.settings import settings as app_settings

    db_client = await db_helper.get_client_async()
    db_names = await db_client.list_database_names()

    prefix = app_settings.DB_NAME_PREFIX
    for db_name in db_names:
        if not db_name.startswith(f"{prefix}_") or db_name.endswith("_commons"):
            continue

        db = await db_helper.get_db_async(db_name)
        collection = db.get_collection(app_settings.DB_COLLECTION_NAME_TERMINAL_INFO)
        terminal_dict = await collection.find_one({"api_key": api_key})

        if terminal_dict:
            logger.debug(f"Found terminal with API key in database {db_name}")
            terminal_info = TerminalInfoDocument(**terminal_dict)
            staff_data = terminal_dict.get("staff")
            if staff_data and staff_data.get("id"):
                terminal_info.staff = StaffMasterDocument(
                    tenant_id=terminal_info.tenant_id,
                    store_code=terminal_info.store_code,
                    id=staff_data.get("id"),
                    name=staff_data.get("name"),
                    pin=staff_data.get("pin"),
                )
            return terminal_info

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "API-Key"},
    )
