from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SnapshotScheduleBase(BaseModel):
    """Base schema for snapshot schedule."""

    enabled: bool = True
    schedule_interval: str = Field(..., description="Schedule interval: daily, weekly, monthly")
    schedule_hour: int = Field(..., ge=0, le=23, description="Execution hour (0-23)")
    schedule_minute: int = Field(0, ge=0, le=59, description="Execution minute (0-59)")
    schedule_day_of_week: Optional[int] = Field(
        None, ge=0, le=6, description="Day of week for weekly schedule (0=Monday, 6=Sunday)"
    )
    schedule_day_of_month: Optional[int] = Field(
        None, ge=1, le=31, description="Day of month for monthly schedule (1-31)"
    )
    retention_days: int = Field(30, ge=1, description="Snapshot retention days")
    target_stores: List[str] = Field(["all"], description="Target stores: ['all'] or specific store codes")

    @field_validator("schedule_interval")
    def validate_interval(cls, v):
        if v not in ["daily", "weekly", "monthly"]:
            raise ValueError("schedule_interval must be one of: daily, weekly, monthly")
        return v

    @field_validator("target_stores")
    def validate_target_stores(cls, v):
        if not v:
            raise ValueError("target_stores must not be empty")
        return v


class SnapshotScheduleCreate(SnapshotScheduleBase):
    """Schema for creating/updating snapshot schedule."""

    pass


class SnapshotScheduleResponse(SnapshotScheduleBase):
    """Schema for snapshot schedule response."""

    tenant_id: str
    last_executed_at: Optional[datetime] = None
    next_execution_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True
