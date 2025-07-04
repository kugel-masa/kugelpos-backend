# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from enum import Enum


class StoreStatus(Enum):
    """
    Enum representing the different states of a store.
    Used to track and manage the operational status of the store.
    """

    Idle = "Idle"  # Store is initialized but not yet opened
    Opened = "Opened"  # Store is currently open for business
    Closed = "Closed"  # Store is closed for business
