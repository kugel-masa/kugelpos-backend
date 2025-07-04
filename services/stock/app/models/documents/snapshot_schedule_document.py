from datetime import datetime
from typing import List, Optional

from bson import ObjectId

from kugel_common.models.documents.abstract_document import AbstractDocument


class SnapshotScheduleDocument(AbstractDocument):
    """Document model for tenant-specific snapshot schedule configuration."""

    tenant_id: str
    enabled: bool = True
    schedule_interval: str  # "daily", "weekly", "monthly"
    schedule_hour: int  # 0-23
    schedule_minute: int = 0  # 0-59
    schedule_day_of_week: Optional[int] = None  # 0-6 (for weekly, 0=Monday)
    schedule_day_of_month: Optional[int] = None  # 1-31 (for monthly)
    retention_days: int = 30
    target_stores: List[str] = ["all"]  # ["all"] or specific store codes
    last_executed_at: Optional[datetime] = None
    next_execution_at: Optional[datetime] = None
    created_by: str = "system"
    updated_by: str = "system"

    class Settings:
        name = "snapshot_schedules"
        indexes = [
            {
                "keys": [("tenant_id", 1)],
                "unique": True,
            }
        ]
