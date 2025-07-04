# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.utils.misc import get_app_time_str
from kugel_common.models.documents.base_tranlog import BaseTransaction


def get_date_time_str():
    return get_app_time_str()


# tran_log
def make_tran_log(
    tenant_id: str,
    store_code: str,
    terminal_no: int,
    tran_type: int,
    tran_no: int,
    receipt_no: int,
    business_date: str,
    open_counter: int = 1,
    business_counter: int = 1001,
    generate_date_time: str = get_date_time_str(),
):

    print(f"***** generate_date_time: {generate_date_time}")

    return_tranlog = BaseTransaction(
        tenant_id=tenant_id,
        store_code=store_code,
        terminal_no=terminal_no,
        transaction_no=tran_no,
        transaction_type=tran_type,
        business_date=business_date,
        open_counter=open_counter,
        business_counter=business_counter,
        generate_date_time=generate_date_time,
        receipt_no=receipt_no,
        user={"id": "user789", "name": "John Doe"},
        sales={
            "reference_date_time": generate_date_time,
            "total_amount": 500.0,
            "total_amount_with_tax": 550.0,
            "tax_amount": 50.0,
            "total_quantity": 3,
            "change_amount": 450.0,
            "total_discount_amount": 0.0,
            "is_cancelled": False,
        },
        line_items=[
            {
                "line_no": 1,
                "item_code": "item123",
                "category_code": "cat456",
                "description": "Sample Item",
                "description_short": "Item",
                "unit_price": 100.0,
                "quantity": 1,
                "discounts": [],
                "discounts_allocated": [],
                "amount": 100.0,
                "tax_code": "01",
                "is_cancelled": False,
            },
            {
                "line_no": 2,
                "item_code": "item234",
                "category_code": "cat567",
                "description": "Sample Item 2",
                "description_short": "Item 2",
                "unit_price": 200.0,
                "quantity": 2,
                "discounts": [],
                "discounts_allocated": [],
                "amount": 400.0,
                "tax_code": "01",
                "is_cancelled": False,
            },
        ],
        payments=[
            {"payment_no": 1, "payment_code": "01", "deposit_amount": 1000.0, "amount": 550.0, "description": "Cash"}
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "外税10%",
                "tax_amount": 50.0,
                "target_amount": 500.0,
                "target_quantity": 3,
            }
        ],
        subtotal_discounts=[],
        receipt_text="Thank you for your purchase!",
    )

    return return_tranlog.model_dump()
