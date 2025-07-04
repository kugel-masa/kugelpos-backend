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
"""
Service-to-service authentication utilities

This module provides JWT token generation for internal service communication.
All services share the same SECRET_KEY, allowing them to generate and validate
tokens for inter-service API calls.
"""
from datetime import datetime, timedelta, timezone
from jose import jwt
from logging import getLogger

from kugel_common.config.settings import settings

logger = getLogger(__name__)

def create_service_token(
    tenant_id: str,
    service_name: str,
    expires_delta: timedelta = None
) -> str:
    """
    Create a JWT token for service-to-service authentication.
    
    This function generates a JWT token that can be used by the report service
    to authenticate with other services (like journal service). The token includes
    the tenant_id and identifies the calling service.
    
    Args:
        tenant_id: The tenant identifier
        service_name: Name of the service creating the token (default: "report-service")
        expires_delta: Optional custom expiration time (default: 5 minutes)
        
    Returns:
        str: The encoded JWT token
    """
    # Token payload
    data = {
        "sub": f"service:{service_name}",  # Subject identifies this as a service account
        "tenant_id": tenant_id,
        "service": service_name,
        "is_service_account": True,  # Flag to identify service-to-service calls
        "is_superuser": False,  # Services are not superusers
    }
    
    # Set expiration (default 5 minutes for service tokens)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    data.update({"exp": expire})
    
    # Create the token using the shared secret key
    encoded_jwt = jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    logger.debug(f"Created service token for tenant {tenant_id} from {service_name}")
    
    return encoded_jwt