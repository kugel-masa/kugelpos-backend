# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal Function Mode Enumeration

This module defines the possible function modes for a terminal in the POS system.
The function mode determines what operations are available to users and what
business functions can be performed on the terminal at a given time.
"""

from enum import Enum


class FunctionMode(Enum):
    """
    Terminal Function Mode Enum

    Represents the current operational function mode of a terminal:
    - MainMenu: Default mode showing the main menu options
    - OpenTerminal: Mode for opening the terminal for business
    - Sales: Mode for processing sales transactions
    - Returns: Mode for processing return transactions
    - Void: Mode for voiding transactions
    - Reports: Mode for generating and viewing reports
    - CloseTerminal: Mode for closing the terminal after business
    - Journal: Mode for viewing transaction journal
    - Maintenance: Mode for terminal maintenance functions
    - CashInOut: Mode for cash drawer operations
    """

    MainMenu = "MainMenu"  # Main menu display mode
    OpenTerminal = "OpenTerminal"  # Terminal opening operation mode
    Sales = "Sales"  # Sales transaction processing mode
    Returns = "Returns"  # Return transaction processing mode
    Void = "Void"  # Transaction voiding mode
    Reports = "Reports"  # Report generation and viewing mode
    CloseTerminal = "CloseTerminal"  # Terminal closing operation mode
    Journal = "Journal"  # Transaction journal viewing mode
    Maintenance = "Maintenance"  # Terminal maintenance functions mode
    CashInOut = "CashInOut"  # Cash deposit and withdrawal mode
