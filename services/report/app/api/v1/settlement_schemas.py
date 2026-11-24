# Copyright 2026 masa@kugel
"""Request and response schemas of the settlement endpoints (#343)."""

from typing import Optional

from pydantic import Field

from kugel_common.schemas.base_schemas import BaseSchemmaModel


class NumberRangeSchema(BaseSchemmaModel):
    first: int
    last: int


class CashMovementSchema(BaseSchemmaModel):
    amount: float = 0.0
    count: int = 0


class ExpectedCashSchema(BaseSchemmaModel):
    cash_sales: float = 0.0
    cash_in: CashMovementSchema = CashMovementSchema()
    cash_out: CashMovementSchema = CashMovementSchema()
    total: float = 0.0


class SettlementConfirmRequest(BaseSchemmaModel):
    """What terminal sends to settle a session at close."""

    business_counter: int = Field(..., ge=1)
    business_date: str = Field(..., pattern=r"^\d{8}$")
    open_counter: int = Field(..., ge=1)
    settled_at: str
    # The last number of the carried series the terminal issued (R-13)
    seq: Optional[int] = Field(None, ge=0)
    # The cash logs the terminal recorded for the session
    cash_log_count: Optional[int] = Field(None, ge=0)
    physical_amount: Optional[float] = None
    settled_by: Optional[str] = None


class SettlementFigures(BaseSchemmaModel):
    """The figures a settlement records."""

    tenant_id: str
    store_code: str
    terminal_no: int
    business_counter: int
    business_date: str
    open_counter: int
    settled_kind: str = "close"
    settled_by: Optional[str] = None
    admin_reason: Optional[str] = None
    settled_at: str
    declared_count: Optional[int] = None
    declared_source: str
    included_count: int
    included_ranges: list[NumberRangeSchema] = []
    missing_count: int
    missing_ranges: list[NumberRangeSchema] = []
    duplicate_numbers: list[int] = []
    server_numbered_count: int = 0
    declared_cash_log_count: Optional[int] = None
    cash_log_count: int
    missing_cash_log_count: int
    expected_cash: ExpectedCashSchema
    physical_amount: Optional[float] = None
    difference: Optional[float] = None


class SettlementRecordResponse(SettlementFigures):
    settlement_id: str
    state: str
    recorded_at: str
    finalized_at: Optional[str] = None


class SettlementConfirmResponse(SettlementRecordResponse):
    # True when this request computed the record; False when it returned a final one
    created: bool


class SettlementPreviewResponse(SettlementFigures):
    # True when the session already has a final settlement; the figures are then its own
    settled: bool


def figures_of(record) -> dict:
    """The settlement record's fields as the schemas name them (snake_case input)."""
    return record.model_dump(exclude={"cutoff", "shard_key", "created_at", "updated_at", "etag"})
