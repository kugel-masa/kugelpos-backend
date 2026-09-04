# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.  # api/routes/cart.py
from fastapi import APIRouter, status, Depends
from logging import getLogger
from typing import Optional
import inspect

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.status_codes import StatusCodes
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import (
    Cart,
    CartCreateRequest,
    CartCreateResponse,
    FinalizeContext,
    Item,
    PaymentRequest,
    DiscountRequest,
    ItemQuantityUpdateRequest,
    ItemUnitPriceUpdateRequest,
)
from app.dependencies.get_cart_service import get_cart_service_async, get_cart_service_with_cart_id_async
from app.exceptions import SnapshotGenerationFailedException
from app.exceptions.cart_error_codes import CartErrorCode, CartErrorMessage
from app.services import snapshot_service
from app.services.cart_service import CartService

# Create a router instance
router = APIRouter()

# Get logger instance
logger = getLogger(__name__)


# The one status on these routes whose correct handling is not "the request
# failed" (issue #192). Declared here rather than taken from the shared
# StatusCodes table because the part a client needs is cart-specific: the cart is
# held by the client, so it has to be repeated, and on a finalize the transaction
# is already recorded, so starting a new sale books it twice.
CARRIED_SNAPSHOT_UNAVAILABLE = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": (
            "The cart is carried by the client and its snapshot could not be signed, so it "
            "cannot be returned. Repeat the identical request with the snapshot already held: "
            "a mutation wrote no cart state, and a finalize is idempotent by cart_id, so the "
            "repeat returns the transaction already recorded. Do NOT start a new cart - the "
            "transaction may already exist and a new one would be booked a second time."
        ),
        "model": ApiResponse,
        "content": {
            "application/json": {
                # The shape the handler actually returns, so a client can be written
                # against it: `user_error.code` is the stable identifier to match on,
                # since 503 alone does not distinguish this from an outage.
                "example": {
                    "success": False,
                    "code": 503,
                    "message": (
                        "Cannot sign the snapshot for carried cart_id=...; the cart is held by "
                        "the client alone and cannot be returned unsigned"
                    ),
                    "user_error": {
                        "code": CartErrorCode.SNAPSHOT_GENERATION_FAILED,
                        "message": CartErrorMessage.get_message(CartErrorCode.SNAPSHOT_GENERATION_FAILED),
                    },
                    "data": None,
                }
            }
        },
    }
}


def _cart_data_with_snapshot(cart_service: CartService, cart_doc) -> dict:
    """
    Transform a mutated cart into response data with a signed snapshot attached.

    A carried response carries a restorable copy of the cart (issue #148), and
    for it the snapshot is not optional (issue #192): the server kept no copy,
    so a response without one hands the client a cart it can no longer address.
    The request has to fail instead, and the client repeats it with the
    snapshot it still holds.

    A cache-path response carries none (issue #215). #148 attached one to every
    mutating response, which was right while there was one path; #192 split
    them, and since then the envelope on this side is refused by this same
    server - present it on the next request and `cart_service` answers 409,
    because a cart opened without `carrySnapshot` is served from the cache and
    cannot be carried. There is no restore endpoint either. So it was built,
    signed and shipped with nowhere to be spent, at 74-85% of the response
    body, and the clients paying for it are the ones that declined the feature.

    `is_carried` is the right question to ask because it describes the REQUEST,
    not the cart: true when this request arrived carrying a snapshot, or when
    it creates a cart declared as carried. A client that wants to carry says so
    by carrying, and gets an envelope back.
    """
    if not cart_service.is_carried:
        return SchemasTransformerV1().transform_cart(cart_doc=cart_doc, snapshot=None).model_dump()

    snapshot = snapshot_service.build_envelope(cart_doc, cart_service.terminal_info)
    if snapshot is None:
        raise SnapshotGenerationFailedException(
            f"Cannot sign the snapshot for carried cart_id={cart_doc.cart_id}; "
            "the cart is held by the client alone and cannot be returned unsigned",
            logger,
        )
    return SchemasTransformerV1().transform_cart(cart_doc=cart_doc, snapshot=snapshot).model_dump()


# API Endpoints


