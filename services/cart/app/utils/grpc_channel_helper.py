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
gRPC Channel Helper for Master-Data Service

Provides module-level gRPC channel pooling to eliminate channel creation overhead.
Channels are shared across all requests for the same tenant/store combination.

Performance Impact:
- Eliminates 100-300ms gRPC channel creation overhead per request
- Expected channel creation reduction: 98-99%

Usage:
    from app.utils.grpc_channel_helper import get_master_data_grpc_stub

    stub = await get_master_data_grpc_stub(tenant_id, store_code)
    response = await stub.GetItemDetail(request)
"""

from typing import Dict, Tuple, Optional
import grpc
from kugel_common.grpc import item_service_pb2_grpc
from kugel_common.utils.grpc_client_helper import GrpcClientHelper
from app.config.settings_cart import cart_settings
from logging import getLogger

logger = getLogger(__name__)

# Module-level channel and stub cache (shared across all requests)
# Key: (tenant_id, store_code)
_channels: Dict[Tuple[str, str], grpc.aio.Channel] = {}
_stubs: Dict[Tuple[str, str], item_service_pb2_grpc.ItemServiceStub] = {}


class _DaprAppIdInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """Adds the ``dapr-app-id`` metadata a Dapr sidecar routes a gRPC call by.

    Dapr's gRPC proxy picks the callee from this entry, not from the address.
    The call's own metadata (the terminal's credential) is kept and travels on
    to master-data unchanged.
    """

    def __init__(self, app_id: str):
        self._entry = ("dapr-app-id", app_id)

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        metadata = list(client_call_details.metadata or [])
        metadata.append(self._entry)
        return await continuation(client_call_details._replace(metadata=metadata), request)


def _grpc_target() -> Tuple[str, Optional[list], str]:
    """
    Resolve (target, interceptors, pool_key) for the master-data channel.

    Direct to MASTER_DATA_GRPC_URL unless MASTER_DATA_GRPC_APP_ID is set; then
    to the local Dapr sidecar, with the app-id in the metadata and in the pool
    key, since every sidecar-routed channel has the same target.
    """
    app_id = cart_settings.MASTER_DATA_GRPC_APP_ID
    if not app_id:
        return cart_settings.MASTER_DATA_GRPC_URL, None, cart_settings.MASTER_DATA_GRPC_URL
    target = f"localhost:{cart_settings.DAPR_GRPC_PORT}"
    return target, [_DaprAppIdInterceptor(app_id)], f"{target}#{app_id}"


async def get_master_data_grpc_stub(
    tenant_id: str,
    store_code: str
) -> item_service_pb2_grpc.ItemServiceStub:
    """
    Get or create a shared gRPC stub for master-data service.

    Stubs are cached per (tenant_id, store_code) combination and reused across all requests.
    This eliminates the 100-300ms channel creation overhead per request.

    Args:
        tenant_id: The tenant identifier
        store_code: The store code

    Returns:
        ItemServiceStub: A gRPC stub for ItemService, shared across all requests
                         for the same tenant/store combination

    Performance:
        - First call for a tenant/store: Creates channel (~100-300ms)
        - Subsequent calls: Returns cached stub (~1-5ms)
        - Expected improvement: 98-99% reduction in channel creation overhead
    """
    cache_key = (tenant_id, store_code)

    if cache_key not in _channels or cache_key not in _stubs:
        # Create gRPC helper with configuration
        target, interceptors, pool_key = _grpc_target()
        grpc_helper = GrpcClientHelper(
            target=target,
            options=[
                ('grpc.max_send_message_length', 10 * 1024 * 1024),  # 10 MB
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),  # 10 MB
            ],
            interceptors=interceptors,
            pool_key=pool_key,
        )

        # Create channel via helper
        _channels[cache_key] = await grpc_helper.get_channel()

        # Create stub (reused for all requests)
        _stubs[cache_key] = item_service_pb2_grpc.ItemServiceStub(_channels[cache_key])

        logger.info(
            f"Created new gRPC channel for master-data service "
            f"(tenant={tenant_id}, store={store_code}, target={target}, via_dapr={bool(interceptors)})"
        )

    return _stubs[cache_key]


async def close_master_data_grpc_channels() -> None:
    """
    Close all gRPC channels and release resources.

    Should be called during application shutdown to properly close all open channels.
    This method is safe to call multiple times.
    """
    if not _channels:
        logger.info("No gRPC channels to close")
        return

    closed_count = 0
    error_count = 0

    for cache_key, channel in list(_channels.items()):
        try:
            await channel.close()
            logger.info(
                f"Closed gRPC channel for master-data service "
                f"(tenant={cache_key[0]}, store={cache_key[1]})"
            )
            closed_count += 1
        except Exception as e:
            logger.warning(
                f"Error closing gRPC channel for (tenant={cache_key[0]}, store={cache_key[1]}): {e}",
                exc_info=True
            )
            error_count += 1

    # Clear the caches
    _channels.clear()
    _stubs.clear()

    logger.info(
        f"gRPC channel cleanup complete: {closed_count} closed, {error_count} errors"
    )


def get_channel_cache_stats() -> Dict[str, int]:
    """
    Get statistics about the channel cache.

    Returns:
        Dict with 'total_channels' and 'total_stubs' counts

    Note: This is primarily for testing and monitoring purposes.
    """
    return {
        'total_channels': len(_channels),
        'total_stubs': len(_stubs),
    }
