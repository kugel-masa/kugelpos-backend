import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config.settings import settings
from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument
from app.repositories.snapshot_schedule_repository import SnapshotScheduleRepository
from app.services.snapshot_service import SnapshotService
from logging import getLogger


logger = getLogger(__name__)


class MultiTenantSnapshotScheduler:
    """Manages snapshot schedules for multiple tenants."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.tenant_jobs: Dict[str, str] = {}  # {tenant_id: job_id}
        self.logger = logger
        self._lock = asyncio.Lock()  # For thread-safe operations

    async def initialize(self, get_db_func):
        """Initialize scheduler with all tenant schedules."""
        self.get_db_func = get_db_func

        try:
            # Get all tenant IDs from the system
            tenant_ids = await self._get_all_tenant_ids()

            for tenant_id in tenant_ids:
                try:
                    db = await self.get_db_func(tenant_id)
                    repo = SnapshotScheduleRepository(db)
                    schedule = await repo.get_by_tenant_id(tenant_id)

                    if schedule and schedule.enabled:
                        await self.update_tenant_schedule(schedule)
                except Exception as e:
                    self.logger.error(f"Failed to initialize schedule for tenant {tenant_id}: {e}")

            self.scheduler.start()
            self.logger.info(f"Snapshot scheduler initialized with {len(self.tenant_jobs)} active jobs")

        except Exception as e:
            self.logger.error(f"Failed to initialize snapshot scheduler: {e}")
            raise

    async def update_tenant_schedule(self, schedule: SnapshotScheduleDocument):
        """Update or create a schedule for a specific tenant."""
        async with self._lock:
            tenant_id = schedule.tenant_id

            # Remove existing job if any
            if tenant_id in self.tenant_jobs:
                try:
                    self.scheduler.remove_job(self.tenant_jobs[tenant_id])
                    del self.tenant_jobs[tenant_id]
                except Exception as e:
                    self.logger.warning(f"Failed to remove existing job for tenant {tenant_id}: {e}")

            # If schedule is disabled, don't create a new job
            if not schedule.enabled:
                self.logger.info(f"Schedule disabled for tenant {tenant_id}")
                return

            # Create cron trigger based on schedule interval
            trigger = self._create_cron_trigger(schedule)

            if trigger:
                # Add new job
                job = self.scheduler.add_job(
                    self._execute_tenant_snapshot,
                    trigger=trigger,
                    args=[tenant_id, schedule],
                    id=f"snapshot_{tenant_id}",
                    name=f"Snapshot for tenant {tenant_id}",
                    replace_existing=True,
                    misfire_grace_time=3600,  # 1 hour grace time
                )

                self.tenant_jobs[tenant_id] = job.id
                self.logger.info(
                    f"Scheduled snapshot job for tenant {tenant_id}: {schedule.schedule_interval} at {schedule.schedule_hour:02d}:{schedule.schedule_minute:02d}"
                )

                # Update next execution time in the schedule
                next_run = job.next_run_time
                if next_run:
                    db = await self.get_db_func(tenant_id)
                    repo = SnapshotScheduleRepository(db)
                    schedule.next_execution_at = next_run
                    # Only update if schedule has an id (i.e., it exists in DB)
                    if hasattr(schedule, "id") and schedule.id:
                        await repo.update_one_async(
                            {"tenant_id": tenant_id}, {"last_executed_at": schedule.last_executed_at}
                        )

                # Setup TTL index for snapshots with the configured retention days
                from app.models.repositories.stock_snapshot_repository import StockSnapshotRepository

                ttl_db = await self.get_db_func(tenant_id)
                snapshot_repo = StockSnapshotRepository(ttl_db)
                await snapshot_repo.ensure_ttl_index(schedule.retention_days)

    async def remove_tenant_schedule(self, tenant_id: str):
        """Remove schedule for a specific tenant."""
        async with self._lock:
            if tenant_id in self.tenant_jobs:
                try:
                    self.scheduler.remove_job(self.tenant_jobs[tenant_id])
                    del self.tenant_jobs[tenant_id]
                    self.logger.info(f"Removed snapshot schedule for tenant {tenant_id}")
                except Exception as e:
                    self.logger.error(f"Failed to remove schedule for tenant {tenant_id}: {e}")

    def _create_cron_trigger(self, schedule: SnapshotScheduleDocument) -> Optional[CronTrigger]:
        """Create a cron trigger based on schedule configuration."""
        try:
            if schedule.schedule_interval == "daily":
                return CronTrigger(hour=schedule.schedule_hour, minute=schedule.schedule_minute)
            elif schedule.schedule_interval == "weekly":
                day_of_week = schedule.schedule_day_of_week if schedule.schedule_day_of_week is not None else 0
                return CronTrigger(
                    day_of_week=day_of_week, hour=schedule.schedule_hour, minute=schedule.schedule_minute
                )
            elif schedule.schedule_interval == "monthly":
                day = schedule.schedule_day_of_month if schedule.schedule_day_of_month is not None else 1
                return CronTrigger(day=day, hour=schedule.schedule_hour, minute=schedule.schedule_minute)
            else:
                self.logger.error(f"Invalid schedule interval: {schedule.schedule_interval}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to create cron trigger: {e}")
            return None

    async def _execute_tenant_snapshot(self, tenant_id: str, schedule: SnapshotScheduleDocument):
        """Execute snapshot creation for a specific tenant."""
        lock_key = f"snapshot_lock_{tenant_id}_{datetime.now().strftime('%Y%m%d%H')}"

        # Simple in-memory lock for now (can be replaced with distributed lock)
        if hasattr(self, "_execution_locks"):
            if lock_key in self._execution_locks:
                self.logger.warning(f"Snapshot already running for tenant {tenant_id}")
                return
        else:
            self._execution_locks = set()

        self._execution_locks.add(lock_key)

        try:
            self.logger.info(f"Starting scheduled snapshot for tenant {tenant_id}")

            db = await self.get_db_func(tenant_id)
            snapshot_service = SnapshotService(db)

            # Get target stores
            stores = await self._get_target_stores(tenant_id, schedule.target_stores)

            # Create snapshots for each store
            success_count = 0
            error_count = 0

            for store_code in stores:
                try:
                    await snapshot_service.create_snapshot_async(
                        tenant_id=tenant_id, store_code=store_code, created_by="scheduled_system"
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Failed to create snapshot for tenant {tenant_id}, store {store_code}: {e}")

            # Update last execution time
            try:
                repo = SnapshotScheduleRepository(db)
                schedule.last_executed_at = datetime.now(timezone.utc)
                await repo.update_one_async({"tenant_id": tenant_id}, {"last_executed_at": schedule.last_executed_at})
            except Exception as e:
                self.logger.error(f"Failed to update last execution time for tenant {tenant_id}: {e}")

            self.logger.info(
                f"Completed scheduled snapshot for tenant {tenant_id}: {success_count} success, {error_count} errors"
            )

        except Exception as e:
            self.logger.error(f"Failed to execute snapshot for tenant {tenant_id}: {e}")
        finally:
            self._execution_locks.discard(lock_key)

    async def _get_all_tenant_ids(self) -> List[str]:
        """Get all tenant IDs from the system."""
        # This is a simplified implementation
        # In production, this would query a central tenant registry
        # For now, we'll get unique tenant_ids from all databases
        try:
            # Get admin database connection
            from motor.motor_asyncio import AsyncIOMotorClient

            client = AsyncIOMotorClient(settings.MONGODB_URI)

            # List all databases
            db_list = await client.list_database_names()

            # Extract tenant IDs from database names
            tenant_ids = []
            prefix = f"{settings.DB_NAME_PREFIX}_"

            for db_name in db_list:
                if db_name.startswith(prefix):
                    tenant_id = db_name[len(prefix) :]
                    if tenant_id and tenant_id not in ["admin", "config", "local"]:
                        tenant_ids.append(tenant_id)

            return tenant_ids

        except Exception as e:
            self.logger.error(f"Failed to get tenant IDs: {e}")
            return []

    async def _get_target_stores(self, tenant_id: str, target_stores: List[str]) -> List[str]:
        """Get list of stores to create snapshots for."""
        if "all" in target_stores:
            # Get all stores for the tenant
            try:
                db = await self.get_db_func(tenant_id)
                # Query stores collection to get all store codes
                stores_collection = db["stores"]
                stores = await stores_collection.find({}, {"store_code": 1}).to_list(None)
                return [store["store_code"] for store in stores if "store_code" in store]
            except Exception as e:
                self.logger.error(f"Failed to get stores for tenant {tenant_id}: {e}")
                return []
        else:
            # Return specific stores
            return target_stores

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.logger.info("Snapshot scheduler shutdown completed")

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.scheduler.running,
            "active_jobs": len(self.tenant_jobs),
            "tenant_jobs": list(self.tenant_jobs.keys()),
        }
