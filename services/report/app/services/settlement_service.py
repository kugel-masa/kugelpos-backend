# Copyright 2026 masa@kugel
"""
Settling a terminal session (#343).

At close, terminal asks report to confirm the session's settlement. Report
counts what has arrived by a cutoff, freezes the session's daily reports and
stores a provisional settlement record. The record becomes final when report
receives the session's close log carrying its settlement_id, and never changes
after that.
"""

import asyncio
import uuid
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Optional

import bson

from kugel_common.utils.misc import get_app_time, get_app_time_str

from app.exceptions.report_exceptions import SettlementAggregationException
from app.models.documents.settlement_record_document import (
    DECLARED_BY_POS,
    DECLARED_NONE,
    STATE_FINAL,
    SettlementRecordDocument,
)
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.settlement_record_repository import MAX_DAILY_REPORT_BYTES, SettlementRecordRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.expected_cash import cash_difference, cash_sales_of, expected_cash, summarize_cash_logs
from app.services.plugins.sales_report_receipt_data import SalesReportReceiptData
from app.services.report_plugin_manager import ReportPluginManager
from app.services.settlement_counting import TranRow, count_session, missing_cash_log_count

logger = getLogger(__name__)

# Every report type a settlement freezes (FR-008)
FROZEN_REPORT_TYPES = ("sales", "category", "item", "payment", "promotion")
# Names are fetched once per settlement, briefly: a slow master-data must not
# hold the close up. Without them the codes stand in, as the reports already do.
NAME_FETCH_TIMEOUT_SECONDS = 5.0


@dataclass
class SettlementRequest:
    """What terminal sends to settle a session."""

    store_code: str
    terminal_no: int
    business_counter: int
    business_date: str
    open_counter: int
    settled_at: str
    seq: Optional[int] = None
    cash_log_count: Optional[int] = None
    physical_amount: Optional[float] = None
    settled_by: Optional[str] = None


@dataclass
class SessionSnapshot:
    """A settlement's figures, before they are stored."""

    record: SettlementRecordDocument
    daily_reports: dict[str, dict]


