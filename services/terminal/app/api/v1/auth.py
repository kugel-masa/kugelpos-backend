"""
Terminal JWT token authentication endpoint.

Provides POST /auth/token to exchange an API key for a JWT token.
"""
from fastapi import APIRouter, HTTPException, Security, status
from logging import getLogger
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
):
    """
    Exchange an API key for a terminal JWT token.

    The returned JWT contains terminal state claims and can be used
    for authentication with all services without inter-service calls.

    Args:
        api_key: Terminal API key from X-API-KEY header

    Returns:
        ApiResponse containing access_token, token_type, and expires_in
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "API-Key"},
        )

    # Look up terminal by API key across all tenants
    terminal_info = await _get_terminal_info_by_api_key(api_key)

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


async def _get_terminal_info_by_api_key(api_key: str):
    """
    Look up terminal information by API key using the terminal service's
    database access pattern.

    This searches for a terminal with the matching API key. Since we don't
    know the terminal_id upfront, we search across tenant databases.

    Args:
        api_key: The API key to search for

    Returns:
        TerminalInfoDocument for the matched terminal

    Raises:
        HTTPException: If the API key is invalid or terminal not found
    """
    from kugel_common.database import database as db_helper
    from kugel_common.security import transform_terminal_info
    from app.config.settings import settings as app_settings

    # Search for terminal with this API key across known tenant databases
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
            return transform_terminal_info(terminal_dict)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "API-Key"},
    )
