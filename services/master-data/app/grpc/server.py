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
gRPC server lifecycle management

Handles server startup, shutdown, and graceful termination.
"""

import grpc
from grpc import aio
from kugel_common.grpc import item_service_pb2_grpc
from app.grpc.item_service_impl import ItemServiceImpl
import logging

logger = logging.getLogger(__name__)


async def start_grpc_server(port: int):
    """
    Start gRPC server

    Args:
        port: Port number to bind the gRPC server to

    Returns:
        grpc.aio.Server: The started gRPC server instance
    """
    server = aio.server()

    # Register service implementation
    item_service_pb2_grpc.add_ItemServiceServicer_to_server(
        ItemServiceImpl(),
        server
    )

    # Bind to port
    server.add_insecure_port(f'[::]:{port}')

    await server.start()
    logger.info(f"gRPC server started on port {port}")

    return server


async def stop_grpc_server(server):
    """
    Stop gRPC server gracefully

    Args:
        server: The gRPC server instance to stop
    """
    logger.info("Stopping gRPC server...")
    await server.stop(grace=5)
    logger.info("gRPC server stopped")
