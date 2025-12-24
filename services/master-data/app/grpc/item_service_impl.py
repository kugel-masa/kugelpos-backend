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
ItemService gRPC implementation

Implements the GetItemDetail RPC method for retrieving item master data.
"""

import grpc
from kugel_common.grpc import item_service_pb2, item_service_pb2_grpc
from kugel_common.exceptions import DocumentNotFoundException
from app.dependencies.get_master_services import get_item_store_master_service_async
import logging

logger = logging.getLogger(__name__)


class ItemServiceImpl(item_service_pb2_grpc.ItemServiceServicer):
    """gRPC service implementation for item master data"""

    async def GetItemDetail(self, request, context):
        """Get item detail by item code"""
        try:
            logger.info(
                f"gRPC GetItemDetail request: tenant_id={request.tenant_id}, "
                f"store_code={request.store_code}, item_code={request.item_code}"
            )

            # Get item store master service for the tenant and store
            master_service = await get_item_store_master_service_async(
                request.tenant_id, request.store_code
            )

            # Get combined common + store-specific item data
            try:
                item = await master_service.get_item_store_detail_by_code_async(request.item_code)
            except DocumentNotFoundException:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Item {request.item_code} not found")
                logger.warning(f"Item not found: {request.item_code}")
                return item_service_pb2.ItemDetailResponse()

            # Use store_price if available, otherwise fall back to unit_price
            price = item.store_price if item.store_price is not None else item.unit_price

            # Build response
            response = item_service_pb2.ItemDetailResponse(
                item_code=item.item_code,
                item_name=item.description or "",
                price=int(price) if price else 0,
                tax_rate=int(item.tax_code) if item.tax_code else 0,
                category_code=item.category_code or "",
                barcode=item.item_code,  # Using item_code as barcode for now
                is_active=not item.is_deleted if hasattr(item, 'is_deleted') else True,
                created_at=item.created_at.isoformat() if item.created_at else "",
                updated_at=item.updated_at.isoformat() if item.updated_at else "",
                tax_code=item.tax_code or "",  # Tax code as string
            )

            logger.info(f"gRPC GetItemDetail success: item_code={item.item_code}, price={price}")
            return response

        except DocumentNotFoundException:
            raise
        except Exception as e:
            logger.error(f"gRPC GetItemDetail error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return item_service_pb2.ItemDetailResponse()
