# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo
from app.models.documents.open_close_log import OpenCloseLog
from app.api.common.schemas import *

logger = getLogger(__name__)


class SchemasTransformer:

    def __init__(self):
        pass

    # transform TerminalInfoDocument to Terminal
    def transform_terminal(self, terminal_info: TerminalInfoDocument) -> BaseTerminal:
        logger.debug(f"TerminalInfoDocument: {terminal_info}")

        return_terminal = BaseTerminal(
            terminal_id=terminal_info.terminal_id,
            tenant_id=terminal_info.tenant_id,
            store_code=terminal_info.store_code,
            terminal_no=terminal_info.terminal_no,
            description=terminal_info.description,
            function_mode=terminal_info.function_mode,
            status=terminal_info.status,
            business_date=terminal_info.business_date,
            open_counter=terminal_info.open_counter,
            business_counter=terminal_info.business_counter,
            initial_amount=terminal_info.initial_amount,
            physical_amount=terminal_info.physical_amount,
            api_key=terminal_info.api_key,
            entry_datetime=terminal_info.created_at.strftime("%Y-%m-%d %H:%M:%S") if terminal_info.created_at else None,
            last_update_datetime=(
                terminal_info.updated_at.strftime("%Y-%m-%d %H:%M:%S") if terminal_info.updated_at else None
            ),
        )

        if terminal_info.staff is not None:
            return_terminal.staff = BaseStaff(
                staff_id=terminal_info.staff.id, staff_name=terminal_info.staff.name, staff_pin=terminal_info.staff.pin
            )

        logger.debug(f"return_terminal: {return_terminal}")
        return return_terminal

    # transform TeanantInfoDocument to Teanant
    def transform_tenant(self, tenant_info: TenantInfoDocument) -> BaseTenant:
        logger.debug(f"TenantInfoDocument: {tenant_info}")

        stores = []
        for store in tenant_info.stores:
            return_store = BaseStore(
                store_code=store.store_code,
                store_name=store.store_name,
                status=store.status,
                business_date=store.business_date,
                tags=store.tags,
                entry_datetime=store.created_at.strftime("%Y-%m-%d %H:%M:%S") if store.created_at else None,
                last_update_datetime=store.updated_at.strftime("%Y-%m-%d %H:%M:%S") if store.updated_at else None,
            )
            stores.append(return_store)

        return_tenant = BaseTenant(
            tenant_id=tenant_info.tenant_id,
            tenant_name=tenant_info.tenant_name,
            stores=stores,
            tags=tenant_info.tags,
            entry_datetime=tenant_info.created_at.strftime("%Y-%m-%d %H:%M:%S") if tenant_info.created_at else None,
            last_update_datetime=(
                tenant_info.updated_at.strftime("%Y-%m-%d %H:%M:%S") if tenant_info.updated_at else None
            ),
        )

        return return_tenant

    # transform StoreInfo to BaseStore
    def transform_store(self, store: StoreInfo) -> BaseStore:
        logger.debug(f"StoreInfo: {store}")

        return BaseStore(
            store_code=store.store_code,
            store_name=store.store_name,
            status=store.status,
            business_date=store.business_date,
            tags=store.tags,
            entry_datetime=store.created_at.strftime("%Y-%m-%d %H:%M:%S") if store.created_at else None,
            last_update_datetime=store.updated_at.strftime("%Y-%m-%d %H:%M:%S") if store.updated_at else None,
        )

    # transform OpenCloseLog to BaseTerminalOpenResponse
    def transform_open_log(self, open_close_log: OpenCloseLog) -> BaseTerminalOpenResponse:
        logger.debug(f"OpenCloseLog: {open_close_log}")

        return BaseTerminalOpenResponse(
            terminal_id=open_close_log.terminal_info.terminal_id,
            business_date=open_close_log.business_date,
            open_counter=open_close_log.terminal_info.open_counter,
            business_counter=open_close_log.terminal_info.business_counter,
            initial_amount=open_close_log.terminal_info.initial_amount,
            terminal_info=self.transform_terminal(open_close_log.terminal_info),
            receipt_text=open_close_log.receipt_text,
            journal_text=open_close_log.journal_text,
        )

    # tranform OpenCloseLog to BaseTerminalCloseResponseo
    def transform_close_log(self, open_close_log: OpenCloseLog) -> BaseTerminalCloseResponse:
        logger.debug(f"OpenCloseLog: {open_close_log}")

        return BaseTerminalCloseResponse(
            terminal_id=open_close_log.terminal_info.terminal_id,
            business_date=open_close_log.business_date,
            open_counter=open_close_log.terminal_info.open_counter,
            business_counter=open_close_log.terminal_info.business_counter,
            initial_amount=open_close_log.terminal_info.initial_amount,
            physical_amount=open_close_log.terminal_info.physical_amount,
            terminal_info=self.transform_terminal(open_close_log.terminal_info),
            receipt_text=open_close_log.receipt_text,
            journal_text=open_close_log.journal_text,
        )
