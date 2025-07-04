# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
This script is used to republish undelivered terminallog messages.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import asyncio
from logging import getLogger
from kugel_common.database import database as db_helper
from app.services.terminal_service import TerminalService
from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
from app.config.settings import settings

logger = getLogger(__name__)

# グローバルスケジューラーインスタンスを作成
scheduler = AsyncIOScheduler()


async def start_republish_undelivered_terminallog_job():
    """
    Start the job to republish undelivered terminallog messages.
    """
    # グローバル変数を使用
    global scheduler

    interval = settings.UNDELIVERED_CHECK_INTERVAL_IN_MINUTES
    if interval is None or interval <= 0:
        interval = 5

    # スケジューラーがすでに実行中かチェック
    if scheduler.running:
        logger.info("Scheduler is already running. Skipping start.")
        return

    scheduler.add_job(
        republish_undelivered_terminallog_async,
        trigger=CronTrigger(minute=f"*/{interval}"),
        id="republish_undelivered_terminallog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Started the republish undelivered terminallog job scheduler.")


async def stop_republish_undelivered_terminallog_job():
    """
    Stop the job to republish undelivered terminallog messages.
    """
    # グローバル変数を使用
    global scheduler

    # スケジューラーが実行中かチェック
    if not scheduler.running:
        logger.info("Scheduler is not running. No job to stop.")
        return

    job = scheduler.get_job("republish_undelivered_terminallog")
    if job:
        scheduler.remove_job("republish_undelivered_terminallog")
        logger.info("Stopped the republish undelivered terminallog job.")
    else:
        logger.info("No job found to stop.")


async def shutdown_republish_undelivered_terminallog_job():
    """
    Shutdown the job to republish undelivered terminallog messages.
    """
    # グローバル変数を使用
    global scheduler

    # まずはジョブを停止
    await stop_republish_undelivered_terminallog_job()

    # スケジューラーが実行中なら、シャットダウン
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Shutdown the republish undelivered terminallog job scheduler.")
    else:
        logger.info("Scheduler is already stopped.")


async def republish_undelivered_terminallog_async():
    """
    Republish undelivered terminallog messages.
    This function retrieves undelivered terminallog messages from the database
    and attempts to republish them.
    """
    db_common = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_commons")
    terminallog_delivery_status_repo = TerminallogDeliveryStatusRepository(db=db_common, terminal_info=None)
    terminal_service = TerminalService(
        terminal_info_repo=None,
        staff_master_repo=None,
        store_info_repo=None,
        cash_in_out_log_repo=None,
        open_close_log_repo=None,
        tran_log_repo=None,
        terminal_log_delivery_status_repo=terminallog_delivery_status_repo,
        terminal_id=None,
    )

    logger.info("Start republishing undelivered terminallog messages...")
    await republish_undelivered_messages(terminal_service)
    logger.info("Finished republishing undelivered terminallog messages.")


async def republish_undelivered_messages(terminal_service: TerminalService):
    """
    Republish undelivered terminallog messages using the terminal service.

    Args:
        terminal_service: The terminal service instance to use for republishing
    """
    await terminal_service.republish_undelivered_terminallog_async()


if __name__ == "__main__":
    asyncio.run(republish_undelivered_terminallog_async())
