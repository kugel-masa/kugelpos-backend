# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.documents import StockDocument, StockUpdateDocument
from app.models.repositories import StockRepository, StockUpdateRepository
from app.enums.update_type import UpdateType
from app.exceptions.stock_exceptions import StockNotFoundError
from app.config.settings import settings
from app.services.alert_service import AlertService
from kugel_common.exceptions import DuplicateKeyException

logger = getLogger(__name__)


class StockService:
    def __init__(self, database: AsyncIOMotorDatabase, alert_service: Optional[AlertService] = None):
        self._database = database
        self._stock_repository = StockRepository(database)
        self._stock_update_repository = StockUpdateRepository(database)
        self._alert_service = alert_service

    async def get_stock_async(self, tenant_id: str, store_code: str, item_code: str) -> Optional[StockDocument]:
        """Get current stock for an item"""
        return await self._stock_repository.find_by_item_async(tenant_id, store_code, item_code)

    async def get_store_stocks_async(
        self, tenant_id: str, store_code: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[StockDocument], int]:
        """Get all stocks for a store with total count"""
        stocks = await self._stock_repository.find_by_store_async(tenant_id, store_code, skip, limit)
        total_count = await self._stock_repository.count_by_store_async(tenant_id, store_code)
        return stocks, total_count

    async def get_low_stocks_async(self, tenant_id: str, store_code: str) -> Tuple[List[StockDocument], int]:
        """Get items with stock below minimum quantity with count"""
        stocks = await self._stock_repository.find_low_stock_async(tenant_id, store_code)
        return stocks, len(stocks)

    async def update_stock_async(
        self,
        tenant_id: str,
        store_code: str,
        item_code: str,
        quantity_change: float,
        update_type: UpdateType,
        reference_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        note: Optional[str] = None,
        terminal_no: Optional[int] = None,
        transaction_no: Optional[int] = None,
        cart_id: Optional[str] = None,
    ) -> StockUpdateDocument:
        """Update stock quantity and record the update with atomic operations to prevent race conditions.

        When `terminal_no` and `transaction_no` are supplied, the resulting
        StockUpdateDocument carries them too — the unique partial index on
        `(tenant_id, store_code, terminal_no, transaction_no, item_code,
        update_type)` then ensures Dapr cannot double-apply the same
        transaction even if the state-store idempotency check misses
        (issue #98). On `DuplicateKeyException`, the inventory $inc is
        rolled back and the existing record is returned instead, keeping
        stock balanced.
        """

        # Use atomic update with upsert - this handles both existing and non-existing documents
        updated_stock = await self._stock_repository.update_quantity_atomic_async(
            tenant_id, store_code, item_code, quantity_change, reference_id
        )

        if updated_stock is None:
            raise StockNotFoundError(message=f"Failed to update stock for item {item_code}")

        # Calculate before quantity from the after quantity and change
        after_quantity = updated_stock.current_quantity
        before_quantity = after_quantity - quantity_change

        # Allow negative stock (backorders are permitted)
        # Log warning if stock goes negative
        if after_quantity < 0:
            logger.warning(
                f"Stock going negative for item {item_code}. "
                f"Available: {before_quantity}, After: {after_quantity}, "
                f"Change: {quantity_change}"
            )

        # Create update record
        update_record = StockUpdateDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            item_code=item_code,
            update_type=update_type,
            quantity_change=quantity_change,
            before_quantity=before_quantity,
            after_quantity=after_quantity,
            reference_id=reference_id,
            timestamp=datetime.now(timezone.utc),
            operator_id=operator_id,
            note=note,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            cart_id=cart_id,
        )

        try:
            await self._stock_update_repository.create_async(update_record)
        except DuplicateKeyException:
            # Same transaction already applied — Dapr redelivered past a
            # state-store idempotency miss. The $inc above DID happen, so
            # roll it back to keep stock balanced, then return the
            # already-existing record.
            logger.warning(
                f"Duplicate stock update detected at DB layer; rolling back $inc. "
                f"tenant={tenant_id}, store={store_code}, item={item_code}, "
                f"terminal_no={terminal_no}, transaction_no={transaction_no}, "
                f"update_type={update_type.value}"
            )
            await self._stock_repository.update_quantity_atomic_async(
                tenant_id, store_code, item_code, -quantity_change, reference_id
            )
            # Look up the already-applied record. Phase 2 (issue #156) keys on
            # cart_id when present (the duplicate carries the same cart_id);
            # otherwise the legacy (terminal_no, transaction_no) identity.
            lookup = {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "item_code": item_code,
                "update_type": update_type.value,
            }
            if cart_id is not None:
                lookup["cart_id"] = cart_id
            else:
                lookup["terminal_no"] = terminal_no
                lookup["transaction_no"] = transaction_no
            existing = await self._stock_update_repository.get_one_async(lookup)
            return existing or update_record

        logger.info(
            f"Stock updated - Item: {item_code}, Before: {before_quantity}, "
            f"After: {after_quantity}, Type: {update_type.value}"
        )

        # Check for alerts if alert service is available
        if self._alert_service:
            await self._alert_service.check_and_send_alerts(updated_stock)

        return update_record

    async def get_stock_history_async(
        self, tenant_id: str, store_code: str, item_code: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[StockUpdateDocument], int]:
        """Get stock update history for an item with total count"""
        updates = await self._stock_update_repository.find_by_item_async(tenant_id, store_code, item_code, skip, limit)
        total_count = await self._stock_update_repository.count_by_item_async(tenant_id, store_code, item_code)
        return updates, total_count

    async def process_transaction_async(self, transaction_data: Dict[str, Any]) -> None:
        """Process transaction from pubsub"""
        try:
            # Extract transaction details
            tenant_id = transaction_data.get("tenant_id")
            store_code = transaction_data.get("store_code")
            terminal_no = transaction_data.get("terminal_no")
            transaction_no = transaction_data.get("transaction_no")
            cart_id = transaction_data.get("cart_id")
            transaction_type = transaction_data.get("transaction_type")
            line_items = transaction_data.get("line_items", [])

            # Convert transaction_no to string for reference
            transaction_no_str = str(transaction_no) if transaction_no is not None else None

            logger.info(
                f"Processing transaction {transaction_no} (cart_id: {cart_id}, type: {transaction_type}) for tenant {tenant_id} store {store_code}, terminal {terminal_no}"
            )

            # Idempotency pre-check: if any stock_update already exists for this
            # transaction, it was already processed — skip the whole batch
            # (re-applying $inc would double-decrement). Client-carried cart
            # phase 2 (issue #156 / #152) keys on cart_id when present (a
            # duplicate finalize / lost-ACK retry to any backend carries the
            # same cart_id); otherwise the legacy (terminal_no, transaction_no)
            # identity (Dapr redelivery, issue #98).
            existing = None
            if cart_id is not None:
                existing = await self._stock_update_repository.find_by_cart_id_async(
                    tenant_id=tenant_id, store_code=store_code, cart_id=cart_id
                )
            elif terminal_no is not None and transaction_no is not None:
                existing = await self._stock_update_repository.find_by_transaction_async(
                    tenant_id=tenant_id,
                    store_code=store_code,
                    terminal_no=terminal_no,
                    transaction_no=transaction_no,
                )
            if existing:
                logger.warning(
                    f"Transaction already processed (cart_id={cart_id}, transaction_no={transaction_no}) for "
                    f"tenant={tenant_id}, store={store_code}, terminal={terminal_no} "
                    f"({len(existing)} existing stock_update records). Skipping."
                )
                return

            # Check if transaction is cancelled
            is_cancelled = transaction_data.get("sales", {}).get("is_cancelled", False)
            if is_cancelled:
                logger.info("Transaction is cancelled, skipping stock update.")
                return

            # Determine stock update sign based on transaction type
            from kugel_common.enums import TransactionType

            if transaction_type == TransactionType.NormalSales.value:
                logger.debug("Processing normal sales transaction")
                update_type = UpdateType.SALE
                sign = -1
            elif transaction_type == TransactionType.VoidSales.value:
                logger.debug("Processing void sales transaction")
                update_type = UpdateType.VOID
                sign = 1
            elif transaction_type == TransactionType.ReturnSales.value:
                logger.debug("Processing return sales transaction")
                update_type = UpdateType.RETURN
                sign = 1
            elif transaction_type == TransactionType.VoidReturn.value:
                logger.debug("Processing void return transaction")
                update_type = UpdateType.VOID_RETURN
                sign = -1
            else:
                logger.warning(
                    f"Unknown transaction type {transaction_type} for transaction {transaction_no}. Skipping stock update."
                )
                return

            # Process each item in the transaction
            for item in line_items:
                item_code = item.get("item_code")
                quantity = item.get("quantity", 0)
                is_item_cancelled = item.get("is_cancelled", False)

                # Skip cancelled items
                if is_item_cancelled:
                    logger.info(
                        f"Item {item_code} in transaction {transaction_no} is cancelled, skipping stock update."
                    )
                    continue

                if quantity > 0:
                    # Sales reduce stock (negative change)
                    await self.update_stock_async(
                        tenant_id=tenant_id,
                        store_code=store_code,
                        item_code=item_code,
                        quantity_change=quantity * sign,  # negative for sales, positive for returns
                        update_type=update_type,
                        reference_id=transaction_no_str,
                        terminal_no=terminal_no,
                        transaction_no=transaction_no,
                        cart_id=cart_id,
                    )

            logger.info(
                f"Transaction processed successfully. tenant_id: {tenant_id}, store_code: {store_code}, terminal_no: {terminal_no}, transaction_no: {transaction_no}"
            )

        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
            raise

    async def set_minimum_quantity_async(
        self, tenant_id: str, store_code: str, item_code: str, minimum_quantity: float
    ) -> bool:
        """Set minimum quantity for an item"""
        stock = await self._stock_repository.find_by_item_async(tenant_id, store_code, item_code)

        if stock is None:
            # Create new stock record with minimum quantity
            stock = StockDocument(
                tenant_id=tenant_id,
                store_code=store_code,
                item_code=item_code,
                current_quantity=0.0,
                minimum_quantity=minimum_quantity,
                reorder_point=0.0,
                reorder_quantity=0.0,
            )
            await self._stock_repository.create_async(stock)
            return True
        else:
            # Update existing stock
            return await self._stock_repository.update_one_async(
                {"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code},
                {"minimum_quantity": minimum_quantity},
            )

    async def set_reorder_parameters_async(
        self, tenant_id: str, store_code: str, item_code: str, reorder_point: float, reorder_quantity: float
    ) -> bool:
        """Set reorder point and quantity for an item"""
        stock = await self._stock_repository.find_by_item_async(tenant_id, store_code, item_code)

        if stock is None:
            # Create new stock record with reorder parameters
            stock = StockDocument(
                tenant_id=tenant_id,
                store_code=store_code,
                item_code=item_code,
                current_quantity=0.0,
                minimum_quantity=0.0,
                reorder_point=reorder_point,
                reorder_quantity=reorder_quantity,
            )
            await self._stock_repository.create_async(stock)

            # Check if new stock triggers alerts
            if self._alert_service:
                await self._alert_service.check_and_send_alerts(stock)

            return True
        else:
            # Update existing stock
            success = await self._stock_repository.update_reorder_parameters_async(
                tenant_id, store_code, item_code, reorder_point, reorder_quantity
            )

            # Check if updated stock triggers alerts
            if success and self._alert_service:
                updated_stock = await self._stock_repository.find_by_item_async(tenant_id, store_code, item_code)
                if updated_stock:
                    await self._alert_service.check_and_send_alerts(updated_stock)

            return success

    async def get_reorder_alerts_async(self, tenant_id: str, store_code: str) -> Tuple[List[StockDocument], int]:
        """Get items with stock below reorder point"""
        stocks = await self._stock_repository.find_reorder_alerts_async(tenant_id, store_code)
        return stocks, len(stocks)
