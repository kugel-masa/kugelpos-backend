# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class CartSettings(BaseSettings):
    # undelivered check interval in minutes
    UNDELIVERED_CHECK_INTERVAL_IN_MINUTES: int = 5
    # undelivered check period in hours
    UNDELIVERED_CHECK_PERIOD_IN_HOURS: int = 24
    # undelivered check failed period in minutes
    UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES: int = 15

    # debug mode
    DEBUG: str = "false"
    # This port is used for debugging purposes
    DEBUG_PORT: int = 5678

    # Terminal info cache TTL in seconds (default: 5 minutes)
    TERMINAL_CACHE_TTL_SECONDS: int = 300
    # Use terminal cache to avoid frequent database queries
    USE_TERMINAL_CACHE: bool = True

    # gRPC settings
    USE_GRPC: bool = Field(default=False, description="Use gRPC for master-data communication")
    GRPC_TIMEOUT: float = Field(default=5.0, description="gRPC request timeout in seconds")
    MASTER_DATA_GRPC_URL: str = Field(
        default="master-data:50051",
        description="Master-data gRPC server URL"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Create settings instance
cart_settings = CartSettings()
