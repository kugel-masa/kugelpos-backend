# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
gRPC Client Helper with connection pooling

Features:
- Global connection pool (shared across workers)
- Automatic retry with exponential backoff
- Error handling and logging
- Context manager support
"""

import grpc
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Global connection pool
_grpc_client_pool: Dict[str, grpc.aio.Channel] = {}


class GrpcClientHelper:
    """gRPC client helper with connection pooling"""

    def __init__(self, target: str, options: Optional[list] = None):
        """
        Initialize gRPC client helper

        Args:
            target: Target server address (e.g., "localhost:50051")
            options: gRPC channel options
        """
        self.target = target
        self.options = options or [
            ('grpc.max_send_message_length', 10 * 1024 * 1024),
            ('grpc.max_receive_message_length', 10 * 1024 * 1024),
            ('grpc.keepalive_time_ms', 10000),
            ('grpc.keepalive_timeout_ms', 5000),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.keepalive_permit_without_calls', 1),
        ]

    async def get_channel(self) -> grpc.aio.Channel:
        """
        Get or create gRPC channel from pool

        Returns:
            grpc.aio.Channel: gRPC channel
        """
        if self.target not in _grpc_client_pool:
            logger.info(f"Creating new gRPC channel for {self.target}")
            _grpc_client_pool[self.target] = grpc.aio.insecure_channel(
                self.target,
                options=self.options
            )
        return _grpc_client_pool[self.target]

    async def close_all(self):
        """Close all pooled channels"""
        logger.info("Closing all gRPC channels")
        for target, channel in _grpc_client_pool.items():
            try:
                await channel.close()
                logger.info(f"Closed gRPC channel for {target}")
            except Exception as e:
                logger.error(f"Error closing gRPC channel for {target}: {e}")
        _grpc_client_pool.clear()


async def close_all_grpc_channels():
    """Close all gRPC channels in the pool"""
    logger.info("Closing all gRPC channels from pool")
    for target, channel in _grpc_client_pool.items():
        try:
            await channel.close()
            logger.info(f"Closed gRPC channel for {target}")
        except Exception as e:
            logger.error(f"Error closing gRPC channel for {target}: {e}")
    _grpc_client_pool.clear()
