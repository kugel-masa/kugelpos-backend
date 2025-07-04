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
from enum import Enum

class TaxType(Enum):
    """
    Enum representing types of tax application methods in transactions.
    
    External: Tax is added to the price (e.g., 100 yen + 10% tax = 110 yen)
    Internal: Tax is included in the price (e.g., 110 yen includes 10% tax)
    Exempt: No tax is applied to the item
    """
    External:str = "External"
    Internal:str = "Internal"
    Exempt:str = "Exempt"

class RoundMethod(Enum):
    """
    Enum representing tax amount rounding methods.
    
    These methods are used when calculating tax amounts to determine
    how fractional parts should be handled.
    """
    # Round to the nearest integer
    Round = "Round"
    # Round down to the nearest integer
    Floor = "Floor"
    # Round up to the nearest integer
    Ceil = "Ceil"

class TransactionType(Enum):
    """
    Enum representing the different types of transactions in the POS system.
    
    Each transaction type is associated with a specific numeric code to
    facilitate identification and processing of different operation types.
    """
    NormalSales:int = 101           # Standard sales transaction
    NormalSalesCancel:int = -101    # Cancellation of a normal sales transaction before billing
    ReturnSales:int = 102           # Return of previously sold items
    VoidSales:int = 201             # Cancellation of a sales transaction
    VoidReturn:int = 202            # Cancellation of a return transaction
    Open:int = 301                  # Terminal opening operation
    Close:int = 302                 # Terminal closing operation
    CashIn:int = 401                # Cash deposit into the terminal
    CashOut:int = 402               # Cash withdrawal from the terminal
    FlashReport:int = 501           # Sales flash report (interim report)
    DailyReport:int = 502           # Sales daily report (closing report)
