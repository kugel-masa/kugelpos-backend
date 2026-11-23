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


def test_a_promotion_document_without_a_list_still_answers():
    doc = PromotionReportDocument(tenant_id="T1", store_code="S1", report_scope="flash", promotions=None)

    data = SchemasTransformerV1().transform_promotion_report_response(doc).model_dump(by_alias=True)

    assert data["promotions"] is None


def test_v1_transformers_answer_the_v1_classes():
    from app.api.v1.schemas import PaymentReportResponse, PromotionReportResponse

    payment = PaymentReportDocument(tenant_id="T1", store_code="S1", report_scope="flash",
                                    total=PaymentReportDocument.PaymentTotal(count=0, amount=0.0))
    promotion = PromotionReportDocument(tenant_id="T1", store_code="S1", report_scope="flash")

    assert type(SchemasTransformerV1().transform_payment_report_response(payment)) is PaymentReportResponse
    assert type(SchemasTransformerV1().transform_promotion_report_response(promotion)) is PromotionReportResponse


def test_a_plugin_answering_a_dict_gets_the_same_shape():
    payment = PaymentReportDocument(
        shard_key="T1_S1", tenant_id="T1", store_code="S1", report_scope="flash",
        payment_summary=[PaymentReportDocument.PaymentSummaryItem(
            payment_code="01", payment_name="Cash", count=1, amount=100.0, ratio=100.0)],
        total=PaymentReportDocument.PaymentTotal(count=1, amount=100.0),
    ).model_dump()
    promotion = PromotionReportDocument(shard_key="T1_S1", tenant_id="T1", report_scope="flash").model_dump()

    transformer = SchemasTransformerV1()
    paid = transformer.transform_payment_report_dict(payment).model_dump(by_alias=True)
    promoted = transformer.transform_promotion_report_dict(promotion).model_dump(by_alias=True)

    assert paid["paymentSummary"][0]["paymentName"] == "Cash"
    assert "shardKey" not in paid and "shard_key" not in paid
    assert promoted["reportType"] == "promotion" and "shardKey" not in promoted
