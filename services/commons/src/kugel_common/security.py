# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from fastapi import HTTPException, status, Depends, Security, Path, Query
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from logging import getLogger, Logger
from typing import Optional
from httpx import AsyncClient
import json

from kugel_common.config.settings import settings
from kugel_common.database import database as db_helper
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument

logger = getLogger(__name__)

"""
Authentication and authorization utilities for OAuth2-based authentication
"""
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=settings.TOKEN_URL, auto_error=False)
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

def verify_token(token: str):
    """
    Verifies the provided JWT token and extracts user information.
    
    Args:
        token: JWT token string to be verified
        
    Returns:
        Dictionary containing username, tenant_id, is_superuser, and is_service_account extracted from the token
        
    Raises:
        HTTPException: If the token is invalid or cannot be properly decoded
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Payload: {payload}")
        username: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        is_superuser: bool = payload.get("is_superuser", False)
        is_service_account: bool = payload.get("is_service_account", False)
        service: Optional[str] = payload.get("service")
        if username is None or tenant_id is None:
            raise credentials_exception
        logger.debug(f"username: {username}, tenant_id: {tenant_id}, is_superuser: {is_superuser}, is_service_account: {is_service_account}")
    except JWTError:
        raise credentials_exception
    return {
        "username": username, 
        "tenant_id": tenant_id, 
        "is_superuser": is_superuser,
        "is_service_account": is_service_account,
        "service": service
    }

def verify_tenant_id(tenant_id: str, tenant_id_in_token: str, logger: Logger) -> None:
    """
    Verifies that the tenant ID in the URL matches the tenant ID in the token.
    
    Args:
        tenant_id: Tenant ID from the URL or request
        tenant_id_in_token: Tenant ID extracted from the authentication token
        logger: Logger instance for logging any validation errors
        
    Raises:
        HTTPException: If the tenant IDs do not match
    """
    if tenant_id != tenant_id_in_token:
        message = f"Tenant ID in URL does not match the tenant ID in the token : tenant_id->{tenant_id}, tenant_id_in_token->{tenant_id_in_token}"
        logger.error(message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    FastAPI dependency that returns the current authenticated user based on JWT token.
    
    Args:
        token: JWT token extracted from the Authorization header
        
    Returns:
        Dictionary containing user information extracted from the token
    """
    return verify_token(token)

async def get_service_account_info(token: str = Depends(oauth2_scheme)):
    """
    FastAPI dependency that returns service account information based on JWT token.
    
    Args:
        token: JWT token extracted from the Authorization header
        
    Returns:
        Dictionary containing service account information if the token represents a service account
        
    Raises:
        HTTPException: If the token is not from a service account
    """
    user_info = verify_token(token)
    if not user_info.get("is_service_account"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service account required"
        )
    return user_info

"""
Authentication and authorization utilities for API Key-based authentication
"""
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

def get_tenant_id(terminal_id: str):
    """
    Extracts tenant ID from a terminal ID.
    
    Terminal IDs are formatted as {tenant_id}-{store_code}-{terminal_no}
    
    Args:
        terminal_id: Terminal ID string
        
    Returns:
        The tenant ID portion of the terminal ID
    """
    return terminal_id.split("-")[0]

async def get_terminal_info(
    terminal_id: str,
    api_key: str,
    is_terminal_service: Optional[bool] = False
) -> TerminalInfoDocument:
    """
    Retrieves terminal information either from the database or from the terminal service.
    
    Args:
        terminal_id: Terminal ID to retrieve information for
        api_key: API key for authentication
        is_terminal_service: Whether the caller is the terminal service itself
    Returns:
        TerminalInfoDocument containing the terminal information
    """
    if is_terminal_service:
        terminal_doc = await get_terminal_info_for_terminal_service(terminal_id, api_key)
    else:
        terminal_doc = await get_terminal_info_from_terminal_service(terminal_id, api_key)

    return terminal_doc

