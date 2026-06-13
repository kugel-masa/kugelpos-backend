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

    # Master-data cache (shared via Dapr state store, backed by Redis).
    # Read by AbstractMasterDataRepository and its subclasses.
    MASTER_DATA_CACHE_ENABLED: bool = Field(
        default=True,
        description="Global switch for the master-data cache layer; False bypasses cache and always fetches.",
    )
    MASTER_DATA_CACHE_STATE_STORE: str = Field(
        default="masterstore",
        description="Dapr state-store component name for master-data cache.",
    )
    MASTER_DATA_CACHE_TTL_SECONDS: int = Field(
        default=300,
        description="Fallback TTL when a namespace-specific TTL is not set.",
    )
    ITEM_MASTER_CACHE_TTL_SECONDS: int = Field(default=300, description="Item master cache TTL in seconds.")
    PAYMENT_MASTER_CACHE_TTL_SECONDS: int = Field(default=600, description="Payment master cache TTL in seconds.")
    PROMOTION_MASTER_CACHE_TTL_SECONDS: int = Field(default=60, description="Promotion master cache TTL in seconds.")
    SETTINGS_MASTER_CACHE_TTL_SECONDS: int = Field(default=600, description="Settings master cache TTL in seconds.")
    TAX_MASTER_CACHE_TTL_SECONDS: int = Field(default=3600, description="Tax master cache TTL in seconds.")

    # Signed cart snapshot (client-carried cart phase 1, issue #148).
    # Format: "<kid>:<base64 key>[,<kid>:<base64 key>...]". The first entry is the
    # current signing key; the rest are previous generations accepted for verification
    # only (rotation grace). Empty means the snapshot feature runs degraded: cart
    # responses carry no snapshot and the restore API rejects all envelopes.
    SNAPSHOT_HMAC_KEYS: str = Field(
        default="",
        description="HMAC keys for cart snapshot signing as 'kid:base64key' CSV; first entry signs, the rest verify.",
    )
    SNAPSHOT_SIZE_WARN_BYTES: int = Field(
        default=262144,
        description="Raw snapshot size threshold in bytes that triggers a warning log.",
    )

    # Client-carried cart phase 2 (issue #156).
    # Per-request snapshot handling mode (service-wide migration switch):
    #   DUAL     - accept both: a request carrying a snapshot is processed
    #              statelessly (snapshot authoritative, cache not consulted);
    #              a request without a snapshot falls back to the phase 1
    #              cache-authoritative path. Lets phase 1/2 clients coexist.
    #   REQUIRED - reject snapshot-less mutating requests with a dedicated error
    #              (post-migration; cache no longer the authority).
    # The presence/absence branching is automatic per request; this setting only
    # controls whether the snapshot-less path is permitted.
    CART_REQUEST_SNAPSHOT_MODE: str = Field(
        default="DUAL",
        description="Per-request snapshot mode: 'DUAL' (accept snapshot-less) or 'REQUIRED' (reject snapshot-less).",
    )
    # Max decompressed request-body size (bytes) for the request-decompression
    # middleware; bodies exceeding this are rejected before being fully expanded
    # (zip-bomb guard). Kept in line with SNAPSHOT_SIZE_WARN_BYTES.
    REQUEST_DECOMPRESS_MAX_BYTES: int = Field(
        default=1048576,
        description="Maximum decompressed request body size in bytes; larger is rejected (zip-bomb guard).",
    )

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
