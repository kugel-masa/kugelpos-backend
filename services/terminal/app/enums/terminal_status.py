# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal Status Enumeration

This module defines the possible status values for a terminal in the POS system.
The terminal status represents the operational state of the physical terminal device.
"""

from enum import Enum


class TerminalStatus(Enum):
    """
    Terminal Status Enum

    Represents the current operational state of a terminal:
    - Idle: Terminal is initialized but not opened for business
    - Opened: Terminal is open and ready for business operations
    - Closed: Terminal is closed and business operations are not possible
    """

    Idle = "Idle"  # Initial state, not opened for business
    Opened = "Opened"  # Terminal has been opened for business
    Closed = "Closed"  # Terminal has been closed after business
