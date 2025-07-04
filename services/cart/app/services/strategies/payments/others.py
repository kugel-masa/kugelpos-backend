# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.strategies.payments.cashless import PaymentByCashless
from logging import getLogger

logger = getLogger(__name__)


class PaymentByOthers(PaymentByCashless):
    """
    Other payment methods strategy implementation.

    This class implements the payment strategy for other types of payment methods
    that aren't specifically cash or standard cashless methods. Examples might
    include gift cards, store credit, or other specialized payment types.

    This strategy inherits all behavior from the cashless payment strategy,
    following the same validation rules (no change given, payment cannot exceed balance).

    This payment method is typically identified by the payment code "12" in the system.
    """

    pass
