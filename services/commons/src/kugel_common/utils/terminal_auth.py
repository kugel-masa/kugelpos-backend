"""
Terminal JWT token generation utilities

This module provides JWT token generation for terminal authentication.
Terminal tokens contain terminal state claims and are validated locally
by all services without inter-service HTTP calls.
"""
from datetime import datetime, timedelta, timezone
from jose import jwt
from logging import getLogger

from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument

logger = getLogger(__name__)


def create_terminal_token(
    terminal_info: TerminalInfoDocument,
    expires_delta: timedelta = None,
) -> str:
    """
    Create a JWT token for terminal authentication.

    Builds JWT claims from TerminalInfoDocument fields and signs
    with the shared SECRET_KEY using HS256.

    Args:
        terminal_info: Terminal information document containing state
        expires_delta: Optional custom expiration time
            (default: TERMINAL_TOKEN_EXPIRE_HOURS from settings)

    Returns:
        Encoded JWT token string
    """
    claims = {
        "sub": f"terminal:{terminal_info.terminal_id}",
        "tenant_id": terminal_info.tenant_id,
        "store_code": terminal_info.store_code,
        "terminal_no": terminal_info.terminal_no,
        "terminal_id": terminal_info.terminal_id,
        "status": terminal_info.status,
        "token_type": "terminal",
        "iss": "terminal-service",
    }

    # Optional claims based on terminal state
    if terminal_info.business_date is not None:
        claims["business_date"] = terminal_info.business_date
    if terminal_info.open_counter is not None:
        claims["open_counter"] = terminal_info.open_counter
    if terminal_info.business_counter is not None:
        claims["business_counter"] = terminal_info.business_counter

    # Staff claims (only present when signed in)
    if terminal_info.staff and terminal_info.staff.id:
        claims["staff_id"] = terminal_info.staff.id
        claims["staff_name"] = terminal_info.staff.name

    # Set expiration
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.TERMINAL_TOKEN_EXPIRE_HOURS)

    claims["exp"] = expire

    encoded_jwt = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    logger.debug(f"Created terminal token for {terminal_info.terminal_id}")

    return encoded_jwt
