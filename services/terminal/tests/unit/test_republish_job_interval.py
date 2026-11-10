"""The terminal republish job runs at the configured interval, whatever its value.

It was scheduled with ``CronTrigger(minute=f"*/{interval}")``. The cron minute
field only spans 0-59, so ``UNDELIVERED_CHECK_INTERVAL_IN_MINUTES`` of 60 or more
raised ``ValueError`` inside the startup handler and the service exited. A value
that does not divide 60 (7, 45) fired at uneven gaps, because the step restarts at
the top of every hour.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.cron import republish_undelivery_message as job_module

JOB_ID = "republish_undelivered_terminallog"


@pytest_asyncio.fixture
async def fresh_scheduler(monkeypatch):
    """Swap the module's global scheduler for one this test owns, and shut it down
    while the test's event loop is still running."""
    scheduler = AsyncIOScheduler()
    monkeypatch.setattr(job_module, "scheduler", scheduler)
    yield scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("minutes", [5, 7, 45, 60, 90, 120])
async def test_job_registers_and_keeps_an_even_interval(fresh_scheduler, monkeypatch, minutes):
    monkeypatch.setattr(job_module.settings, "UNDELIVERED_CHECK_INTERVAL_IN_MINUTES", minutes)

    await job_module.start_republish_undelivered_terminallog_job()

    job = fresh_scheduler.get_job(JOB_ID)
    assert job is not None, "the republish job was not registered"

    # Every gap between consecutive runs is the configured interval. Walk at
    # least three hours so the run crosses the top of the hour more than once.
    fire = job.next_run_time
    for _ in range(max(5, 180 // minutes + 1)):
        following = job.trigger.get_next_fire_time(fire, fire)
        assert following - fire == timedelta(minutes=minutes)
        fire = following


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", [0, -1])
async def test_non_positive_interval_falls_back_to_five_minutes(fresh_scheduler, monkeypatch, configured):
    monkeypatch.setattr(job_module.settings, "UNDELIVERED_CHECK_INTERVAL_IN_MINUTES", configured)

    await job_module.start_republish_undelivered_terminallog_job()

    job = fresh_scheduler.get_job(JOB_ID)
    assert job.trigger.interval == timedelta(minutes=5)
