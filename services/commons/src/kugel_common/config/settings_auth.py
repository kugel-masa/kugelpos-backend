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
Authentication settings configuration

This module defines authentication-related settings such as JWT token configuration,
encryption algorithms, and authentication endpoints.
"""
from pydantic_settings import BaseSettings

class AuthSettings(BaseSettings):
    """
    Authentication settings class
    
    Contains configuration for authentication and authorization mechanisms
    used across the application, particularly for JWT token generation and validation.
    
    Attributes:
        SECRET_KEY: Secret key used for JWT token signing (should be overridden in production)
        ALGORITHM: JWT signing algorithm
        TOKEN_URL: URL endpoint for token generation
        TOKEN_EXPIRE_MINUTES: JWT token expiration time in minutes
        PUBSUB_NOTIFY_API_KEY: API key for Pub/Sub notifications
    """
    SECRET_KEY: str = "test-secret-key-for-development-only"  # Override with environment variable in production
    ALGORITHM: str = "HS256"
    TOKEN_URL: str = "http://localhost:8000/api/v1/accounts/token"
    TOKEN_EXPIRE_MINUTES: int = 30
    PUBSUB_NOTIFY_API_KEY: str = "test-api-key-for-development-only"  # Override with environment variable in production