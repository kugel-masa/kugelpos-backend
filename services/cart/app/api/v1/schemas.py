# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime, timedelta
from typing import Optional

from kugel_common.utils.misc import get_app_time
from pydantic import BaseModel, field_validator, model_validator
from app.api.common.schemas import (
    BaseCart,
    BaseItem,
    BaseItemQuantityUpdateRequest,
    BaseItemUnitPriceUpdateRequest,
    BasePaymentRequest,
    BaseDiscount,
    BaseCartCreateRequest,
    BaseCartCreateResponse,
    BaseCartDeleteResponse,
    BaseTenantCreateRequest,
    BaseTenantCreateResponse,
    BaseDiscountRequest,
    BaseTranLineItem,
    BaseTranPayment,
    BaseTranTax,
    BaseTranStaff,
    BaseTranStatus,
    BaseTran,
    BaseStore,
    BaseUser,
    BaseSchemmaModel,
)


class Item(BaseItem):
    """
    API v1 model for representing items in shopping cart operations.
    Extends the BaseItem with version-specific functionality.
    """

    pass


class ItemQuantityUpdateRequest(BaseItemQuantityUpdateRequest):
    """
    API v1 model for item quantity update requests.
    Used when changing the quantity of an item in the cart.
    """

    pass


class ItemUnitPriceUpdateRequest(BaseItemUnitPriceUpdateRequest):
    """
    API v1 model for unit price update requests.
    Used when manually changing the price of an item in the cart.
    """

    pass


class PaymentRequest(BasePaymentRequest):
    """
    API v1 model for payment processing requests.
    Contains information needed to process a payment against a cart.
    """

    pass


class TranLineItem(BaseTranLineItem):
    """
    API v1 model for transaction line items.
    Represents a single line item in a transaction record.
    """

    pass


class TranPayment(BaseTranPayment):
    """
    API v1 model for transaction payment records.
    Contains payment method and amount details for a transaction.
    """

    pass


class TranTax(BaseTranTax):
    """
    API v1 model for transaction tax information.
    Extends the base tax model with additional v1-specific tax properties.
    """

    tax_code: Optional[str] = None
    tax_target_amount: Optional[float] = 0.0
    tax_target_quantity: Optional[int] = 0
    pass


class TranStaff(BaseTranStaff):
    """
    API v1 model for transaction staff information.
    Contains details about the staff member associated with a transaction.
    """

    pass


class TranStatus(BaseTranStatus):
    """
    API v1 model for transaction status.
    Represents the current status of a transaction, such as pending or completed.
    """

    pass


class Tran(BaseTran):
    """
    API v1 model for transaction records.
    Represents a complete transaction with all associated details.
    """

    pass


class Cart(BaseCart):
    """
    API v1 model for shopping carts.
    Contains all information about a cart including its items, status, and totals.
    """

    pass


class Store(BaseStore):
    """
    API v1 model for store information.
    Contains store identification and terminal details.
    """

    pass


class User(BaseUser):
    """
    API v1 model for user information.
    Contains user identification details for cart operations.
    """

    pass


class CartCreateRequest(BaseCartCreateRequest):
    """
    API v1 model for cart creation requests.
    Contains parameters required to create a new shopping cart.
    """

    pass


class CartCreateResponse(BaseCartCreateResponse):
    """
    API v1 model for cart creation responses.
    Contains the identifier of the newly created cart.
    """

    pass


# How far a client-stamped finalize time may sit from server time (issue #156).
# Generous on purpose: terminal clocks drift and an offline session may be
# settled long after the sale. These bounds only reject a plainly wrong clock.
MAX_BACKDATED_FINALIZE = timedelta(days=90)
MAX_FUTUREDATED_FINALIZE = timedelta(days=1)


