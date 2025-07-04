# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument


class TaxMasterDocument(AbstractDocument):
    """
    Document model representing tax configuration.

    This class defines the structure for storing tax rates and calculation methods
    used for pricing and reporting.
    """

    tax_code: Optional[str] = None  # Unique identifier for the tax
    tax_type: Optional[str] = None  # Type of tax (e.g., sales tax, VAT)
    tax_name: Optional[str] = None  # Descriptive name of the tax
    rate: Optional[float] = 0.0  # Tax rate as a decimal
    round_digit: Optional[int] = 0  # Number of decimal places for rounding
    round_method: Optional[str] = None  # Rounding method (e.g., round, ceiling, floor)
