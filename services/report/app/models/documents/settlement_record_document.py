# Copyright 2026 masa@kugel
"""
The settlement of one terminal session, as report confirmed it at close (#343).

One per (tenant, store, terminal, business_counter). It is provisional until
report receives the session's close log carrying its settlement_id; until then a
new settlement request recomputes and replaces it. Once final it never changes.
"""

from datetime import datetime
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel

STATE_PROVISIONAL = "provisional"
STATE_FINAL = "final"

DECLARED_BY_POS = "pos"
DECLARED_NONE = "none"


class NumberRange(BaseDocumentModel):
    """A run of transaction numbers, both ends included."""

    first: int
    last: int


class CashMovement(BaseDocumentModel):
    amount: float = 0.0
    count: int = 0


class ExpectedCash(BaseDocumentModel):
    """The expected cash and its breakdown (app.services.expected_cash)."""

    cash_sales: float = 0.0
    cash_in: CashMovement = CashMovement()
    cash_out: CashMovement = CashMovement()
    total: float = 0.0


class SettlementRecordDocument(AbstractDocument):
    tenant_id: str
    store_code: str
    terminal_no: int
    business_counter: int
    business_date: str
    open_counter: int

    state: str = STATE_PROVISIONAL
    settlement_id: str

    settled_by: Optional[str] = None
    settled_at: str
    recorded_at: str
    finalized_at: Optional[str] = None
    # Only logs that had reached report by this moment were counted (R-12)
    cutoff: datetime

    declared_count: Optional[int] = None
    declared_source: str = DECLARED_NONE
    included_count: int = 0
    included_ranges: list[NumberRange] = []
    missing_count: int = 0
    missing_ranges: list[NumberRange] = []
    duplicate_numbers: list[int] = []
    server_numbered_count: int = 0

    declared_cash_log_count: Optional[int] = None
    cash_log_count: int = 0
    missing_cash_log_count: int = 0

    expected_cash: ExpectedCash = ExpectedCash()
    physical_amount: Optional[float] = None
    # Counted minus expected; None when nothing was counted, never 0 for that
    difference: Optional[float] = None
