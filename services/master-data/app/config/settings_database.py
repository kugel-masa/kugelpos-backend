# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic_settings import BaseSettings


class DBCollectionSettings(BaseSettings):
    DB_COLLECTION_NAME_ACCOUNT: str = "info_account"
    DB_COLLECTION_NAME_STAFF_MASTER: str = "master_staff"
    DB_COLLECTION_NAME_CATEGORY_MASTER: str = "master_category"
    DB_COLLECTION_NAME_ITEM_COMMON_MASTER: str = "master_item_common"
    DB_COLLECTION_NAME_ITEM_STORE_MASTER: str = "master_item_store"
    DB_COLLECTION_NAME_ITEM_BOOK_MASTER: str = "master_item_book"
    DB_COLLECTION_NAME_PAYMENT_MASTER: str = "master_payment"
    DB_COLLECTION_NAME_SETTINGS_MASTER: str = "master_settings"
    DB_COLLECTION_NAME_KEY_PRESET_MASTER: str = "master_key_preset"
    DB_COLLECTION_NAME_TAX_MASTER: str = "master_tax"
