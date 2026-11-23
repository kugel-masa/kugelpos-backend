"""The payment report breaks each payment method down by variant (issue #311)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from app.enums.transaction_type import TransactionType
from app.services.plugins.payment_report_maker import PaymentReportMaker


def _maker() -> PaymentReportMaker:
    return PaymentReportMaker(
        tran_repository=AsyncMock(), cash_in_out_log_repository=AsyncMock(), open_close_log_repository=AsyncMock()
    )


def _row(code, variant, ttype, amount, count, name, when="2026-11-01T10:00:00"):
    return {
        "payment_code": code,
        "variant_code": variant,
        "transaction_type": ttype,
        "amount": amount,
        "count": count,
        "variant_name": name,
        "latest_date_time": when,
    }


SALE = TransactionType.NormalSales.value
VOID = TransactionType.VoidSales.value


class TestSummarizePaymentVariants:
    def test_variants_are_summed_with_their_sign_and_ordered(self):
        breakdown = _maker()._summarize_payment_variants(
            [
                _row("11", "VISA", SALE, 1000.0, 1, "VISA"),
                _row("11", "PAYPAY", SALE, 2500.0, 2, "PayPay"),
                _row("11", None, SALE, 300.0, 1, "Cashless"),
                _row("11", "VISA", VOID, 1000.0, 1, "VISA"),
            ],
            {},
        )

        assert breakdown["11"] == [
            {"variant_code": "PAYPAY", "variant_name": "PayPay", "amount": 2500.0, "count": 2},
            {"variant_code": "VISA", "variant_name": "VISA", "amount": 0.0, "count": 0},
            {"variant_code": None, "variant_name": "Cashless", "amount": 300.0, "count": 1},
        ]

    def test_the_current_master_name_wins_and_the_newest_line_name_backs_it(self):
        rows = [
            _row("11", "VISA", SALE, 100.0, 1, "VISA old", when="2026-11-01T10:00:00"),
            _row("11", "VISA", VOID, 50.0, 1, "VISA new", when="2026-11-02T10:00:00"),
            _row("11", "GONE", SALE, 10.0, 1, "Gone card"),
        ]
        for ordered in (rows, list(reversed(rows))):
            breakdown = _maker()._summarize_payment_variants(ordered, {("11", "VISA"): "VISA (master)"})
            names = {v["variant_code"]: v["variant_name"] for v in breakdown["11"]}
            assert names == {"VISA": "VISA (master)", "GONE": "Gone card"}

        breakdown = _maker()._summarize_payment_variants(rows, {})
        assert {v["variant_code"]: v["variant_name"] for v in breakdown["11"]}["VISA"] == "VISA new"

    def test_a_transaction_using_two_variants_counts_under_each(self):
        breakdown = _maker()._summarize_payment_variants(
            [_row("11", "VISA", SALE, 1000.0, 1, "VISA"), _row("11", "PAYPAY", SALE, 2000.0, 1, "PayPay")], {}
        )

        assert sum(v["count"] for v in breakdown["11"]) == 2


def _page(payments, page, total_pages):
    return {
        "success": True,
        "data": payments,
        "metadata": {"page": page, "total_pages": total_pages, "has_next": page < total_pages},
    }


@pytest.mark.asyncio
async def test_every_page_of_the_payment_master_is_read():
    pages = {
        1: _page([{"paymentCode": f"{i:02d}", "description": f"Method {i}"} for i in range(100)], 1, 2),
        2: _page(
            [
                {
                    "paymentCode": "X1",
                    "description": "Late method",
                    "variants": [{"variantCode": "V1", "name": "Late variant"}],
                }
            ],
            2,
            2,
        ),
    }
    client = AsyncMock()
    client.get = AsyncMock(side_effect=lambda url, params, headers: pages[params["page"]])

    @asynccontextmanager
    async def fake_client(name, **kwargs):
        yield client

    maker = _maker()
    with patch("app.services.plugins.payment_report_maker.get_service_client", fake_client), patch(
        "app.services.plugins.payment_report_maker.create_service_token", return_value="token"
    ):
        payment_map, variant_map = await maker._fetch_payment_master("T1", "S1")

    assert len(payment_map) == 101
    assert payment_map["X1"] == "Late method"
    assert variant_map == {("X1", "V1"): "Late variant"}
    assert [c.kwargs["params"]["page"] for c in client.get.await_args_list] == [1, 2]


@pytest.mark.asyncio
async def test_a_failure_on_a_later_page_drops_the_variant_names_read_before_it():
    first = _page(
        [{"paymentCode": "11", "description": "Cashless", "variants": [{"variantCode": "VISA", "name": "VISA"}]}], 1, 2
    )

    async def get(url, params, headers):
        if params["page"] == 1:
            return first
        raise RuntimeError("master-data went away")

    client = AsyncMock()
    client.get = AsyncMock(side_effect=get)

    @asynccontextmanager
    async def fake_client(name, **kwargs):
        yield client

    with patch("app.services.plugins.payment_report_maker.get_service_client", fake_client), patch(
        "app.services.plugins.payment_report_maker.create_service_token", return_value="token"
    ):
        payment_map, variant_map = await _maker()._fetch_payment_master("T1", "S1")

    assert payment_map == {"01": "Cash", "11": "Cashless", "12": "Others"}
    assert variant_map == {}


def test_both_pipelines_cover_the_same_transactions():
    maker = _maker()
    maker.tran_repository.tenant_id = "T1"
    args = dict(store_code="S1", terminal_no=2, business_date="20260101", open_counter=3)

    report = maker._create_pipeline_for_payment_report(**args, limit=0, page=1, sort=[])
    variants = maker._create_pipeline_for_payment_variants(**args)

    assert report[0] == variants[0] == {"$match": maker._match_transactions(**args)}


class TestHalfDateRange:
    """A range given by one end is refused, not ignored (#314)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bounds", [{"business_date_from": "20261101"}, {"business_date_to": "20261130"}]
    )
    async def test_a_half_range_is_refused(self, bounds):
        maker = _maker()
        maker._fetch_payment_master = AsyncMock()

        with pytest.raises(ValueError, match="must be provided together"):
            await maker.generate_report(
                store_code="5678", terminal_no=None, business_counter=None, business_date="20261122",
                open_counter=None, report_scope="daily", report_type="payment", limit=100, page=1, sort=[], **bounds,
            )

        maker._fetch_payment_master.assert_not_called()
        maker.tran_repository.execute_pipeline.assert_not_called()
