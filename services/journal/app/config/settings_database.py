# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic_settings import BaseSettings


class DBCollectionSettings(BaseSettings):
    DB_COLLECTION_NAME_TRAN: str = "log_tran"
    DB_COLLECTION_NAME_CASH_IN_OUT_LOG: str = "log_cash_in_out"
    DB_COLLECTION_NAME_OPEN_CLOSE_LOG: str = "log_open_close"
    DB_COLLECTION_NAME_JOURNAL: str = "journal"
