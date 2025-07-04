from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository


class SnapshotScheduleRepository(AbstractRepository[SnapshotScheduleDocument]):
    """Repository for managing snapshot schedule documents."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__("snapshot_schedules", SnapshotScheduleDocument, db)

    async def get_by_tenant_id(self, tenant_id: str) -> Optional[SnapshotScheduleDocument]:
        """Get snapshot schedule for a specific tenant."""
        return await self.get_one_async({"tenant_id": tenant_id})

    async def get_all_enabled_schedules(self) -> list[SnapshotScheduleDocument]:
        """Get all enabled snapshot schedules."""
        return await self.get_list_async({"enabled": True})

    async def upsert_schedule(self, schedule: SnapshotScheduleDocument) -> SnapshotScheduleDocument:
        """Create or update a snapshot schedule for a tenant."""
        existing = await self.get_by_tenant_id(schedule.tenant_id)

        if existing:
            # Update existing schedule
            schedule.created_at = existing.created_at
            schedule.created_by = existing.created_by
            # Update document
            await self.update_one_async(
                {"tenant_id": schedule.tenant_id}, schedule.model_dump(by_alias=True, exclude={"id"})
            )
            return schedule
        else:
            # Create new schedule
            await self.create_async(schedule)
            return schedule
