"""Two sales that share a numbering are both journaled (issue #230).

A cart_id is a transaction's identity; the numbering (terminal_no,
business_counter, transaction_no) is unique at the source, where cart refuses a
second finalize. Downstream the numbering index covered every record, so a sale
reusing a numbering with a different cart_id failed with a duplicate key on every
delivery. Each copy held a subscriber slot while it was retried, until it was
dead-lettered, and ten of them stopped the journal.
"""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from kugel_common.database import database as db_helper
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.models.documents.user_info_document import UserInfoDocument

from app.config.settings import settings
from app.database import database_setup
from app.models.repositories import tranlog_repository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.journal_repository import JournalRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.journal_service import JournalService
from app.services.log_service import LogService

TERMINAL = 230


async def _db():
    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    for name in (settings.DB_COLLECTION_NAME_TRAN, settings.DB_COLLECTION_NAME_JOURNAL):
        await db[name].delete_many({"terminal_no": TERMINAL})
    await database_setup.create_tran_collection(tenant_id)
    return db


def _service(db) -> LogService:
    tenant_id = os.environ.get("TENANT_ID")
    return LogService(
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
        journal_service=JournalService(JournalRepository(db=db, tenant_id=tenant_id)),
    )


def _sale(cart_id: str, second: int) -> BaseTransaction:
    return BaseTransaction(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=os.environ.get("STORE_CODE"),
        terminal_no=TERMINAL,
        transaction_no=1,
        business_counter=7,
        transaction_type=TransactionType.NormalSales.value,
        business_date="20261022",
        open_counter=1,
        generate_date_time=f"2026-10-22T10:00:{second:02d}",
        receipt_no=second,
        cart_id=cart_id,
        user=UserInfoDocument(id="u", name="u"),
        staff=BaseTransaction.Staff(id="s", name="s"),
        sales=BaseTransaction.SalesInfo(
            total_amount=100.0, total_amount_with_tax=110.0, tax_amount=10.0, total_quantity=1, is_cancelled=False
        ),
        journal_text="journal",
        receipt_text="receipt",
    )


@pytest.mark.asyncio
async def test_a_sale_reusing_a_numbering_with_another_cart_id_is_journaled():
    db = await _db()

    with patch("app.services.log_service.send_fatal_error_notification", new_callable=AsyncMock) as fatal:
        await _service(db).receive_tranlog_async(_sale(str(uuid.uuid4()), 1))
        with patch.object(tranlog_repository.logger, "warning") as warning:
            await _service(db).receive_tranlog_async(_sale(str(uuid.uuid4()), 2))

    fatal.assert_not_awaited()
    assert await db[settings.DB_COLLECTION_NAME_TRAN].count_documents({"terminal_no": TERMINAL}) == 2
    assert await db[settings.DB_COLLECTION_NAME_JOURNAL].count_documents({"terminal_no": TERMINAL}) == 2
    # Stored, but the numbering reuse is still said.
    assert any("share one numbering" in call.args[0] for call in warning.call_args_list)


@pytest.mark.asyncio
async def test_the_same_cart_id_is_still_journaled_once():
    db = await _db()
    cart_id = str(uuid.uuid4())

    await _service(db).receive_tranlog_async(_sale(cart_id, 1))
    await _service(db).receive_tranlog_async(_sale(cart_id, 1))

    assert await db[settings.DB_COLLECTION_NAME_TRAN].count_documents({"terminal_no": TERMINAL}) == 1
    assert await db[settings.DB_COLLECTION_NAME_JOURNAL].count_documents({"terminal_no": TERMINAL}) == 1


@pytest.mark.asyncio
async def test_a_numbering_index_over_every_record_is_replaced():
    """An existing tenant has the old index; setup rebuilds it as a partial one."""
    db = await _db()
    collection = db[settings.DB_COLLECTION_NAME_TRAN]
    name = next(n for n, i in (await collection.index_information()).items() if "business_counter" in dict(i["key"]))
    await collection.drop_index(name)
    await collection.create_index(list(database_setup.NUMBERING_KEYS.items()), name=name, unique=True)

    await database_setup.create_tran_collection(os.environ.get("TENANT_ID"))
    await database_setup.create_tran_collection(os.environ.get("TENANT_ID"))

    info = (await collection.index_information())[name]
    assert info["unique"] is True
    assert info["partialFilterExpression"] == {"cart_id": None}
