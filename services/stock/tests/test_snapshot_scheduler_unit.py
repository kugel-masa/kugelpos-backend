"""Unit tests for MultiTenantSnapshotScheduler — covers paths not exercised
by the existing test_snapshot_scheduler.py (initialize, _execute_tenant_snapshot,
edge-case branches, exception paths).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument
from app.services.multi_tenant_snapshot_scheduler import MultiTenantSnapshotScheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scheduler():
    return MultiTenantSnapshotScheduler()


@pytest.fixture
def daily_schedule():
    return SnapshotScheduleDocument(
        tenant_id="t1",
        enabled=True,
        schedule_interval="daily",
        schedule_hour=2,
        schedule_minute=0,
        retention_days=30,
        target_stores=["all"],
    )


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_loads_enabled_schedules(scheduler):
    """initialize should load enabled schedules and start the scheduler."""
    schedule = SnapshotScheduleDocument(
        tenant_id="t1", enabled=True, schedule_interval="daily",
        schedule_hour=1, schedule_minute=0,
    )
    mock_db = MagicMock()
    get_db = AsyncMock(return_value=mock_db)

    with patch.object(scheduler, "_get_all_tenant_ids", return_value=["t1"]):
        with patch(
            "app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository"
        ) as MockRepo:
            repo_inst = AsyncMock()
            repo_inst.get_by_tenant_id.return_value = schedule
            MockRepo.return_value = repo_inst

            with patch.object(scheduler, "update_tenant_schedule", new_callable=AsyncMock) as mock_update:
                scheduler.scheduler = MagicMock()
                await scheduler.initialize(get_db)

                mock_update.assert_called_once_with(schedule)
                scheduler.scheduler.start.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_skips_disabled_schedules(scheduler):
    """initialize should skip disabled schedules."""
    schedule = SnapshotScheduleDocument(
        tenant_id="t1", enabled=False, schedule_interval="daily",
        schedule_hour=1, schedule_minute=0,
    )
    mock_db = MagicMock()
    get_db = AsyncMock(return_value=mock_db)

    with patch.object(scheduler, "_get_all_tenant_ids", return_value=["t1"]):
        with patch(
            "app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository"
        ) as MockRepo:
            repo_inst = AsyncMock()
            repo_inst.get_by_tenant_id.return_value = schedule
            MockRepo.return_value = repo_inst

            with patch.object(scheduler, "update_tenant_schedule", new_callable=AsyncMock) as mock_update:
                scheduler.scheduler = MagicMock()
                await scheduler.initialize(get_db)

                mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_skips_none_schedule(scheduler):
    """initialize should skip tenants with no schedule."""
    mock_db = MagicMock()
    get_db = AsyncMock(return_value=mock_db)

    with patch.object(scheduler, "_get_all_tenant_ids", return_value=["t1"]):
        with patch(
            "app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository"
        ) as MockRepo:
            repo_inst = AsyncMock()
            repo_inst.get_by_tenant_id.return_value = None
            MockRepo.return_value = repo_inst

            with patch.object(scheduler, "update_tenant_schedule", new_callable=AsyncMock) as mock_update:
                scheduler.scheduler = MagicMock()
                await scheduler.initialize(get_db)

                mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_handles_per_tenant_error(scheduler):
    """initialize should continue when one tenant fails."""
    get_db = AsyncMock(side_effect=Exception("db error"))

    with patch.object(scheduler, "_get_all_tenant_ids", return_value=["t1", "t2"]):
        scheduler.scheduler = MagicMock()
        await scheduler.initialize(get_db)
        # Scheduler should still start despite errors
        scheduler.scheduler.start.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_raises_on_fatal_error(scheduler):
    """initialize should raise if _get_all_tenant_ids fails."""
    get_db = AsyncMock()

    with patch.object(scheduler, "_get_all_tenant_ids", side_effect=Exception("fatal")):
        scheduler.scheduler = MagicMock()
        with pytest.raises(Exception, match="fatal"):
            await scheduler.initialize(get_db)


# ---------------------------------------------------------------------------
# _execute_tenant_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_tenant_snapshot_success(scheduler, daily_schedule):
    """_execute_tenant_snapshot should create snapshots for all stores."""
    mock_db = MagicMock()
    scheduler.get_db_func = AsyncMock(return_value=mock_db)

    mock_snapshot_svc = AsyncMock()

    with patch(
        "app.services.multi_tenant_snapshot_scheduler.SnapshotService",
        return_value=mock_snapshot_svc,
    ):
        with patch.object(scheduler, "_get_target_stores", return_value=["s1", "s2"]):
            with patch(
                "app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository"
            ) as MockRepo:
                repo_inst = AsyncMock()
                MockRepo.return_value = repo_inst

                await scheduler._execute_tenant_snapshot("t1", daily_schedule)

    assert mock_snapshot_svc.create_snapshot_async.call_count == 2


@pytest.mark.asyncio
async def test_execute_tenant_snapshot_partial_failure(scheduler, daily_schedule):
    """_execute_tenant_snapshot should continue when one store fails."""
    mock_db = MagicMock()
    scheduler.get_db_func = AsyncMock(return_value=mock_db)

    mock_snapshot_svc = AsyncMock()
    mock_snapshot_svc.create_snapshot_async.side_effect = [
        None,  # store1 OK
        Exception("snapshot error"),  # store2 fails
        None,  # store3 OK
    ]

    with patch(
        "app.services.multi_tenant_snapshot_scheduler.SnapshotService",
        return_value=mock_snapshot_svc,
    ):
        with patch.object(scheduler, "_get_target_stores", return_value=["s1", "s2", "s3"]):
            with patch(
                "app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository"
            ) as MockRepo:
                repo_inst = AsyncMock()
                MockRepo.return_value = repo_inst

                await scheduler._execute_tenant_snapshot("t1", daily_schedule)

    assert mock_snapshot_svc.create_snapshot_async.call_count == 3


@pytest.mark.asyncio
async def test_execute_tenant_snapshot_skips_if_locked(scheduler, daily_schedule):
    """_execute_tenant_snapshot should skip if already running for the same hour."""
    scheduler.get_db_func = AsyncMock()
    lock_key = f"snapshot_lock_t1_{datetime.now().strftime('%Y%m%d%H')}"
    scheduler._execution_locks = {lock_key}

    mock_snapshot_svc = AsyncMock()
    with patch(
        "app.services.multi_tenant_snapshot_scheduler.SnapshotService",
        return_value=mock_snapshot_svc,
    ):
        await scheduler._execute_tenant_snapshot("t1", daily_schedule)

    mock_snapshot_svc.create_snapshot_async.assert_not_called()


@pytest.mark.asyncio
async def test_execute_tenant_snapshot_clears_lock_on_error(scheduler, daily_schedule):
    """_execute_tenant_snapshot should release the lock even on unexpected error."""
    scheduler.get_db_func = AsyncMock(side_effect=Exception("db down"))

    await scheduler._execute_tenant_snapshot("t1", daily_schedule)

    # Lock should be released
    lock_key = f"snapshot_lock_t1_{datetime.now().strftime('%Y%m%d%H')}"
    assert lock_key not in scheduler._execution_locks


@pytest.mark.asyncio
async def test_execute_tenant_snapshot_update_last_executed_error(scheduler, daily_schedule):
    """_execute_tenant_snapshot should handle error updating last_executed_at."""
    mock_db = MagicMock()
    scheduler.get_db_func = AsyncMock(return_value=mock_db)

    mock_snapshot_svc = AsyncMock()

    with patch(
        "app.services.multi_tenant_snapshot_scheduler.SnapshotService",
        return_value=mock_snapshot_svc,
    ):
        with patch.object(scheduler, "_get_target_stores", return_value=["s1"]):
            with patch(
                "app.services.multi_tenant_snapshot_scheduler.SnapshotScheduleRepository"
            ) as MockRepo:
                repo_inst = AsyncMock()
                repo_inst.update_one_async.side_effect = Exception("update failed")
                MockRepo.return_value = repo_inst

                # Should not raise
                await scheduler._execute_tenant_snapshot("t1", daily_schedule)


# ---------------------------------------------------------------------------
# remove_tenant_schedule edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_tenant_schedule_not_found(scheduler):
    """remove_tenant_schedule should be a no-op when tenant has no job."""
    scheduler.scheduler = MagicMock()
    await scheduler.remove_tenant_schedule("nonexistent")
    scheduler.scheduler.remove_job.assert_not_called()


@pytest.mark.asyncio
async def test_remove_tenant_schedule_error(scheduler):
    """remove_tenant_schedule should handle errors from scheduler.remove_job."""
    scheduler.tenant_jobs = {"t1": "job1"}
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.remove_job.side_effect = Exception("remove error")

    await scheduler.remove_tenant_schedule("t1")
    # Should not raise; error is logged


# ---------------------------------------------------------------------------
# _create_cron_trigger edge cases
# ---------------------------------------------------------------------------

def test_create_cron_trigger_weekly_default_day(scheduler):
    """Weekly schedule with no day_of_week should default to 0 (Monday)."""
    schedule = SnapshotScheduleDocument(
        tenant_id="t1", schedule_interval="weekly",
        schedule_hour=3, schedule_minute=0,
        schedule_day_of_week=None,
    )
    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is not None


def test_create_cron_trigger_monthly_default_day(scheduler):
    """Monthly schedule with no day_of_month should default to 1."""
    schedule = SnapshotScheduleDocument(
        tenant_id="t1", schedule_interval="monthly",
        schedule_hour=3, schedule_minute=0,
        schedule_day_of_month=None,
    )
    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is not None


def test_create_cron_trigger_exception(scheduler):
    """_create_cron_trigger should return None on unexpected exception."""
    schedule = MagicMock()
    schedule.schedule_interval = "daily"
    schedule.schedule_hour = "not_a_number"  # will cause CronTrigger to raise
    schedule.schedule_minute = "bad"

    trigger = scheduler._create_cron_trigger(schedule)
    assert trigger is None


# ---------------------------------------------------------------------------
# _get_all_tenant_ids edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_tenant_ids_exception(scheduler):
    """_get_all_tenant_ids should return [] on exception."""
    with patch("motor.motor_asyncio.AsyncIOMotorClient") as MockClient:
        MockClient.side_effect = Exception("connection refused")
        result = await scheduler._get_all_tenant_ids()
        assert result == []


@pytest.mark.asyncio
async def test_get_all_tenant_ids_filters_system_dbs(scheduler):
    """_get_all_tenant_ids should filter out admin/config/local suffixes."""
    with patch("motor.motor_asyncio.AsyncIOMotorClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client
        mock_client.list_database_names.return_value = [
            "db_stock_admin", "db_stock_config", "db_stock_local",
            "db_stock_real_tenant", "unrelated_db",
        ]
        result = await scheduler._get_all_tenant_ids()
        assert result == ["real_tenant"]


# ---------------------------------------------------------------------------
# _get_target_stores edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_target_stores_all_exception(scheduler):
    """_get_target_stores should return [] when DB query fails."""
    scheduler.get_db_func = AsyncMock(side_effect=Exception("db error"))
    result = await scheduler._get_target_stores("t1", ["all"])
    assert result == []


# ---------------------------------------------------------------------------
# shutdown edge case
# ---------------------------------------------------------------------------

def test_shutdown_not_running(scheduler):
    """shutdown should be a no-op when scheduler is not running."""
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = False
    scheduler.shutdown()
    scheduler.scheduler.shutdown.assert_not_called()
