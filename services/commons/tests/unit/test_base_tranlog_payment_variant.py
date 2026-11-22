"""A transaction's payment line carries its payment variant (issue #311)."""

from kugel_common.models.documents.base_tranlog import BaseTransaction


def test_a_line_recorded_before_variants_reads_without_them():
    tran = BaseTransaction(payments=[{"payment_no": 1, "payment_code": "11", "amount": 100.0, "description": "Cashless"}])

    payment = tran.payments[0]
    assert payment.variant_code is None
    assert payment.builtin_description is None


def test_a_line_keeps_its_variant_and_the_method_name():
    tran = BaseTransaction(
        payments=[
            {
                "payment_no": 1,
                "payment_code": "11",
                "amount": 100.0,
                "description": "PayPay",
                "variant_code": "PAYPAY",
                "builtin_description": "Cashless",
            }
        ]
    )

    payment = tran.payments[0]
    assert payment.variant_code == "PAYPAY"
    assert payment.description == "PayPay"
    assert payment.builtin_description == "Cashless"


def test_the_variant_fields_are_dumped():
    payment = BaseTransaction.Payment(payment_code="11", variant_code="VISA", builtin_description="Cashless")

    dumped = payment.model_dump()
    assert dumped["variant_code"] == "VISA"
    assert dumped["builtin_description"] == "Cashless"
