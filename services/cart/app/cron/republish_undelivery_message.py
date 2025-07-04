# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
This script is used to republish undelivered tranlog messages.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import asyncio
from logging import getLogger
from kugel_common.database import database as db_helper
from app.services.tran_service import TranService
from app.models.repositories.tranlog_delivery_status_repository import TranlogDeliveryStatusRepository
from app.config.settings import settings

logger = getLogger(__name__)

# グローバルスケジューラーインスタンスを作成
scheduler = AsyncIOScheduler()


async def start_republish_undelivered_tranlog_job():
    """
    Start the job to republish undelivered tranlog messages.
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
        republish_undelivered_tranlog_async,
        trigger=CronTrigger(minute=f"*/{interval}"),
        id="republish_undelivered_tranlog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Started the republish undelivered tranlog job scheduler.")


async def stop_republish_undelivered_tranlog_job():
    """
    Stop the job to republish undelivered tranlog messages.
    """
    # グローバル変数を使用
    global scheduler

    # スケジューラーが実行中かチェック
    if not scheduler.running:
        logger.info("Scheduler is not running. No job to stop.")
        return

    job = scheduler.get_job("republish_undelivered_tranlog")
    if job:
        scheduler.remove_job("republish_undelivered_tranlog")
        logger.info("Stopped the republish undelivered tranlog job.")
    else:
        logger.info("No job found to stop.")


async def shutdown_republish_undelivered_tranlog_job():
    """
    Shutdown the job to republish undelivered tranlog messages.
    """
    # グローバル変数を使用
    global scheduler

    # まずはジョブを停止
    await stop_republish_undelivered_tranlog_job()

    # スケジューラーが実行中なら、シャットダウン
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Shutdown the republish undelivered tranlog job scheduler.")
    else:
        logger.info("Scheduler is already stopped.")


async def republish_undelivered_tranlog_async():
    """
    Republish undelivered tranlog messages.
    This function retrieves undelivered tranlog messages from the database
    and attempts to republish them.
    """
    db_common = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_commons")
    tranlog_delivery_status_repo = TranlogDeliveryStatusRepository(db=db_common, terminal_info=None)
    tran_service = TranService(
        terminal_info=None,
        terminal_counter_repo=None,
        tranlog_repo=None,
        tranlog_delivery_status_repo=tranlog_delivery_status_repo,
        settings_master_repo=None,
        payment_master_repo=None,
        transaction_status_repo=None,
    )

    logger.info("Start republishing undelivered tranlog messages...")
    try:
        await tran_service.republish_undelivered_tranlog_async()
        logger.info("Finished republishing undelivered tranlog messages.")
    finally:
        # Always close the TranService to cleanup resources
        await tran_service.close()


if __name__ == "__main__":
    asyncio.run(republish_undelivered_tranlog_async())
