"""Two sales that share a numbering are both stored and both counted (issue #230).

A cart_id is a transaction's identity; the numbering (terminal_no,
business_counter, transaction_no) is unique at the source, where cart refuses a
second finalize. Downstream the numbering index covered every record, so a sale
reusing a numbering with a different cart_id was rejected: report dropped it as
"already stored", journal retried it until it was dead-lettered. And the sales and
payment reports grouped transactions by transaction_no, so two sales sharing one,
including the same seq in two opens of a day (#156), were counted as one.
"""

import os
import uuid

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction

from app.database import database_setup
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.report_service import ReportService

# A tenant of its own, dropped after each test: these tests store sales that
# share a numbering, which a shared tenant's numbering index would then refuse
# to be rebuilt over, and they rebuild that index.
TENANT = "T230NUMBERING"
STORE = "STORE230"
TERMINAL = 23
DATE = "2026-10-22"


@pytest_asyncio.fixture(autouse=True)
async def _own_tenant():
    yield
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await db.client.drop_database(db.name)


def _sale(amount: int, cart_id: str | None, business_counter: int = 7, transaction_no: int = 1) -> BaseTransaction:
    tax = amount // 10
    return BaseTransaction(
        tenant_id=TENANT,
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        business_counter=business_counter,
        open_counter=1,
        transaction_no=transaction_no,
        transaction_type=TransactionType.NormalSales.value,
        generate_date_time=f"{DATE}T10:00:00",
        cart_id=cart_id,
        sales={
            "total_amount": amount,
            "total_amount_with_tax": amount + tax,
            "tax_amount": tax,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,
        },
        payments=[{"payment_no": 1, "payment_code": "01", "amount": amount + tax, "description": "Cash"}],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "10%",
                "tax_amount": tax,
                "target_amount": amount,
                "target_quantity": 1,
            }
        ],
        line_items=[
            {"line_no": 1, "item_code": "I230", "quantity": 1, "unit_price": amount, "amount": amount, "tax_code": "01"}
        ],
    )


async def _db_and_repo():
    tenant_id = TENANT
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")
    repo = TranlogRepository(db, tenant_id)
    await db[repo.collection_name].delete_many({"store_code": STORE})
    await database_setup.create_tran_collection(tenant_id)
    return db, repo


async def _report(db, report_type: str):
    tenant_id = TENANT
    service = ReportService(
        tran_repository=TranlogRepository(db, tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db, tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db, tenant_id),
        daily_info_repository=DailyInfoDocumentRepository(db, tenant_id),
        terminal_info_repository=TerminalInfoWebRepository(db, tenant_id),
    )
    return await service.get_report_for_terminal_async(
        store_code=STORE,
        terminal_no=TERMINAL,
        report_scope="flash",
        report_type=report_type,
        business_date=DATE,
        open_counter=1,
        limit=100,
        page=1,
    )


@pytest.mark.asyncio
async def test_a_sale_reusing_a_numbering_with_another_cart_id_is_stored():
    db, repo = await _db_and_repo()

    await repo.create_tranlog_async(_sale(1000, str(uuid.uuid4())))
    await repo.create_tranlog_async(_sale(2000, str(uuid.uuid4())))

    assert await db[repo.collection_name].count_documents({"store_code": STORE}) == 2


@pytest.mark.asyncio
async def test_the_same_cart_id_is_still_stored_once():
    db, repo = await _db_and_repo()
    cart_id = str(uuid.uuid4())

    await repo.create_tranlog_async(_sale(1000, cart_id))
    await repo.create_tranlog_async(_sale(1000, cart_id))

    assert await db[repo.collection_name].count_documents({"store_code": STORE}) == 1


@pytest.mark.asyncio
async def test_a_numbering_without_a_cart_id_is_still_unique():
    db, repo = await _db_and_repo()
    collection = db[repo.collection_name]

    await collection.insert_one(_sale(1000, None).model_dump())
    with pytest.raises(Exception, match="E11000"):
        await collection.insert_one(_sale(2000, None).model_dump())


@pytest.mark.asyncio
async def test_a_numbering_index_over_every_record_is_replaced():
    """An existing tenant has the old index; setup rebuilds it as a partial one."""
    db, repo = await _db_and_repo()
    collection = db[repo.collection_name]
    name = next(n for n, i in (await collection.index_information()).items() if "business_counter" in dict(i["key"]))
    await collection.drop_index(name)
    await collection.create_index(list(database_setup.NUMBERING_KEYS.items()), name=name, unique=True)

    await database_setup.create_tran_collection(TENANT)

    info = (await collection.index_information())[name]
    assert info["unique"] is True
    assert info["partialFilterExpression"] == {"cart_id": None}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "second",
    [
        {"cart_id": "other", "business_counter": 7},
        # The same per-open seq in another open of the day (#156).
        {"cart_id": None, "business_counter": 8},
    ],
    ids=["same-numbering-other-cart-id", "same-seq-other-open"],
)
async def test_both_sales_are_counted_in_the_reports(second):
    db, repo = await _db_and_repo()
    await db[repo.collection_name].insert_many(
        [_sale(1000, str(uuid.uuid4())).model_dump(), _sale(2000, **second).model_dump()]
    )

    sales = await _report(db, "sales")
    payments = await _report(db, "payment")

    assert sales.sales_net.amount == 3000
    assert sum(p.amount for p in sales.payments) == 3300
    cash = next(p for p in payments.payment_summary if p.payment_code == "01")
    assert (cash.count, cash.amount) == (2, 3300)


def _stages(plan: dict) -> list[str]:
    stages = [plan.get("stage")]
    for key in ("inputStage", "queryPlan"):
        if key in plan:
            stages += _stages(plan[key])
    for child in plan.get("inputStages", []):
        stages += _stages(child)
    return stages


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [{"cart_id": {"$ne": "this-one"}}, {}],
    ids=["numbering-reuse-check", "dedupe-without-cart-id"],
)
async def test_a_lookup_by_numbering_uses_an_index(extra):
    """The partial numbering index cannot serve these; without another index they scan every record."""
    db, repo = await _db_and_repo()
    collection = db[repo.collection_name]
    numbering = {
        "tenant_id": TENANT,
        "store_code": "S",
        "terminal_no": 1,
        "business_counter": 1,
        "transaction_no": 1,
    }

    plan = (await collection.find({**numbering, **extra}).limit(1).explain())["queryPlanner"]["winningPlan"]

    assert "IXSCAN" in _stages(plan), plan
    assert "COLLSCAN" not in _stages(plan), plan
