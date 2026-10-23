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
from logging import getLogger

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)

#: Values of SECRET_KEY / PUBSUB_NOTIFY_API_KEY that are published in this
#: repository: the code defaults, the .env.sample placeholders and the
#: quick_start.sh exports. Anyone can read them, so a service holding one of
#: them accepts tokens and notifications that anyone can make (issue #132).
PUBLISHED_SECRET_VALUES = frozenset(
    {
        "test-secret-key-for-development-only",
        "test-api-key-for-development-only",
        "your_secret_key",
        "your_pubsub_notify_api_key",
        "dev-secret-key-123456789",
        "dev-api-key-123456789",
    }
)


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
        ALLOW_INSECURE_DEV_SECRETS: Let the service start with an empty or
            published SECRET_KEY / PUBSUB_NOTIFY_API_KEY. For the development
            stack and the tests only
    """
    SECRET_KEY: str = "test-secret-key-for-development-only"  # Development only; see ALLOW_INSECURE_DEV_SECRETS
    ALGORITHM: str = "HS256"
    TOKEN_URL: str = "http://localhost:8000/api/v1/accounts/token"
    TOKEN_EXPIRE_MINUTES: int = 30
    PUBSUB_NOTIFY_API_KEY: str = "test-api-key-for-development-only"  # Development only; see ALLOW_INSECURE_DEV_SECRETS
    TERMINAL_TOKEN_EXPIRE_HOURS: int = 24
    ALLOW_INSECURE_DEV_SECRETS: bool = False

    # A settings error reports the values it was given; these include the secrets.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    @model_validator(mode="after")
    def _refuse_published_secrets(self):
        """Refuse to start on a secret anyone can read (issue #132).

        SECRET_KEY signs and verifies every user, terminal and service JWT
        (HS256, so knowing it is enough to forge one, superuser claims
        included). PUBSUB_NOTIFY_API_KEY is accepted in place of any
        terminal's API key. A service holding a value published in this
        repository, or an empty one, is therefore open to anyone, and nothing
        about it looks wrong until it is abused: the failure belongs at startup.

        An empty value in the environment does not reach here as empty:
        ``env_ignore_empty`` falls back to the default, which is published, so
        a blank ``SECRET_KEY=`` copied from a .env.sample is refused too.

        Declared on the model rather than on the fields so that it still runs
        when a subclass redefines one of them (stock declares its own
        PUBSUB_NOTIFY_API_KEY, with an empty default).
        """
        insecure = [
            name
            for name in ("SECRET_KEY", "PUBSUB_NOTIFY_API_KEY")
            if not getattr(self, name).strip() or getattr(self, name) in PUBLISHED_SECRET_VALUES
        ]
        if not insecure:
            return self
        if self.ALLOW_INSECURE_DEV_SECRETS:
            logger.warning(
                f"Running with an empty or published {' and '.join(insecure)}: "
                "allowed by ALLOW_INSECURE_DEV_SECRETS, which only the development stack and the tests may set"
            )
            return self
        raise ValueError(
            f"{' and '.join(insecure)} {'is' if len(insecure) == 1 else 'are'} empty or a value published in the repository, "
            "so anyone could forge tokens or notifications this service accepts. "
            "Set each to a secret of your own, the same in every service, for example "
            "the output of: python -c 'import secrets; print(secrets.token_urlsafe(48))'. "
            "For the development stack and the tests only, ALLOW_INSECURE_DEV_SECRETS=true lets it start."
        )