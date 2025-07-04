# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic_settings import BaseSettings


class DBCollectionSettings(BaseSettings):
    DB_COLLECTION_NAME_CACHE_CART: str = "cache_cart"
    DB_COLLECTION_NAME_TRAN_LOG: str = "log_tran"
    DB_COLLECTION_NAME_TRAN_LOG_DELIVERY_STATUS: str = "status_tran_delivery"
    DB_COLLECTION_NAME_STATUS_TRAN: str = "status_tran"
    DB_COLLECTION_NAME_ITEM_MASTER: str = "master_item"
    DB_COLLECTION_NAME_TAX_MASTER: str = "master_tax"
    DB_COLLECTION_NAME_PAYMENT_MASTER: str = "master_payment"
    DB_COLLECTION_NAME_TERMINAL_COUTER: str = "info_terminal_counter"
