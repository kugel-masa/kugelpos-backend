# Copyright 2026 masa@kugel
"""Settling the sessions an e2e test seeded, before it reads a daily report (#343).

The report e2e tests write logs straight into MongoDB rather than through a
terminal, so no terminal closes the sessions. This settles every session in a
scope the way a close does: report confirms the settlement, then finalizes it
as it does when the session's close log arrives.
"""

import os

from kugel_common.database import database as db_helper

from app.config.settings import settings
from app.dependencies.get_settlement_service import get_settlement_service_async
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.report_service import ReportService
from app.services.settlement_service import SettlementRequest


async def settle_scope_async(store_code: str, business_date: str = None, business_date_from: str = None, business_date_to: str = None) -> int:
    """Confirm and finalize every unsettled session with a log in the scope; returns how many."""
    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    reports = ReportService(
        tran_repository=TranlogRepository(db, tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db, tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db, tenant_id),
    )
    sessions = await reports._sessions_in_scope_async(
        store_code, business_date=business_date, business_date_from=business_date_from, business_date_to=business_date_to
    )
    service = await get_settlement_service_async(tenant_id)
    close_logs = db[settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG]
    settled = 0
    for (terminal_no, business_counter), info in sessions.items():
        if business_counter is None:
            continue
        # What the terminal would have sent: the seeded close log's figures
        close = await close_logs.find_one(
            {"tenant_id": tenant_id, "store_code": store_code, "terminal_no": terminal_no,
             "business_counter": business_counter, "operation": "close"}
        ) or {}
        record, _ = await service.confirm_async(
            SettlementRequest(
                store_code=store_code,
                terminal_no=terminal_no,
                business_counter=business_counter,
                business_date=info["business_date"],
                open_counter=info["open_counter"] or 1,
                settled_at=f"{info['business_date']}T23:59:00",
                cash_log_count=close.get("cash_in_out_count"),
                physical_amount=(close.get("terminal_info") or {}).get("physical_amount"),
            )
        )
        if await service.settlement_repository.finalize_async(
            store_code, terminal_no, business_counter, record.settlement_id, "e2e"
        ):
            settled += 1
    return settled
