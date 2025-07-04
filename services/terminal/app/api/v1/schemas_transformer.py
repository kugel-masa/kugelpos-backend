# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.  # This file contains transformer classes to convert internal document models to API schemas  # for version 1 of the Terminal API
from app.api.common.schemas import BaseStore
from app.api.common.schemas_transformer import SchemasTransformer
from app.api.v1.schemas import *
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo
from app.models.documents.terminal_info_document import TerminalInfoDocument


class SchemasTransformerV1(SchemasTransformer):
    """
    Schema transformer for API version 1
    Handles conversion between internal document models and API response schemas
    """

    def __init__(self):
        super().__init__()

    def transform_terminal(self, terminal_info: TerminalInfoDocument) -> Terminal:
        """
        Transform a terminal document into a terminal API schema

        Args:
            terminal_info: The terminal document to transform

        Returns:
            Terminal: The API schema representation of the terminal
        """
        return super().transform_terminal(terminal_info)

    def transform_tenant(self, tenant_info: TenantInfoDocument) -> Tenant:
        """
        Transform a tenant document into a tenant API schema

        Args:
            tenant_info: The tenant document to transform

        Returns:
            Tenant: The API schema representation of the tenant
        """
        return super().transform_tenant(tenant_info)

    def transform_store(self, store: StoreInfo) -> BaseStore:
        """
        Transform a store info object into a store API schema

        Args:
            store: The store info object to transform

        Returns:
            BaseStore: The API schema representation of the store
        """
        return super().transform_store(store)
