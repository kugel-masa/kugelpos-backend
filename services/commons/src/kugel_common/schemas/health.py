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

"""Health check response models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class HealthStatus(str, Enum):
    """Health status enumeration."""
    
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Individual component health status."""
    
    status: HealthStatus = Field(..., description="Health status of the component")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details about the component")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    component: Optional[str] = Field(None, description="Component name (for Dapr components)")


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    model_config = ConfigDict()
    
    status: HealthStatus = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Health check timestamp")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    checks: Dict[str, ComponentHealth] = Field(default_factory=dict, description="Individual component health checks")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info) -> str:
        """Serialize timestamp to ISO format with Z suffix."""
        return timestamp.isoformat() + "Z"