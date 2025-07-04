# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from logging import getLogger
import asyncio
import json

from app.models.documents.stock_document import StockDocument
from app.websocket.connection_manager import ConnectionManager

logger = getLogger(__name__)


class AlertService:
    """Service for managing stock alerts and notifications"""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        # Get cooldown from settings, default to 60 seconds
        from app.config.settings import settings

        self.alert_cooldown = settings.ALERT_COOLDOWN_SECONDS
        self.recent_alerts: Dict[str, datetime] = {}  # Track recent alerts to prevent spam
        self._cleanup_task = None

    def start(self):
        """Start the alert service background tasks"""
        self._cleanup_task = asyncio.create_task(self._cleanup_old_alerts())

    async def stop(self):
        """Stop the alert service"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_old_alerts(self):
        """Periodically clean up old alert records"""
        while True:
            try:
                await asyncio.sleep(600)  # Run every 10 minutes
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(seconds=self.alert_cooldown)

                # Remove old alert records
                keys_to_remove = [key for key, timestamp in self.recent_alerts.items() if timestamp < cutoff]
                for key in keys_to_remove:
                    del self.recent_alerts[key]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert cleanup: {e}")

    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if we should send an alert based on cooldown"""
        now = datetime.now(timezone.utc)

        if alert_key in self.recent_alerts:
            last_alert = self.recent_alerts[alert_key]
            if (now - last_alert).total_seconds() < self.alert_cooldown:
                return False

        self.recent_alerts[alert_key] = now
        return True

    async def check_and_send_alerts(self, stock: StockDocument) -> None:
        """Check stock levels and send alerts if necessary"""
        alerts_to_send = []

        # Check reorder point
        if stock.reorder_point > 0 and stock.current_quantity <= stock.reorder_point:
            alert_key = f"reorder_{stock.tenant_id}_{stock.store_code}_{stock.item_code}"
            if self._should_send_alert(alert_key):
                alerts_to_send.append(
                    {
                        "type": "stock_alert",
                        "alert_type": "reorder_point",
                        "tenant_id": stock.tenant_id,
                        "store_code": stock.store_code,
                        "item_code": stock.item_code,
                        "current_quantity": stock.current_quantity,
                        "reorder_point": stock.reorder_point,
                        "reorder_quantity": stock.reorder_quantity,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        # Check minimum stock
        if stock.minimum_quantity > 0 and stock.current_quantity < stock.minimum_quantity:
            alert_key = f"minimum_{stock.tenant_id}_{stock.store_code}_{stock.item_code}"
            if self._should_send_alert(alert_key):
                alerts_to_send.append(
                    {
                        "type": "stock_alert",
                        "alert_type": "minimum_stock",
                        "tenant_id": stock.tenant_id,
                        "store_code": stock.store_code,
                        "item_code": stock.item_code,
                        "current_quantity": stock.current_quantity,
                        "minimum_quantity": stock.minimum_quantity,
                        "reorder_quantity": stock.reorder_quantity,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        # Send alerts via WebSocket
        for alert in alerts_to_send:
            await self.send_alert(alert)

    async def send_alert(self, alert_data: Dict[str, Any]) -> None:
        """Send an alert to connected clients"""
        tenant_id = alert_data.get("tenant_id")
        store_code = alert_data.get("store_code")

        if not tenant_id or not store_code:
            logger.warning("Alert missing tenant_id or store_code")
            return

        # Send to all connections for this tenant/store
        await self.connection_manager.send_to_store(tenant_id, store_code, json.dumps(alert_data))

        logger.info(f"Sent {alert_data['alert_type']} alert for item {alert_data['item_code']}")

    async def get_current_alerts(self, tenant_id: str, store_code: str) -> list:
        """Get all current alerts for a store (for new connections)"""
        # This method would typically query the database for current alert conditions
        # For now, return empty list as this will be implemented with the stock service
        return []
