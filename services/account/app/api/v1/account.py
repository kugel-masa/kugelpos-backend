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
from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from logging import getLogger
from datetime import timedelta
import inspect

from kugel_common.status_codes import StatusCodes
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.utils.misc import get_app_time
from kugel_common.utils.slack_notifier import send_info_notification
from app.database import database_setup
from app.api.v1.schemas import LoginResponse, UserAccount, UserAccountInDB
from app.dependencies.auth import (
    get_password_hash,
    create_access_token,
    get_user_collection,
    authenticate_user,
    authenticate_superuser,
    get_current_user,
    generate_tenant_id,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

# Create a FastAPI router instance for account endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)

# API endpoint to obtain a JWT access token


@router.post(
    "/token",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and provide a JWT access token

    The client_id field in the form is used as the tenant_id for multi-tenant support

    Args:
        form_data: Form containing username, password and client_id (as tenant_id)

    Returns:
        LoginResponse: Object containing the access token and token type

    Raises:
        HTTPException: If authentication fails
    """
    tenant_id = form_data.client_id
    logger.info(f"login_for_access_token: username->{form_data.username} tenant_id->{tenant_id}")

    user = await authenticate_user(form_data.username, form_data.password, tenant_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username, password or tenant_id",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "tenant_id": tenant_id, "is_superuser": user.is_superuser},
        expires_delta=access_token_expires,
    )

    # Update last login timestamp
    try:
        users_collection = await get_user_collection(tenant_id)
        result = await users_collection.update_one(
            {"username": user.username}, {"$set": {"last_login": get_app_time()}}
        )
        if result.modified_count == 0:
            raise Exception()
    except Exception as e:
        logger.error(f"update last login failed: {e}. user->{user.username} tenant_id->{tenant_id}")
        # No need to raise exception here - login still succeeds

    return LoginResponse(access_token=access_token, token_type="bearer")


# API endpoint to register a superuser and create a new tenant
@router.post(
    "/register",
    response_model=ApiResponse[UserAccountInDB],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def register_super_user(user: UserAccount, tenant_id: str = Depends(generate_tenant_id)):
    """
    Register a new superuser and create a new tenant

    This endpoint is used for initial setup of a tenant and its admin user

    Args:
        user: User information (username, password, optional tenant_id)
        tenant_id: Generated or verified tenant ID from the dependency

    Returns:
        ApiResponse[UserAccountInDB]: Response with the created user information
    """
    logger.info(f"register_super_user: user->{user.username} tenant_id->{tenant_id}")

    # Set up database for the new tenant
    await database_setup.execute(tenant_id)

    # Create user information with hashed password
    user_info = UserAccountInDB(
        username=user.username,
        password="*****",  # password is not stored in the database
        hashed_password=get_password_hash(user.password),
        tenant_id=tenant_id,
        is_superuser=True,
        is_active=True,
        created_at=get_app_time(),
        updated_at=None,
        last_login=None,
    )

    logger.debug(f"register_super_user: user_info->{user_info.model_dump()}")

    users_collection = await get_user_collection(user_info.tenant_id)
    await users_collection.insert_one(user_info.model_dump())

    # Send notification to Slack about the new tenant creation
    await send_info_notification(
        message=f"Tenant created: {tenant_id}",
        service="account",
        context={"tenant_id": tenant_id, "username": user.username},
    )

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message="User registration successful",
        data=user_info.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


# API endpoint for superusers to register normal users
@router.post(
    "/register/user",
    response_model=ApiResponse[UserAccountInDB],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def register_user_by_superuser(user: UserAccount, current_user: UserAccountInDB = Depends(get_current_user)):
    """
    Register a new regular user in the tenant by a superuser

    This endpoint is protected and can only be called by authenticated superusers

    Args:
        user: User information to create (username, password)
        current_user: The authenticated superuser creating this user

    Returns:
        ApiResponse[UserAccountInDB]: Response with the created user information

    Raises:
        HTTPException: If the current user is not a superuser
    """
    logger.info(
        f"register_user_by_superuser: user->{user.username} "
        f"superuser->{current_user.username} - {current_user.tenant_id}"
    )

    # Authenticate and verify the current user is a superuser
    superuser_info = await authenticate_superuser(current_user.username, current_user.tenant_id)
    if not superuser_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new user information with hashed password
    user_info = UserAccountInDB(
        username=user.username,
        password="*****",  # password is not stored in the database
        hashed_password=get_password_hash(user.password),
        tenant_id=current_user.tenant_id,
        is_superuser=False,
        is_active=True,
        created_at=get_app_time(),
        updated_at=None,
        last_login=None,
    )

    users_collection = await get_user_collection(user_info.tenant_id)
    await users_collection.insert_one(user_info.model_dump())

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message="User registration successful",
        data=user_info.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
