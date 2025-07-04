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
from fastapi import status, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from logging import getLogger
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
import random, string

from kugel_common.database import database as db_helper
from app.config.settings import settings
from app.api.v1.schemas import UserAccountInDB, UserAccount

# Get a logger instance for this module
logger = getLogger(__name__)

# JWT Authentication configuration from environment settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.TOKEN_EXPIRE_MINUTES

# OAuth2 password bearer for token-based authentication
# This specifies the URL that the client should use to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/accounts/token")

# Password hashing context using bcrypt for secure password storage
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Authentication helper functions
def verify_password(plain_password, hashed_password):
    """
    Verify if the plain password matches the hashed password

    Args:
        plain_password: The password provided by the user in plain text
        hashed_password: The hashed password stored in the database

    Returns:
        bool: True if the password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    Hash a password using bcrypt

    Args:
        password: The plain text password to hash

    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    Create a JWT access token with the provided data

    Args:
        data: The payload data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        str: The encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_user_collection(tenant_id: str) -> AsyncIOMotorCollection:
    """
    Get the MongoDB collection for user accounts for a specific tenant

    Args:
        tenant_id: The tenant identifier

    Returns:
        AsyncIOMotorCollection: MongoDB collection for user accounts
    """
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return db.get_collection(settings.DB_COLLECTION_USER_ACCOUNTS)


async def authenticate_user(username: str, password: str, tenant_id: str):
    """
    Authenticate a user by username, password, and tenant_id

    Args:
        username: The username to authenticate
        password: The password to verify
        tenant_id: The tenant identifier

    Returns:
        UserAccountInDB or False: User object if authentication succeeds, False otherwise
    """
    users_collection = await get_user_collection(tenant_id)
    user = await users_collection.find_one({"username": username})
    if user is None:
        return False
    return_user = UserAccountInDB(**user)
    if return_user.is_active is False:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return return_user


async def authenticate_superuser(username: str, tenant_id: str):
    """
    Authenticate a user as a superuser by username and tenant_id

    Args:
        username: The username to authenticate
        tenant_id: The tenant identifier

    Returns:
        UserAccountInDB or False: User object if the user is a superuser, False otherwise
    """
    users_collection = await get_user_collection(tenant_id)
    superuser_dict = await users_collection.find_one({"username": username})
    superuser_info = UserAccountInDB(**superuser_dict)
    if superuser_info is None:
        return False
    if not superuser_info.is_superuser:
        return False
    if superuser_info.is_active is False:
        return False
    return superuser_info


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Get the current user from a JWT token
    Used as a dependency to protect routes that require authentication

    Args:
        token: JWT token from the request header

    Returns:
        UserAccountInDB: Current user information

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        is_superuser: bool = payload.get("is_superuser")
        if username is None or tenant_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_collection = await get_user_collection(tenant_id)
    user = await user_collection.find_one({"username": username})
    if user is None:
        raise credentials_exception
    user.pop("is_superuser")
    return UserAccountInDB(**user, is_superuser=is_superuser)


async def generate_tenant_id(user: UserAccount = None):
    """
    Generate a unique tenant ID or verify the provided one is available

    Args:
        user: Optional user information with preferred tenant_id

    Returns:
        str: A unique tenant ID
    """
    tenant_id = user.tenant_id if user else None

    while True:
        if tenant_id:
            logger.info(f"tenant_id that client want: {tenant_id}")
        else:
            logger.info("generate_tenant_id started")
            # Generate tenant ID with format: one uppercase letter followed by 4 digits
            letter = random.choice(string.ascii_uppercase)
            number = f"{random.randint(1000, 9999):04}"
            tenant_id = f"{letter}{number}"

        # Construct the database name using the tenant ID prefix
        db_name = f"{settings.DB_NAME_PREFIX}_{tenant_id}"

        # Get the MongoDB client to check if the database already exists
        db_client = await db_helper.get_client_async()

        # Get a list of all existing database names
        db_list = await db_client.list_database_names()
        logger.info(f"existing db_list->{db_list}")
        logger.info(f"db_name->{db_name}")

        # Check if the database name is available (not already used)
        if db_name not in db_list:
            logger.info(f"generate_tenant_id: {tenant_id} is available")
            return tenant_id

        # If database name already exists, reset tenant_id and try again
        logger.info(f"generate_tenant_id: {tenant_id} already exists")
        tenant_id = None
