"""Copies of one tranlog delivered at the same time are stored once, and none fails (issue #230).

Copies of an event can be processed concurrently. Each checks that the
transaction is not stored yet, and each inserts it inside the journal's
transaction. The loser's insert then fails with a WriteConflict or a duplicate
key, not with "already stored", because the winner had not committed when the
loser looked. That failure was answered with a retry, and with requeueing on,
the retries never ended. Once the winner has committed there is nothing left
for the loser to do.
"""

import asyncio
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from kugel_common.database import database as db_helper
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.models.documents.user_info_document import UserInfoDocument

from app.config.settings import settings
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.journal_repository import JournalRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.journal_service import JournalService
from app.services.log_service import LogService

COPIES = 4


async def _log_service(db, tenant_id: str) -> LogService:
    # One service per copy, as each delivery gets its own: a repository holds one session.
    return LogService(
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
        journal_service=JournalService(JournalRepository(db=db, tenant_id=tenant_id)),
    )


def _tranlog(tenant_id: str, transaction_no: int) -> BaseTransaction:
    return BaseTransaction(
        tenant_id=tenant_id,
        store_code=os.environ.get("STORE_CODE"),
        terminal_no=int(os.environ.get("TERMINAL_NO")),
        transaction_no=transaction_no,
        transaction_type=TransactionType.NormalSales.value,
        business_date="20260101",
        open_counter=1,
        business_counter=230,
        generate_date_time=f"2026-01-01T10:00:{transaction_no % 60:02d}",
        receipt_no=transaction_no,
        cart_id=str(uuid.uuid4()),
        user=UserInfoDocument(id="user230", name="Concurrent"),
        staff=BaseTransaction.Staff(id="staff230", name="Concurrent"),
        sales=BaseTransaction.SalesInfo(
            total_amount=100.0, total_amount_with_tax=110.0, tax_amount=10.0, total_quantity=1, is_cancelled=False
        ),
        journal_text="journal",
        receipt_text="receipt",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("transaction_no", [23001, 23002, 23003])
async def test_concurrent_copies_store_the_transaction_once_and_none_fails(transaction_no):
    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    services = [await _log_service(db, tenant_id) for _ in range(COPIES)]
    tran = _tranlog(tenant_id, transaction_no)

    with patch("app.services.log_service.send_fatal_error_notification", new_callable=AsyncMock) as fatal:
        results = await asyncio.gather(
            *(service.receive_tranlog_async(tran.model_copy(deep=True)) for service in services),
            return_exceptions=True,
        )

    failures = [result for result in results if isinstance(result, BaseException)]
    assert failures == [], failures
    fatal.assert_not_awaited()
    stored = await db[settings.DB_COLLECTION_NAME_TRAN].count_documents({"cart_id": tran.cart_id})
    journals = await db[settings.DB_COLLECTION_NAME_JOURNAL].count_documents(
        {"terminal_no": tran.terminal_no, "transaction_no": tran.transaction_no, "business_date": "20260101"}
    )
    assert (stored, journals) == (1, 1)
