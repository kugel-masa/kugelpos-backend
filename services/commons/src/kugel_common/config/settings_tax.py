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
"""
Tax configuration settings

This module defines tax-related settings including tax rates, calculation methods,
and tax categorization for use throughout the application.
"""
from pydantic_settings import BaseSettings
from typing import Any
from kugel_common.enums import TaxType, RoundMethod

class TaxSettings(BaseSettings):
    """
    Tax settings class
    
    Contains configuration for tax types, rates and calculation methods used
    for all tax-related calculations in the application.
    
    Attributes:
        TAX_MASTER: List of tax definitions including:
            - tax_code: Unique code for each tax type
            - tax_type: Category of tax (Exempt, External, Internal)
            - tax_name: Human-readable name for the tax type
            - rate: Percentage rate for the tax
            - round_digit: Decimal place for rounding (-1 = tens, 0 = ones, etc.)
            - round_method: Method for rounding (Floor, Ceiling, Round)
    """
    TAX_MASTER: list[dict[str, Any]] = [
        {
            "tax_code": "00",
            "tax_type": TaxType.Exempt.value,
            "tax_name": "非課税",  # Tax exempt
            "rate": 0.0,
            "round_digit": 0,
            "round_method": None
        },
        {
            "tax_code": "01",
            "tax_type": TaxType.External.value,
            "tax_name": "外税10%",  # External tax 10%
            "rate": 10.0,
            "round_digit": -1,
            "round_method": RoundMethod.Floor.value
        },
        {
            "tax_code": "02",
            "tax_type": TaxType.Internal.value,
            "tax_name": "内税10%",  # Internal tax 10% (included in price)
            "rate": 10.0,
            "round_digit": -1,
            "round_method": RoundMethod.Floor.value
        },
        {
            "tax_code": "11",
            "tax_type": TaxType.External.value,
            "tax_name": "外税 8%",  # External tax 8%
            "rate": 8.0,
            "round_digit": -1,
            "round_method": RoundMethod.Floor.value
        },
        {
            "tax_code": "12",
            "tax_type": TaxType.Internal.value,
            "tax_name": "内税 8%",  # Internal tax 8% (included in price)
            "rate": 8.0,
            "round_digit": -1,
            "round_method": RoundMethod.Floor.value
        }
    ]