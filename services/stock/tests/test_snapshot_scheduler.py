import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument
from app.services.multi_tenant_snapshot_scheduler import MultiTenantSnapshotScheduler


@pytest.fixture
def scheduler():
    """Create a scheduler instance for testing."""
    return MultiTenantSnapshotScheduler()


@pytest.fixture
def sample_schedule():
    """Create a sample schedule document."""
    return SnapshotScheduleDocument(
        tenant_id="test_tenant",
        enabled=True,
        schedule_interval="daily",
        schedule_hour=2,
        schedule_minute=0,
        retention_days=30,
        target_stores=["all"],
    )


@pytest.mark.asyncio
async def test_create_cron_trigger_daily(scheduler):
    """Test creating daily cron trigger."""
    schedule = SnapshotScheduleDocument(
        tenant_id="test", schedule_interval="daily", schedule_hour=3, schedule_minute=15
    )

    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is not None
    # Check the trigger has the correct type
    assert trigger.__class__.__name__ == "CronTrigger"


@pytest.mark.asyncio
async def test_create_cron_trigger_weekly(scheduler):
    """Test creating weekly cron trigger."""
    schedule = SnapshotScheduleDocument(
        tenant_id="test",
        schedule_interval="weekly",
        schedule_hour=4,
        schedule_minute=30,
        schedule_day_of_week=1,  # Tuesday
    )

    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is not None
    assert trigger.__class__.__name__ == "CronTrigger"


@pytest.mark.asyncio
async def test_create_cron_trigger_monthly(scheduler):
    """Test creating monthly cron trigger."""
    schedule = SnapshotScheduleDocument(
        tenant_id="test", schedule_interval="monthly", schedule_hour=5, schedule_minute=45, schedule_day_of_month=15
    )

    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is not None
    assert trigger.__class__.__name__ == "CronTrigger"


@pytest.mark.asyncio
async def test_create_cron_trigger_invalid_interval(scheduler):
    """Test creating cron trigger with invalid interval."""
    schedule = SnapshotScheduleDocument(
        tenant_id="test", schedule_interval="invalid", schedule_hour=0, schedule_minute=0
    )

    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is None


@pytest.mark.asyncio
async def test_update_tenant_schedule_enabled(scheduler, sample_schedule):
    """Test updating tenant schedule when enabled."""
    # Mock dependencies
    scheduler.get_db_func = AsyncMock()
    scheduler.scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "job_id"
    mock_job.next_run_time = datetime.now(timezone.utc) + timedelta(hours=1)
    scheduler.scheduler.add_job.return_value = mock_job

    with patch("app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo

        # Mock update to avoid id issue
        mock_repo.update = AsyncMock()

        # Mock the StockSnapshotRepository import that happens inside the method
        with patch(
            "app.models.repositories.stock_snapshot_repository.StockSnapshotRepository"
        ) as mock_snapshot_repo_class:
            mock_snapshot_repo = AsyncMock()
            mock_snapshot_repo_class.return_value = mock_snapshot_repo

            await scheduler.update_tenant_schedule(sample_schedule)

    # Verify job was added
    scheduler.scheduler.add_job.assert_called_once()
    assert "test_tenant" in scheduler.tenant_jobs

    # Verify TTL index was set up (update might not be called if no id)
    mock_snapshot_repo.ensure_ttl_index.assert_called_once_with(30)


@pytest.mark.asyncio
async def test_update_tenant_schedule_disabled(scheduler, sample_schedule):
    """Test updating tenant schedule when disabled."""
    sample_schedule.enabled = False
    scheduler.tenant_jobs = {"test_tenant": "old_job"}
    scheduler.scheduler = MagicMock()

    await scheduler.update_tenant_schedule(sample_schedule)

    # Verify old job was removed
    scheduler.scheduler.remove_job.assert_called_once_with("old_job")
    assert "test_tenant" not in scheduler.tenant_jobs


@pytest.mark.asyncio
async def test_remove_tenant_schedule(scheduler):
    """Test removing tenant schedule."""
    scheduler.tenant_jobs = {"test_tenant": "job_id"}
    scheduler.scheduler = MagicMock()

    await scheduler.remove_tenant_schedule("test_tenant")

    scheduler.scheduler.remove_job.assert_called_once_with("job_id")
    assert "test_tenant" not in scheduler.tenant_jobs


@pytest.mark.asyncio
async def test_get_all_tenant_ids(scheduler):
    """Test getting all tenant IDs from database."""
    with patch("motor.motor_asyncio.AsyncIOMotorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.list_database_names.return_value = [
            "admin",
            "config",
            "db_stock_tenant1",
            "db_stock_tenant2",
            "other_db",
        ]

        tenant_ids = await scheduler._get_all_tenant_ids()

        assert len(tenant_ids) == 2
        assert "tenant1" in tenant_ids
        assert "tenant2" in tenant_ids


@pytest.mark.asyncio
async def test_get_target_stores_all(scheduler):
    """Test getting all stores for a tenant."""
    scheduler.get_db_func = AsyncMock()
    mock_db = MagicMock()
    scheduler.get_db_func.return_value = mock_db

    # Create a mock async cursor
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = [{"store_code": "store1"}, {"store_code": "store2"}, {"store_code": "store3"}]

    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db.__getitem__.return_value = mock_collection

    stores = await scheduler._get_target_stores("test_tenant", ["all"])

    assert len(stores) == 3
    assert "store1" in stores
    assert "store2" in stores
    assert "store3" in stores


@pytest.mark.asyncio
async def test_get_target_stores_specific(scheduler):
    """Test getting specific stores."""
    stores = await scheduler._get_target_stores("test_tenant", ["store1", "store2"])

    assert len(stores) == 2
    assert "store1" in stores
    assert "store2" in stores


def test_get_status(scheduler):
    """Test getting scheduler status."""
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = True
    scheduler.tenant_jobs = {"tenant1": "job1", "tenant2": "job2"}

    status = scheduler.get_status()

    assert status["running"] is True
    assert status["active_jobs"] == 2
    assert "tenant1" in status["tenant_jobs"]
    assert "tenant2" in status["tenant_jobs"]


def test_shutdown(scheduler):
    """Test scheduler shutdown."""
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = True

    scheduler.shutdown()

    scheduler.scheduler.shutdown.assert_called_once()
