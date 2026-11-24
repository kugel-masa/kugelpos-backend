# Copyright 2026 masa@kugel
"""
Settlement records and the daily reports they froze (#343, R-6, R-17).

A record is written provisional, replaced while it stays provisional, and made
final when the session's close log reaches report. A final record is never
written again. The record and its daily reports are written in one transaction,
so a record never exists without its reports or with another settlement's.
"""

from logging import getLogger
from typing import Optional

from pymongo.asynchronous.database import AsyncDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.schemas.base_schemas import Metadata
from kugel_common.schemas.pagination import PaginatedResult

from app.config.settings import settings
from app.models.documents.settlement_daily_report_document import SettlementDailyReportDocument
from app.models.documents.settlement_record_document import (
    STATE_FINAL,
    STATE_PROVISIONAL,
    SettlementRecordDocument,
)

logger = getLogger(__name__)

# A document of one report type must stay well under MongoDB's 16 MB (R-17).
MAX_DAILY_REPORT_BYTES = 15 * 1024 * 1024


class SettlementRecordRepository(AbstractRepository[SettlementRecordDocument]):
    def __init__(self, db: AsyncDatabase, tenant_id: str) -> None:
        super().__init__(settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD, SettlementRecordDocument, db)
        self.tenant_id = tenant_id
        self.reports = db.get_collection(settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT)

    def _key(self, store_code: str, terminal_no: int, business_counter: int) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "business_counter": business_counter,
        }

    async def get_async(self, store_code: str, terminal_no: int, business_counter: int) -> Optional[SettlementRecordDocument]:
        """The session's record, provisional or final, or None."""
        if self.dbcollection is None:
            await self.initialize()
        doc = await self.dbcollection.find_one(self._key(store_code, terminal_no, business_counter))
        return None if doc is None else SettlementRecordDocument(**doc)

    async def save_provisional_async(
        self, record: SettlementRecordDocument, daily_reports: dict[str, dict]
    ) -> SettlementRecordDocument:
        """
        Store a provisional record and its daily reports, replacing a provisional one.

        When the session already has a final record nothing is written and the
        final record is returned.

        Args:
            record: The record to store (state is forced to provisional)
            daily_reports: Report type -> the report's model_dump()

        Returns:
            The record now stored for the session
        """
        if self.dbcollection is None:
            await self.initialize()
        key = self._key(record.store_code, record.terminal_no, record.business_counter)
        record.state = STATE_PROVISIONAL
        values = record.model_dump()
        values.pop("_id", None)

        async with self.db.client.start_session() as session:
            async with await session.start_transaction():
                existing = await self.dbcollection.find_one(key, session=session)
                if existing is not None and existing.get("state") == STATE_FINAL:
                    return SettlementRecordDocument(**existing)
                if existing is not None:
                    await self.reports.delete_many(
                        {"tenant_id": self.tenant_id, "settlement_id": existing["settlement_id"]}, session=session
                    )
                    values["created_at"] = existing.get("created_at")
                await self.dbcollection.replace_one(key, values, upsert=True, session=session)
                if daily_reports:
                    await self.reports.insert_many(
                        [
                            SettlementDailyReportDocument(
                                tenant_id=self.tenant_id,
                                settlement_id=record.settlement_id,
                                store_code=record.store_code,
                                terminal_no=record.terminal_no,
                                business_counter=record.business_counter,
                                report_type=report_type,
                                report=report,
                            ).model_dump()
                            for report_type, report in daily_reports.items()
                        ],
                        session=session,
                    )
        return record

    async def finalize_async(
        self, store_code: str, terminal_no: int, business_counter: int, settlement_id: str, finalized_at: str
    ) -> bool:
        """
        Make the session's provisional record final, if it is the given settlement.

        Returns:
            True if a provisional record with that settlement_id was made final
        """
        if self.dbcollection is None:
            await self.initialize()
        result = await self.dbcollection.update_one(
            {
                **self._key(store_code, terminal_no, business_counter),
                "settlement_id": settlement_id,
                "state": STATE_PROVISIONAL,
            },
            {"$set": {"state": STATE_FINAL, "finalized_at": finalized_at}},
        )
        return result.modified_count == 1

    async def find_final_async(
        self,
        store_code: str,
        terminal_no: Optional[int] = None,
        business_date: Optional[str] = None,
        open_counter: Optional[int] = None,
        business_counter: Optional[int] = None,
        business_date_from: Optional[str] = None,
        business_date_to: Optional[str] = None,
    ) -> list[SettlementRecordDocument]:
        """Final records in a daily report's scope."""
        if self.dbcollection is None:
            await self.initialize()
        query: dict = {"tenant_id": self.tenant_id, "store_code": store_code, "state": STATE_FINAL}
        if terminal_no is not None:
            query["terminal_no"] = terminal_no
        if business_counter is not None:
            query["business_counter"] = business_counter
        if business_date_from and business_date_to:
            query["business_date"] = {"$gte": business_date_from, "$lte": business_date_to}
        elif business_date:
            query["business_date"] = business_date
        if open_counter is not None:
            query["open_counter"] = open_counter
        cursor = self.dbcollection.find(query).sort([("business_date", 1), ("terminal_no", 1), ("business_counter", 1)])
        return [SettlementRecordDocument(**doc) async for doc in cursor]

    async def list_async(
        self,
        store_code: str,
        terminal_no: Optional[int] = None,
        business_counter: Optional[int] = None,
        business_date_from: Optional[str] = None,
        business_date_to: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
        page: int = 1,
    ) -> PaginatedResult[SettlementRecordDocument]:
        """The settlement list, in business date, terminal and session order."""
        if self.dbcollection is None:
            await self.initialize()
        query: dict = {"tenant_id": self.tenant_id, "store_code": store_code}
        if terminal_no is not None:
            query["terminal_no"] = terminal_no
        if business_counter is not None:
            query["business_counter"] = business_counter
        if business_date_from and business_date_to:
            query["business_date"] = {"$gte": business_date_from, "$lte": business_date_to}
        if state is not None:
            query["state"] = state
        total = await self.dbcollection.count_documents(query)
        cursor = (
            self.dbcollection.find(query)
            .sort([("business_date", 1), ("terminal_no", 1), ("business_counter", 1)])
            .skip((page - 1) * limit)
            .limit(limit)
        )
        data = [SettlementRecordDocument(**doc) async for doc in cursor]
        return PaginatedResult(metadata=Metadata(total=total, page=page, limit=limit, sort=None, filter=None), data=data)

    async def get_daily_reports_async(self, settlement_ids: list[str], report_type: str) -> dict[str, dict]:
        """settlement_id -> the frozen report of that type."""
        cursor = self.reports.find(
            {"tenant_id": self.tenant_id, "settlement_id": {"$in": settlement_ids}, "report_type": report_type}
        )
        return {doc["settlement_id"]: doc["report"] async for doc in cursor}