class FinalizeContext(BaseSchemmaModel):
    """
    Client-carried finalize context for the bill endpoint (issue #156).

    On the stateless (snapshot-present) path the terminal stamps the
    transaction's number, receipt counter, and time at bill and supplies them
    here so a retried finalize on any backend yields the same values
    (deterministic finalize, FR-012). Absent on the cache-authoritative path,
    where the server assigns them. The context is all-or-nothing (a partial one
    would write a null transaction_no or receipt_no); accepts camelCase
    (seq / receiptCounter / transactionDatetime) via the alias generator.

    The PRINTED receipt number is not accepted (issue #208). It is derived from
    the counter and the configured range, which is all `derive_receipt_no`
    needs. Accepting it let a request body put any number on the transaction
    log and on the receipt, whatever the terminal's configured range - a
    mismatch was a warning and the finalize succeeded.

    The old behaviour was defensible while the terminal printed: the paper
    existed before the request did, and renumbering it would contradict
    something the customer is holding. It stops being defensible the moment the
    SERVER builds the receipt, because `make_receipt_data` runs on the tranlog
    after this number is decided - so the number the client named is the number
    that gets printed, and there is no paper to contradict. Signing the
    envelope so numbering cannot be forged, and then letting the printed number
    be named in the request body, is not a coherent position.
    """

    seq: Optional[int] = None
    # Running receipt counter (issue #166). The printed number is derived from
    # this and the configured range, so a terminal that wraps prints inside the
    # range rather than counting 1, 2, 3.
    receipt_counter: Optional[int] = None
    transaction_datetime: Optional[str] = None

    @field_validator("transaction_datetime")
    @classmethod
    def _validate_datetime(cls, v):
        # The carried time becomes the authoritative tranlog generate_date_time
        # and feeds the business-date bucket (split on "T"); reject anything that
        # is not an ISO-8601 datetime so it can't corrupt downstream bucketing.
        if v is None:
            return v
        try:
            stamped = datetime.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError("transaction_datetime must be an ISO-8601 datetime string")
        if "T" not in v:
            raise ValueError("transaction_datetime must include a 'T' date/time separator")
        # A well-formed but absurd time is just as corrupting as a malformed one:
        # it lands the sale in a business-date bucket that reports will never
        # reconcile. The window is deliberately wide — a terminal's clock may
        # drift, and an offline session can be settled well after the fact — so
        # this only catches a clock that is plainly wrong, not a late upload.
        now = get_app_time()
        if stamped.tzinfo is None:
            now = now.replace(tzinfo=None)
        if not (now - MAX_BACKDATED_FINALIZE) <= stamped <= (now + MAX_FUTUREDATED_FINALIZE):
            raise ValueError(
                f"transaction_datetime {v} is outside the accepted window "
                f"(-{MAX_BACKDATED_FINALIZE.days}d / +{MAX_FUTUREDATED_FINALIZE.days}d from server time)"
            )
        return v

    @model_validator(mode="after")
    def _all_or_none(self):
        # A partial context would write a null transaction_no or receipt_no, so
        # the context is all-or-nothing. Since #208 the counter is the only
        # receipt input, so a pre-#166 terminal that sends the printed number
        # alone no longer supplies a usable context - which is the point, and
        # what a 422 here is telling it.
        provided = [
            self.seq is not None,
            self.receipt_counter is not None,
            self.transaction_datetime is not None,
        ]
        if any(provided) and not all(provided):
            raise ValueError("seq, receipt_counter and transaction_datetime must all be provided together")
        return self


class CartDeleteResponse(BaseCartDeleteResponse):
    """
    API v1 model for cart deletion responses.
    Contains a status message about the deletion operation.
    """

    pass


class TenantCreateRequest(BaseTenantCreateRequest):
    """
    API v1 model for tenant creation requests.
    Contains parameters required to create a new tenant.
    """

    pass


class TenantCreateResponse(BaseTenantCreateResponse):
    """
    API v1 model for tenant creation responses.
    Contains the identifier of the newly created tenant.
    """

    pass


class DiscountRequest(BaseDiscountRequest):
    """
    API v1 model for discount application requests.
    Contains parameters needed to apply a discount to an item or cart.
    """

    pass


class DeliveryStatusUpdateRequest(BaseModel):
    """
    API model for delivery status update requests.
    Contains parameters needed to update the delivery status of a transaction.
    """

    event_id: str
    service: str
    status: str
    message: Optional[str] = None


class DeliveryStatusUpdateResponse(BaseModel):
    """
    API model for delivery status update responses.
    Returns the result of updating the delivery status.
    """

    event_id: str
    service: str
    status: str
    success: bool
