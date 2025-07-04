# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.


def check_report_data(report_data: dict):

    # sales_gross
    sales_gross_amount = report_data.get("salesGross").get("amount")
    print(f"*** Sales Gross Amount : {sales_gross_amount}")

    # returns
    returns_amount = report_data.get("returns").get("amount")
    print(f"*** Returns Amount : {returns_amount}")

    # discounts
    discount_for_lineItems_amount = report_data.get("discountForLineitems").get("amount")
    print(f"*** Discount For LineItems Amount : {discount_for_lineItems_amount}")
    discount_for_subtotal_amount = report_data.get("discountForSubtotal").get("amount")
    print(f"*** Discount For Subtotal Amount : {discount_for_subtotal_amount}")

    # sales_net
    sales_net_amount = report_data.get("salesNet").get("amount")
    print(f"*** Sales Net Amount : {sales_net_amount}")

    # taxes
    taxes = report_data.get("taxes")
    tax_amount = 0
    for tax in taxes:
        print(f"*** Tax Name : {tax.get('taxName')}")
        print(f"*** Tax Amount : {tax.get('taxAmount')}")
        tax_amount += tax.get("taxAmount")
    print(f"*** Tax Total Amount : {tax_amount}")

    # payments
    payments = report_data.get("payments")
    payment_amount = 0
    for payment in payments:
        print(f"*** Payment Name : {payment.get('paymentName')}")
        print(f"*** Payment Amount : {payment.get('amount')}")
        payment_amount += payment.get("amount")
    print(f"*** Payment Total Amount : {payment_amount}")

    # verify sales report data
    assert (
        sales_gross_amount
        == sales_net_amount + returns_amount + discount_for_lineItems_amount + discount_for_subtotal_amount
    )
    assert payment_amount == sales_net_amount + tax_amount

    # verify cash report data
    cash = report_data.get("cash")
    print(f"*** Cash Report : {cash}")

    if not cash:
        raise AssertionError("Cash report is None or empty")

    logical_amount = cash.get("logicalAmount")
    physical_amount = cash.get("physicalAmount")
    difference_amount = cash.get("differenceAmount")
    cash_in = cash.get("cashIn")
    cash_out = cash.get("cashOut")

    print(f"*** Cash In : {cash_in}")
    print(f"*** Cash Out : {cash_out}")

    if not cash_in:
        raise AssertionError("cash_in is None or empty")
    if not cash_out:
        raise AssertionError("cash_out is None or empty")

    cash_in_amount = cash_in.get("amount")
    cash_in_count = cash_in.get("count")
    cash_out_amount = cash_out.get("amount")
    cash_out_count = cash_out.get("count")

    assert cash_in_amount == 3000.0, f"Expected cash_in_amount to be 3000.0, but got {cash_in_amount}"
    assert cash_in_count == 2, f"Expected cash_in_count to be 2, but got {cash_in_count}"
    assert cash_out_amount == -500.0, f"Expected cash_out_amount to be -500.0, but got {cash_out_amount}"
    assert cash_out_count == 1, f"Expected cash_out_count to be 1, but got {cash_out_count}"
    assert logical_amount == (
        physical_amount - difference_amount
    ), f"Expected logical_amount {logical_amount} to equal (physical_amount {physical_amount} - difference_amount {difference_amount}) = {physical_amount - difference_amount}"