async def get_terminal_info_for_terminal_service(
    terminal_id: str, 
    api_key: str,
):
    """
    Retrieves terminal information directly from the database for use by the terminal service.
    
    Args:
        terminal_id: Terminal ID to retrieve information for
        api_key: API key for authentication
        
    Returns:
        TerminalInfoDocument containing the terminal information
        
    Raises:
        HTTPException: If the API key is invalid or the terminal is not found
    """
    logger.debug(f"get_terminal_info_for_terminal_service: terminal_id: {terminal_id}, api_key: ********")
    tenant_id = get_tenant_id(terminal_id)
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    collection = db.get_collection(settings.DB_COLLECTION_NAME_TERMINAL_INFO)
    terminal_dict =  await collection.find_one({"terminal_id": terminal_id})
    logger.debug(f"TerminalInfo: {terminal_dict}")
    # verify api_key
    if (terminal_dict is None) or (terminal_dict.get("api_key") != api_key):
        if api_key != settings.PUBSUB_NOTIFY_API_KEY:
            # allow pubsub notify api key
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid API Key",
                headers={"WWW-Authenticate": "API-Key"}
            )
    return_terminal = transform_terminal_info(terminal_dict)
    logger.debug(f"return_terminal: {return_terminal}")
    return return_terminal

async def get_terminal_info_from_terminal_service(
    terminal_id: str,
    api_key: str
) -> TerminalInfoDocument:
    """
    Retrieves terminal information by making an API call to the terminal service.
    
    Args:
        terminal_id: Terminal ID to retrieve information for
        api_key: API key for authentication
        
    Returns:
        TerminalInfoDocument containing the terminal information
        
    Raises:
        HTTPException: If the API request fails or returns an error
    """
    async with AsyncClient() as client:
        response = await client.get(
            f"{settings.BASE_URL_TERMINAL}/terminals/{terminal_id}",
            headers={"X-API-KEY": api_key}
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "API-KEY"},
        )

    terminal_dict = response.json().get("data")
    return_terminal = transform_terminal_info(terminal_dict)
    return return_terminal

def transform_terminal_info(terminal_dict: dict) -> TerminalInfoDocument:
    """
    Transforms terminal information from dictionary format to TerminalInfoDocument.
    
    Args:
        terminal_dict: Dictionary containing terminal information
        
    Returns:
        TerminalInfoDocument with properly formatted fields
    """
    return_terminal = TerminalInfoDocument(**terminal_dict)
    staff = terminal_dict.get("staff")
    if staff:
        staff_dict = {
            "tenant_id": return_terminal.tenant_id,
            "store_code": return_terminal.store_code,
            "id": staff.get("staffId"),
            "name": staff.get("staffName"),
            "pin": staff.get("staffPin")
        }
        return_terminal.staff = StaffMasterDocument(**staff_dict)
    return return_terminal

"""
Combined authentication utilities for handling both OAuth and API Key authentication
"""
async def __get_tenant_id(
    terminal_id: Optional[str] = None,
    api_key: Optional[str] = None,
    token: Optional[str] = None,
    is_terminal_service: Optional[bool] = False
):
    """
    Internal helper function to retrieve tenant ID using either API key or OAuth token.
    
    Args:
        terminal_id: Optional terminal ID if using API key authentication
        api_key: Optional API key for terminal-based authentication
        token: Optional OAuth token for user-based authentication
        is_terminal_service: Whether the caller is the terminal service itself
        
    Returns:
        Tenant ID string
        
    Raises:
        HTTPException: If neither valid API key nor token is provided
    """
    if terminal_id and api_key:
        logger.debug(f"Terminal_id: {terminal_id}, and API-KEY provided")
        terminal_info = await get_terminal_info(terminal_id, api_key, is_terminal_service)
        return terminal_info.tenant_id
    elif token:
        logger.debug(f"Token provided")
        user_dict = await get_current_user(token)
        return user_dict.get("tenant_id")
    else:
        message = "Unauthorized access : No token or API-KEY provided"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