class SettlementService:
    def __init__(
        self,
        tenant_id: str,
        tran_repository: TranlogRepository,
        cash_in_out_log_repository: CashInOutLogRepository,
        open_close_log_repository: OpenCloseLogRepository,
        settlement_repository: SettlementRecordRepository,
    ):
        self.tenant_id = tenant_id
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        self.settlement_repository = settlement_repository
        self.report_makers = ReportPluginManager().load_plugins(
            "report_makers",
            tran_repository=tran_repository,
            cash_in_out_log_repository=cash_in_out_log_repository,
            open_close_log_repository=open_close_log_repository,
        )

    # ------------------------------------------------------------------ confirm

    async def confirm_async(self, request: SettlementRequest) -> tuple[SettlementRecordDocument, bool]:
        """
        Confirm a session's settlement.

        Returns:
            (the record now stored, True if this call computed it). A final
            record is returned as stored, with False.

        Raises:
            SettlementAggregationException: A daily report could not be frozen;
                nothing was stored (R-15)
        """
        existing = await self.settlement_repository.get_async(
            request.store_code, request.terminal_no, request.business_counter
        )
        if existing is not None and existing.state == STATE_FINAL:
            return existing, False

        snapshot = await self._snapshot_async(request, settlement_id=str(uuid.uuid4()), with_reports=True)
        stored = await self.settlement_repository.save_provisional_async(snapshot.record, snapshot.daily_reports)
        created = stored.settlement_id == snapshot.record.settlement_id
        logger.info(
            f"Settlement {'computed' if created else 'already final'}: store={request.store_code} "
            f"terminal={request.terminal_no} business_counter={request.business_counter} "
            f"settlement_id={stored.settlement_id} missing={stored.missing_count} "
            f"missing_cash_logs={stored.missing_cash_log_count}"
        )
        return stored, created

    async def preview_async(self, request: SettlementRequest) -> tuple[SettlementRecordDocument, bool]:
        """
        What confirming would record, without storing anything (FR-021).

        Returns:
            (figures, settled). When the session is already final, its stored
            record with True.
        """
        existing = await self.settlement_repository.get_async(
            request.store_code, request.terminal_no, request.business_counter
        )
        if existing is not None and existing.state == STATE_FINAL:
            return existing, True
        snapshot = await self._snapshot_async(request, settlement_id="preview", with_reports=False)
        return snapshot.record, False

    async def finalize_from_close_log_async(self, close_log: Any) -> None:
        """
        Make the session's settlement final when its close log arrives (R-6).

        A close log without a settlement_id comes from a terminal older than
        #343 and finalizes nothing.
        """
        settlement_id = getattr(close_log, "settlement_id", None)
        if not settlement_id:
            return
        store_code, terminal_no, business_counter = (
            close_log.store_code,
            close_log.terminal_no,
            close_log.business_counter,
        )
        if await self.settlement_repository.finalize_async(
            store_code, terminal_no, business_counter, settlement_id, get_app_time_str()
        ):
            return

        record = await self.settlement_repository.get_async(store_code, terminal_no, business_counter)
        if record is not None and record.state == STATE_FINAL:
            return  # a redelivered close log
        # Two closes raced and the losing one replaced the provisional record
        # after the winner was told its settlement_id (R-6). The terminal closed on
        # the close log's settlement_id: recompute under that id and make it final.
        logger.warning(
            f"Close log settlement_id {settlement_id} does not match the provisional record "
            f"{record.settlement_id if record else None}; recomputing it as final. "
            f"store={store_code} terminal={terminal_no} business_counter={business_counter}"
        )
        terminal_info = getattr(close_log, "terminal_info", None)
        request = SettlementRequest(
            store_code=store_code,
            terminal_no=terminal_no,
            business_counter=business_counter,
            business_date=close_log.business_date,
            open_counter=close_log.open_counter,
            settled_at=close_log.generate_date_time,
            seq=close_log.cart_transaction_last_no,
            cash_log_count=close_log.cash_in_out_count,
            physical_amount=getattr(terminal_info, "physical_amount", None) if terminal_info else None,
            settled_by=f"staff:{close_log.staff_id}" if close_log.staff_id else None,
        )
        snapshot = await self._snapshot_async(request, settlement_id=settlement_id, with_reports=True)
        await self.settlement_repository.save_provisional_async(snapshot.record, snapshot.daily_reports)
        if not await self.settlement_repository.finalize_async(
            store_code, terminal_no, business_counter, settlement_id, get_app_time_str()
        ):
            # Replaced again before it could be made final: fail the delivery so
            # the close log is delivered again, rather than leave it provisional
            raise RuntimeError(
                f"Settlement {settlement_id} could not be made final; the close log will be redelivered"
            )

    # ------------------------------------------------------------------ figures

    async def _snapshot_async(
        self, request: SettlementRequest, settlement_id: str, with_reports: bool
    ) -> SessionSnapshot:
        # The session's logs are read once, here; every figure below - the counts,
        # the expected cash and all five frozen reports - is made from exactly
        # these documents, whatever arrives meanwhile (R-12). No clock is
        # involved, so neither a commit landing late nor a replica's clock skew
        # can make two figures disagree.
        cutoff = get_app_time()
        session = {
            "tenant_id": self.tenant_id,
            "store_code": request.store_code,
            "terminal_no": request.terminal_no,
            "business_counter": request.business_counter,
        }

        tran_ids, rows = await self._tran_rows_async(session)
        cash_ids, cash_amounts = await self._cash_amounts_async(session)
        counted = count_session(rows, request.seq)
        cash_summary = summarize_cash_logs(cash_amounts)

        scope = {"extra_match": {"_id": {"$in": tran_ids}}, "cash_extra_match": {"_id": {"$in": cash_ids}}}
        names = await self._names_async(request.store_code)
        sales = await self._report_async("sales", request, scope, names)
        expected = expected_cash(cash_sales_of(p.model_dump() for p in sales.payments), cash_summary)
        difference = cash_difference(request.physical_amount, expected["total"])

        daily_reports: dict[str, dict] = {}
        if with_reports:
            self._overwrite_cash(sales, expected, request.physical_amount, difference)
            daily_reports["sales"] = sales.model_dump()
            for report_type in FROZEN_REPORT_TYPES:
                if report_type == "sales":
                    continue
                report = await self._report_async(report_type, request, scope, names)
                daily_reports[report_type] = report.model_dump() if hasattr(report, "model_dump") else report
            self._check_sizes(daily_reports)

        record = SettlementRecordDocument(
            tenant_id=self.tenant_id,
            store_code=request.store_code,
            terminal_no=request.terminal_no,
            business_counter=request.business_counter,
            business_date=request.business_date,
            open_counter=request.open_counter,
            settlement_id=settlement_id,
            settled_by=request.settled_by,
            settled_at=request.settled_at,
            recorded_at=get_app_time_str(),
            cutoff=cutoff,
            declared_count=request.seq,
            declared_source=DECLARED_BY_POS if request.seq is not None else DECLARED_NONE,
            included_count=counted.included_count,
            included_ranges=counted.included_ranges,
            missing_count=counted.missing_count,
            missing_ranges=counted.missing_ranges,
            duplicate_numbers=counted.duplicate_numbers,
            server_numbered_count=counted.server_numbered_count,
            declared_cash_log_count=request.cash_log_count,
            cash_log_count=len(cash_amounts),
            missing_cash_log_count=missing_cash_log_count(request.cash_log_count, len(cash_amounts)),
            expected_cash=expected,
            physical_amount=request.physical_amount,
            difference=difference,
        )
        return SessionSnapshot(record=record, daily_reports=daily_reports)

    async def _tran_rows_async(self, query: dict) -> tuple[list, list[TranRow]]:
        """The session's transaction logs: their ids, and what counting needs."""
        repo = self.tran_repository
        if repo.dbcollection is None:
            await repo.initialize()
        cursor = repo.dbcollection.find(query, {"cart_id": 1, "transaction_no": 1, "receipt_counter": 1})
        docs = [d async for d in cursor]
        rows = [
            TranRow(cart_id=d.get("cart_id"), transaction_no=d.get("transaction_no"), receipt_counter=d.get("receipt_counter"))
            for d in docs
        ]
        return [d["_id"] for d in docs], rows

    async def _cash_amounts_async(self, query: dict) -> tuple[list, list[float]]:
        """The session's cash logs: their ids and amounts."""
        repo = self.cash_in_out_log_repository
        if repo.dbcollection is None:
            await repo.initialize()
        docs = [d async for d in repo.dbcollection.find(query, {"amount": 1})]
        return [d["_id"] for d in docs], [d.get("amount") or 0 for d in docs]

    async def _names_async(self, store_code: str) -> dict[str, Any]:
        """Category and payment names, fetched once for the five reports."""

        async def bounded(coro, fallback, what):
            try:
                return await asyncio.wait_for(coro, timeout=NAME_FETCH_TIMEOUT_SECONDS)
            except Exception as e:  # noqa: BLE001 - names are cosmetic; the figures must not wait
                logger.warning(f"Settlement: {what} names unavailable ({type(e).__name__}); codes stand in")
                return fallback

        category_names, payment_names = await asyncio.gather(
            bounded(self.report_makers["category"].category_repository.get_categories(), {}, "category"),
            bounded(self.report_makers["payment"]._fetch_payment_master(self.tenant_id, store_code), ({}, {}), "payment"),
        )
        return {"category_names": category_names or {}, "payment_names": payment_names}

    async def _report_async(self, report_type: str, request: SettlementRequest, scope: dict, names: dict) -> Any:
        try:
            return await self.report_makers[report_type].generate_report(
                store_code=request.store_code,
                terminal_no=request.terminal_no,
                business_counter=request.business_counter,
                business_date=request.business_date,
                open_counter=request.open_counter,
                report_scope="daily",
                report_type=report_type,
                limit=100,
                page=1,
                sort=None,
                unbounded=True,
                **scope,
                **names,
            )
        except Exception as e:
            message = (
                f"Cannot freeze the {report_type} report: store={request.store_code} "
                f"terminal={request.terminal_no} business_counter={request.business_counter}"
            )
            raise SettlementAggregationException(message, logger, e) from e

    @staticmethod
    def _overwrite_cash(sales: Any, expected: dict, physical_amount: Optional[float], difference: Optional[float]) -> None:
        """
        Put the settlement's cash on the frozen sales report, and print it again.

        The maker reads the counted cash from the close log, which does not exist
        yet when the settlement is confirmed (R-4).
        """
        sales.cash.logical_amount = expected["total"]
        sales.cash.physical_amount = physical_amount
        sales.cash.difference_amount = difference
        sales.cash.cash_in.amount = expected["cash_in"]["amount"]
        sales.cash.cash_in.count = expected["cash_in"]["count"]
        sales.cash.cash_out.amount = expected["cash_out"]["amount"]
        sales.cash.cash_out.count = expected["cash_out"]["count"]
        receipt = SalesReportReceiptData("Sales Report", 32).make_receipt_data(sales)
        sales.receipt_text = receipt.receipt_text
        sales.journal_text = receipt.journal_text

    @staticmethod
    def _check_sizes(daily_reports: dict[str, dict]) -> None:
        for report_type, report in daily_reports.items():
            size = len(bson.encode({"report": report}))
            if size > MAX_DAILY_REPORT_BYTES:
                raise SettlementAggregationException(
                    f"The frozen {report_type} report is {size} bytes, over {MAX_DAILY_REPORT_BYTES}", logger
                )
