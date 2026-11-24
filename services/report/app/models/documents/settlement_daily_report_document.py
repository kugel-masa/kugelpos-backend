# Copyright 2026 masa@kugel
"""One daily report a settlement froze (#343, R-17).

Kept apart from the settlement record, one document per report type, so no single
document has to hold every report of a large session, and a daily report reads
only the type it needs.
"""

from kugel_common.models.documents.abstract_document import AbstractDocument


class SettlementDailyReportDocument(AbstractDocument):
    tenant_id: str
    settlement_id: str
    store_code: str
    terminal_no: int
    business_counter: int
    report_type: str
    # The report maker's document, as model_dump() produced it
    report: dict
