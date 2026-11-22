"""The sample receipt prints payment lines by variant (issue #311)."""

from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.services.strategies.receipt_data.receipt_data_sample import ReceiptDataSample


def _payment_lines(payments, change=0.0):
    tran = BaseTransaction(
        sales=BaseTransaction.SalesInfo(total_amount_with_tax=sum(p.amount for p in payments), change_amount=change),
        payments=payments,
    )
    return [_text(line) for line in ReceiptDataSample("receipt")._add_payment(tran)]


def _text(line) -> str:
    columns = getattr(line, "columns", None)
    if columns:
        return " ".join(str(column.value) for column in columns)
    return str(getattr(line, "text", "") or "")


def _line(code, amount, name, variant=None, deposit=0.0):
    return BaseTransaction.Payment(
        payment_code=code, amount=amount, description=name, variant_code=variant, deposit_amount=deposit
    )


def test_a_cashless_variant_prints_its_own_name():
    text = "\n".join(_payment_lines([_line("11", 1000.0, "PayPay", "PAYPAY"), _line("11", 500.0, "VISA", "VISA")]))

    assert "PayPay" in text and "VISA" in text


def test_cash_variants_stay_apart_and_deposit_and_change_print_once():
    lines = _payment_lines(
        [
            _line("01", 600.0, "Yen", "JPY", deposit=1000.0),
            _line("01", 400.0, "Gift change", "GIFT", deposit=400.0),
        ],
        change=400.0,
    )
    text = "\n".join(lines)

    assert sum("お預り" in line for line in lines) == 1
    assert sum("お釣り" in line for line in lines) == 1
    assert "1,400" in next(line for line in lines if "お預り" in line)
    assert "Yen" in text and "Gift change" in text


def test_cash_lines_of_one_variant_are_summed_as_before():
    lines = _payment_lines([_line("01", 300.0, "Cash", deposit=300.0), _line("01", 200.0, "Cash", deposit=200.0)])

    cash = [line for line in lines if line.startswith("Cash")]
    assert len(cash) == 1 and "500" in cash[0]