async def get_tenant_id_with_security(
    terminal_id: str = Path(..., description="terminal_id should be provided in the path"),
    api_key: Optional[str] = Security(api_key_header), 
    token: Optional[str] = Depends(oauth2_scheme),
    is_terminal_service: Optional[bool] = False
):
    """
    FastAPI dependency that retrieves tenant ID using path parameter for terminal ID.
    
    Args:
        terminal_id: Terminal ID from path parameter
        api_key: API key from header
        token: OAuth token from header
        is_terminal_service: Whether the caller is the terminal service itself
        
    Returns:
        Tenant ID string
    """
    return await __get_tenant_id(terminal_id, api_key, token, is_terminal_service)

async def get_tenant_id_with_security_by_query(
    terminal_id: str = Query(..., description="terminal_id should be provided by query parameter"),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
    is_terminal_service: Optional[bool] = False
):
    """
    FastAPI dependency that retrieves tenant ID using query parameter for terminal ID.
    
    Args:
        terminal_id: Terminal ID from query parameter
        api_key: API key from header
        token: OAuth token from header
        is_terminal_service: Whether the caller is the terminal service itself
        
    Returns:
        Tenant ID string
    """
    return await __get_tenant_id(terminal_id, api_key, token, is_terminal_service)

async def get_tenant_id_with_security_by_query_optional(
    terminal_id: Optional[str] = Query(None, description="terminal_id should be provided by query parameter optional"),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
    is_terminal_service: Optional[bool] = False
):
    """
    FastAPI dependency that retrieves tenant ID using optional query parameter for terminal ID.
    
    Args:
        terminal_id: Optional terminal ID from query parameter
        api_key: API key from header
        token: OAuth token from header
        is_terminal_service: Whether the caller is the terminal service itself
        
    Returns:
        Tenant ID string
    """
    return await __get_tenant_id(terminal_id, api_key, token, is_terminal_service)

async def get_tenant_id_with_token(
    token: str = Depends(oauth2_scheme),
    is_terminal_service: Optional[bool] = False
):
    """
    FastAPI dependency that retrieves tenant ID using only OAuth token authentication.
    
    Args:
        token: OAuth token from header
        is_terminal_service: Whether the caller is the terminal service itself
        
    Returns:
        Tenant ID string
    """
    return await __get_tenant_id(token=token, is_terminal_service=is_terminal_service)

async def get_terminal_info_with_api_key(
    terminal_id: str = Query(...),
    api_key: str = Security(api_key_header),
    is_terminal_service: Optional[bool] = False
):
    """
    FastAPI dependency that retrieves full terminal information using API key authentication.
    
    Args:
        terminal_id: Terminal ID from query parameter
        api_key: API key from header
        is_terminal_service: Whether the caller is the terminal service itself
        
    Returns:
        TerminalInfoDocument containing the terminal information
    """
    return await get_terminal_info(terminal_id, api_key, is_terminal_service)

async def verify_pubsub_notification_auth(
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> dict:
    """
    FastAPI dependency that verifies authentication for pub/sub notification callbacks.
    Accepts either a service JWT token or the PUBSUB_NOTIFY_API_KEY for backward compatibility.
    
    Args:
        api_key: API key from header
        token: JWT token from header
        
    Returns:
        Dictionary containing authentication information
        
    Raises:
        HTTPException: If neither valid JWT token nor PUBSUB_NOTIFY_API_KEY is provided
    """
    # First try JWT token authentication
    if token:
        try:
            user_info = verify_token(token)
            if user_info.get("is_service_account"):
                return {
                    "auth_type": "jwt",
                    "service": user_info.get("service"),
                    "tenant_id": user_info.get("tenant_id")
                }
        except HTTPException:
            pass  # Fall through to API key check
    
    # Fall back to PUBSUB_NOTIFY_API_KEY for backward compatibility
    if api_key == settings.PUBSUB_NOTIFY_API_KEY:
        return {
            "auth_type": "api_key",
            "service": None,
            "tenant_id": None
        }
    
    # Neither authentication method succeeded
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication for pub/sub notification",
        headers={"WWW-Authenticate": "Bearer, API-Key"}
    )
