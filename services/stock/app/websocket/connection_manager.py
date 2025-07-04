# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Dict, Set
from fastapi import WebSocket
from logging import getLogger
import asyncio

logger = getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for stock alerts"""

    def __init__(self):
        # Store connections by tenant_id and store_code
        # Structure: {tenant_id: {store_code: set(websocket_connections)}}
        self._connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str, store_code: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()

        async with self._lock:
            # Initialize tenant dict if not exists
            if tenant_id not in self._connections:
                self._connections[tenant_id] = {}

            # Initialize store set if not exists
            if store_code not in self._connections[tenant_id]:
                self._connections[tenant_id][store_code] = set()

            # Add the connection
            self._connections[tenant_id][store_code].add(websocket)

        logger.info(f"WebSocket connected for tenant {tenant_id}, store {store_code}")

    async def disconnect(self, websocket: WebSocket, tenant_id: str, store_code: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if tenant_id in self._connections and store_code in self._connections[tenant_id]:
                self._connections[tenant_id][store_code].discard(websocket)

                # Clean up empty structures
                if not self._connections[tenant_id][store_code]:
                    del self._connections[tenant_id][store_code]

                if not self._connections[tenant_id]:
                    del self._connections[tenant_id]

        logger.info(f"WebSocket disconnected for tenant {tenant_id}, store {store_code}")

    async def send_to_store(self, tenant_id: str, store_code: str, message: str):
        """Send a message to all connections for a specific store"""
        disconnected = []

        async with self._lock:
            if tenant_id not in self._connections or store_code not in self._connections[tenant_id]:
                return

            connections = list(self._connections[tenant_id][store_code])

        # Send to all connections
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                if tenant_id in self._connections and store_code in self._connections[tenant_id]:
                    for ws in disconnected:
                        self._connections[tenant_id][store_code].discard(ws)

    async def broadcast_to_tenant(self, tenant_id: str, message: str):
        """Send a message to all stores of a tenant"""
        async with self._lock:
            if tenant_id not in self._connections:
                return

            stores = list(self._connections[tenant_id].keys())

        # Send to all stores
        for store_code in stores:
            await self.send_to_store(tenant_id, store_code, message)

    def get_connection_count(self, tenant_id: str = None, store_code: str = None) -> int:
        """Get the number of active connections"""
        count = 0

        if tenant_id and store_code:
            if tenant_id in self._connections and store_code in self._connections[tenant_id]:
                count = len(self._connections[tenant_id][store_code])
        elif tenant_id:
            if tenant_id in self._connections:
                for store in self._connections[tenant_id].values():
                    count += len(store)
        else:
            for tenant in self._connections.values():
                for store in tenant.values():
                    count += len(store)

        return count
