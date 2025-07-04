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
            - target_amount: Lower threshold amount for this duty tier (in JPY)
            - stamp_duty_amount: Amount of stamp duty to apply (in JPY)
    """
    # Stamp Duty Master
    STAMP_DUTY_MASTER: list[dict[str, Any]] = [
        {
            # 1 billion yen or more
            "stamp_duty_no": 1,
            "target_amount": 1_000_000_000,
            "stamp_duty_amount": 200_000,
        },
        {
            # 500 million yen to less than 1 billion yen
            "stamp_duty_no": 2,
            "target_amount": 500_000_000,
            "stamp_duty_amount": 150_000,
        },
        {
            # 300 million yen to less than 500 million yen
            "stamp_duty_no": 3,
            "target_amount": 300_000_000,
            "stamp_duty_amount": 100_000,
        },
        {
            # 200 million yen to less than 300 million yen
            "stamp_duty_no": 4,
            "target_amount": 200_000_000,
            "stamp_duty_amount": 60_000,
        },
        {
            # 100 million yen to less than 200 million yen
            "stamp_duty_no": 5,
            "target_amount": 100_000_000,
            "stamp_duty_amount": 40_000,
        },
        {
            # 50 million yen to less than 100 million yen
            "stamp_duty_no": 6,
            "target_amount": 50_000_000,
            "stamp_duty_amount": 20_000,
        },
        {
            # 30 million yen to less than 50 million yen
            "stamp_duty_no": 7,
            "target_amount": 30_000_000,
            "stamp_duty_amount": 10_000,
        },
        {
            # 20 million yen to less than 30 million yen
            "stamp_duty_no": 8,
            "target_amount": 20_000_000,
            "stamp_duty_amount": 6_000,
        },
        {
            # 10 million yen to less than 20 million yen
            "stamp_duty_no": 9,
            "target_amount": 10_000_000,
            "stamp_duty_amount": 4_000,
        },
        {
            # 5 million yen to less than 10 million yen
            "stamp_duty_no": 10,
            "target_amount": 5_000_000,
            "stamp_duty_amount": 2_000,
        },
        {
            # 3 million yen to less than 5 million yen
            "stamp_duty_no": 11,
            "target_amount": 3_000_000,
            "stamp_duty_amount": 1_000,
        },
        {
            # 2 million yen to less than 3 million yen
            "stamp_duty_no": 12,
            "target_amount": 2_000_000,
            "stamp_duty_amount": 600,
        },
        {
            # 1 million yen to less than 2 million yen
            "stamp_duty_no": 13,
            "target_amount": 1_000_000,
            "stamp_duty_amount": 400,
        },
        {
            # 50,000 yen to less than 1 million yen
            "stamp_duty_no": 14,
            "target_amount": 50_000,
            "stamp_duty_amount": 200,
        }
    ]