@router.post(
    "/carts",
    response_model=ApiResponse[CartCreateResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def create_cart(
    create_req: CartCreateRequest,
    cart_service: CartService = Depends(get_cart_service_async),
):
    """
    Create a new shopping cart.

    Initializes a new cart for the current terminal with optional user information
    and transaction type.

    Args:
        create_req: Cart creation parameters including user info and transaction type
        cart_service: Injected cart service instance

    Returns:
        API response with the ID of the newly created cart
    """
    logger.debug(f"Creating cart for user {create_req.user_id}")
    terminal_id = cart_service.terminal_info.terminal_id
    try:
        cart_id = await cart_service.create_cart_async(
            terminal_id=terminal_id,
            transaction_type=create_req.transaction_type,
            user_id=create_req.user_id,
            user_name=create_req.user_name,
            carry_snapshot=create_req.carry_snapshot,
        )
    except Exception as e:
        raise e

    # A carried creation answers with a signed snapshot, because the cart is
    # written nowhere else (issue #192). A cache-path creation does not: the
    # server holds the cart, and an envelope for it is refused on the way back
    # (issue #215). See `_cart_data_with_snapshot`.
    snapshot = None
    if cart_service.is_carried and snapshot_service.get_snapshot_signer() is not None:
        cart_doc = await cart_service.get_cart_async()
        snapshot = snapshot_service.build_envelope(cart_doc, cart_service.terminal_info)
    if snapshot is None and cart_service.is_carried:
        # A carried cart is written nowhere, so returning its id without the
        # snapshot loses it at the moment of creation (issue #192). Nothing was
        # persisted, so failing here leaves nothing behind either.
        raise SnapshotGenerationFailedException(
            f"Cannot sign the snapshot for carried cart_id={cart_id}; "
            "the cart would be unreachable the moment it is created",
            logger,
        )

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Cart Created. cart_id: {cart_id}",
        data=CartCreateResponse(cart_id=cart_id, signed_snapshot=snapshot).model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    logger.debug(f"create_cart_response: {response}")
    return response


@router.post(
    "/carts/{cart_id}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def cancel_transaction(
    finalize: Optional[FinalizeContext] = None,
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Cancel a transaction/cart.

    Marks the cart as cancelled, preventing further modifications or processing.

    Args:
        finalize: Client-carried finalize context (issue #170). A cancellation
            writes a transaction log and prints a receipt, so on the stateless
            path the terminal stamps its number, receipt number, and time here
            exactly as it does at bill. Omitted on the cache-authoritative path,
            where the server assigns them.
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Canceling cart {cart_id}")
    try:
        cart_doc = await cart_service.cancel_transaction_async(
            seq=finalize.seq if finalize else None,
            receipt_counter=finalize.receipt_counter if finalize else None,
            transaction_datetime=finalize.transaction_datetime if finalize else None,
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Cart Cancelled. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/lineItems",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def add_items(
    line_items: list[Item],
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Add items to a cart.

    Adds one or more items to the specified cart.

    Args:
        line_items: List of items to add to the cart
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Adding items to cart {cart_id}")
    try:
        cart_doc = await cart_service.add_item_to_cart_async(
            add_item_list=[line_item.model_dump() for line_item in line_items]
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Items added to cart. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/lineItems/{lineNo}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def cancel_line_item(
    lineNo: int,
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Cancel a specific line item in a cart.

    Marks the specified line item as cancelled without removing it from the cart.

    Args:
        lineNo: Line number of the item to cancel
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Canceling line item {lineNo} from cart {cart_id}")
    try:
        cart_doc = await cart_service.cancel_line_item_from_cart_async(lineNo)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Line item cancelled. cart_id: {cart_id}, lineNo: {lineNo}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.patch(
    "/carts/{cart_id}/lineItems/{lineNo}/unitPrice",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def update_item_unit_price(
    lineNo: int,
    unit_price_update: ItemUnitPriceUpdateRequest,
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Update the unit price of a cart line item.

    Changes the unit price of the specified item in the cart.

    Args:
        lineNo: Line number of the item to update
        unit_price_update: New unit price information
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    unit_price = unit_price_update.unit_price
    logger.debug(f"Updating unit price for line item {lineNo} in cart {cart_id} into {unit_price}")
    try:
        cart_doc = await cart_service.update_line_item_unit_price_in_cart_async(lineNo, unit_price)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Unit price updated. cart_id: {cart_id}, line_no: {lineNo}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.patch(
    "/carts/{cart_id}/lineItems/{lineNo}/quantity",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def update_item_quantity(
    quantity_update: ItemQuantityUpdateRequest,
    lineNo: int,
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Update the quantity of a cart line item.

    Changes the quantity of the specified item in the cart.

    Args:
        quantity_update: New quantity information
        lineNo: Line number of the item to update
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    quantity = quantity_update.quantity
    logger.debug(f"Updating quantity for line item {lineNo} in cart {cart_id} into {quantity}")
    try:
        cart_doc = await cart_service.update_line_item_quantity_in_cart_async(lineNo, quantity)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Quantity updated. cart_id: {cart_id}, line_no: {lineNo}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/lineItems/{lineNo}/discounts",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def add_discount_to_line_item(
    discount: list[DiscountRequest],
    lineNo: int,
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Add discount to a specific line item in a cart.

    Applies one or more discounts to the specified item in the cart.

    Args:
        discount: List of discounts to apply
        lineNo: Line number of the item to apply discounts to
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Adding discount to line item {lineNo} in cart {cart_id}")
    try:
        cart_doc = await cart_service.add_discount_to_line_item_in_cart_async(
            line_no=lineNo,
            add_discount_list=[discount.model_dump() for discount in discount],
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Discount added. cart_id: {cart_id}, line_no: {lineNo}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/subtotal",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def subtotal(
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Calculate the subtotal for a cart.

    Updates the cart with calculated subtotals and tax information.

    Args:
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Calculating subtotal for cart {cart_id}")
    try:
        cart_doc = await cart_service.subtotal_async()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Subtotal calculated. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/discounts",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def discount_to_cart(
    discount: list[DiscountRequest],
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Add discount to the entire cart.

    Applies one or more discounts at the cart level, affecting the total price.

    Args:
        discount: List of discounts to apply to the cart
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Adding discount to cart {cart_id}")

    try:
        cart_doc = await cart_service.add_discount_to_cart_async(
            add_discount_list=[discount.model_dump() for discount in discount]
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Discount added. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/payments",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def payments(
    payments: list[PaymentRequest],
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Add payments to a cart.

    Processes one or more payment methods against the cart.

    Args:
        payments: List of payments to process
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Processing payment for cart {cart_id}")
    try:
        cart_doc = await cart_service.add_payment_to_cart_async(
            add_payment_list=[payment.model_dump() for payment in payments]
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Payment processed. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/bill",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def bill(
    finalize: Optional[FinalizeContext] = None,
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Finalize a cart into a billable transaction.

    Completes the cart processing, finalizing the transaction and preparing
    it for receipt generation and storage.

    Args:
        finalize: Client-carried finalize context (issue #156). On the
            stateless path the terminal stamps the transaction number, receipt
            number, and time here so a retried finalize is deterministic.
            Omitted on the cache-authoritative path (server assigns them).
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the finalized cart/transaction data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Billing cart {cart_id}")
    try:
        cart_doc = await cart_service.bill_async(
            seq=finalize.seq if finalize else None,
            receipt_counter=finalize.receipt_counter if finalize else None,
            transaction_datetime=finalize.transaction_datetime if finalize else None,
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Bill processed. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/carts/{cart_id}/resume-item-entry",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Cart],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
        **CARRIED_SNAPSHOT_UNAVAILABLE,
    },
)
async def resume_item_entry(
    cart_service: CartService = Depends(get_cart_service_with_cart_id_async),
):
    """
    Resume item entry from paying state.

    Transitions the cart from Paying state back to EnteringItem state,
    clearing any payment information and allowing additional items to be added.

    Args:
        cart_service: Injected cart service instance with cart_id

    Returns:
        API response with the updated cart data
    """
    cart_id = cart_service.cart_id
    logger.debug(f"Resuming item entry for cart {cart_id}")
    try:
        cart_doc = await cart_service.resume_item_entry_async()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item entry resumed. cart_id: {cart_id}",
        data=_cart_data_with_snapshot(cart_service, cart_doc),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
