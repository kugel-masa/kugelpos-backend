# Copyright 2026 masa@kugel
"""Building the SettlementService for a tenant (#343)."""

from kugel_common.database import database as db_helper

from app.config.settings import settings
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.settlement_record_repository import SettlementRecordRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.settlement_service import SettlementService


async def get_settlement_service_async(tenant_id: str) -> SettlementService:
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return SettlementService(
        tenant_id=tenant_id,
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
        settlement_repository=SettlementRecordRepository(db=db, tenant_id=tenant_id),
    )
