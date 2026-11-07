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
Stamp duty configuration settings

This module defines stamp duty rates and thresholds based on Japanese tax regulations
for calculating stamp duties on receipts and other fiscal documents.
"""
from pydantic_settings import BaseSettings
from typing import Any

class StampDutySettings(BaseSettings):
    """
    Stamp duty settings class
    
    Contains configuration for stamp duty calculation rates and thresholds.
    In Japan, stamp duties are required on various fiscal documents including 
    receipts, with the amount varying based on the transaction value.
    
    Attributes:
        STAMP_DUTY_MASTER: List of stamp duty definitions including:
            - stamp_duty_no: Unique identifier for the duty tier
            - target_amount: Lower bound of this duty tier, inclusive (in JPY)
            - stamp_duty_amount: Amount of stamp duty to apply (in JPY)

    The tiers follow the rate table for receipts of sales proceeds (Stamp Tax Act,
    Appended Table 1, document No. 17; National Tax Agency No. 7141), which is cut
    as "50,000 yen or more, up to 1 million", "more than 1 million, up to 2
    million", ... "more than 1 billion". The cart takes the first tier, highest
    first, with ``target_amount <= x``, where x is in whole yen (fractions are
    floored). So a tier that starts at "more than N yen" has the lower bound
    N + 1: exactly 1,000,000 yen is in the 200-yen tier, not the 400-yen one.
    Only the lowest tier starts at "or more", so it stays at 50,000.
    """

    # Stamp Duty Master
    STAMP_DUTY_MASTER: list[dict[str, Any]] = [
        {
            # more than 1 billion yen
            "stamp_duty_no": 1,
            "target_amount": 1_000_000_001,
            "stamp_duty_amount": 200_000,
        },
        {
            # more than 500 million, up to 1 billion yen
            "stamp_duty_no": 2,
            "target_amount": 500_000_001,
            "stamp_duty_amount": 150_000,
        },
        {
            # more than 300 million, up to 500 million yen
            "stamp_duty_no": 3,
            "target_amount": 300_000_001,
            "stamp_duty_amount": 100_000,
        },
        {
            # more than 200 million, up to 300 million yen
            "stamp_duty_no": 4,
            "target_amount": 200_000_001,
            "stamp_duty_amount": 60_000,
        },
        {
            # more than 100 million, up to 200 million yen
            "stamp_duty_no": 5,
            "target_amount": 100_000_001,
            "stamp_duty_amount": 40_000,
        },
        {
            # more than 50 million, up to 100 million yen
            "stamp_duty_no": 6,
            "target_amount": 50_000_001,
            "stamp_duty_amount": 20_000,
        },
        {
            # more than 30 million, up to 50 million yen
            "stamp_duty_no": 7,
            "target_amount": 30_000_001,
            "stamp_duty_amount": 10_000,
        },
        {
            # more than 20 million, up to 30 million yen
            "stamp_duty_no": 8,
            "target_amount": 20_000_001,
            "stamp_duty_amount": 6_000,
        },
        {
            # more than 10 million, up to 20 million yen
            "stamp_duty_no": 9,
            "target_amount": 10_000_001,
            "stamp_duty_amount": 4_000,
        },
        {
            # more than 5 million, up to 10 million yen
            "stamp_duty_no": 10,
            "target_amount": 5_000_001,
            "stamp_duty_amount": 2_000,
        },
        {
            # more than 3 million, up to 5 million yen
            "stamp_duty_no": 11,
            "target_amount": 3_000_001,
            "stamp_duty_amount": 1_000,
        },
        {
            # more than 2 million, up to 3 million yen
            "stamp_duty_no": 12,
            "target_amount": 2_000_001,
            "stamp_duty_amount": 600,
        },
        {
            # more than 1 million, up to 2 million yen
            "stamp_duty_no": 13,
            "target_amount": 1_000_001,
            "stamp_duty_amount": 400,
        },
        {
            # 50,000 yen or more, up to 1 million yen
            "stamp_duty_no": 14,
            "target_amount": 50_000,
            "stamp_duty_amount": 200,
        },
    ]
