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
Item Master Repository Factory

Provides runtime selection between HTTP and gRPC implementations.
"""

from typing import Union
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.config.settings_cart import cart_settings
from app.models.repositories.item_master_web_repository import ItemMasterWebRepository
from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
from app.models.documents.item_master_document import ItemMasterDocument
import logging

logger = logging.getLogger(__name__)


def create_item_master_repository(
    tenant_id: str,
    store_code: str,
    terminal_info: TerminalInfoDocument,
    item_master_documents: list[ItemMasterDocument] = None,
) -> Union[ItemMasterWebRepository, ItemMasterGrpcRepository]:
    """
    Create item master repository based on configuration

    Returns:
        ItemMasterWebRepository or ItemMasterGrpcRepository depending on USE_GRPC setting
    """
    if cart_settings.USE_GRPC:
        logger.info("Using gRPC client for master-data communication")
        return ItemMasterGrpcRepository(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_info=terminal_info,
            item_master_documents=item_master_documents,
        )
    else:
        logger.info("Using HTTP client for master-data communication")
        return ItemMasterWebRepository(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_info=terminal_info,
            item_master_documents=item_master_documents,
        )
