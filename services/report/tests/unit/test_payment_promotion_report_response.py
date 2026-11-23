"""Payment and promotion reports answer camelCase without stored-document fields (issue #329)."""

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.models.documents.payment_report_document import PaymentReportDocument
from app.models.documents.promotion_report_document import PromotionReportDocument
from app.models.documents.sales_report_document import PaymentVariantReport


def test_the_payment_report_response_is_camel_case_with_its_nested_rows():
    doc = PaymentReportDocument(
        shard_key="T1_S1", etag="e", tenant_id="T1", store_code="S1", report_scope="flash",
        payment_summary=[
            PaymentReportDocument.PaymentSummaryItem(
                payment_code="11", payment_name="Cashless", count=2, amount=300.0, ratio=100.0,
                variants=[PaymentVariantReport(variant_code="VISA", variant_name="VISA", amount=300.0, count=2)],
            )
        ],
        total=PaymentReportDocument.PaymentTotal(count=2, amount=300.0),
        generate_date_time="2026-11-23T10:00:00+09:00",
    )

    data = SchemasTransformerV1().transform_payment_report_response(doc).model_dump(by_alias=True)

    assert data["paymentSummary"] == [{
        "paymentCode": "11", "paymentName": "Cashless", "count": 2, "amount": 300.0, "ratio": 100.0,
        "variants": [{"variantCode": "VISA", "variantName": "VISA", "amount": 300.0, "count": 2}],
    }]
    assert data["total"] == {"count": 2, "amount": 300.0}
    assert (data["reportType"], data["generateDateTime"]) == ("payment", "2026-11-23T10:00:00+09:00")
    assert not {"shardKey", "etag", "createdAt", "updatedAt", "shard_key"} & set(data)


def test_the_promotion_report_response_is_camel_case_with_its_rows():
    doc = PromotionReportDocument(
        shard_key="T1_S1", tenant_id="T1", store_code="S1", report_scope="flash",
        promotions=[PromotionReportDocument.PromotionReportItem(
            promotion_code="P1", promotion_type="category_discount", gross_amount=1000.0, discount_amount=100.0,
            net_amount=900.0, quantity=3, transaction_count=2,
        )],
        total_gross_amount=1000.0, total_discount_amount=100.0, total_net_amount=900.0,
        total_quantity=3, total_transaction_count=2,
    )

    data = SchemasTransformerV1().transform_promotion_report_response(doc).model_dump(by_alias=True)

    assert data["promotions"] == [{
        "promotionCode": "P1", "promotionType": "category_discount", "grossAmount": 1000.0,
        "discountAmount": 100.0, "netAmount": 900.0, "quantity": 3, "transactionCount": 2,
    }]
    assert (data["totalGrossAmount"], data["totalTransactionCount"], data["reportType"]) == (1000.0, 2, "promotion")
    assert not {"shardKey", "etag", "createdAt", "updatedAt", "shard_key"} & set(data)
