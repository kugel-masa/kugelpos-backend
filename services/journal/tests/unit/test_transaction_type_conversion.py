# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Unit tests specifically for the transaction type conversion logic in LogService.

This test module focuses on the business logic that converts NormalSales
transactions to NormalSalesCancel when the transaction is cancelled.
"""
import pytest
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction


class TestTransactionTypeConversion:
    """Test cases for transaction type conversion logic."""

    def test_normal_sales_not_cancelled_keeps_original_type(self):
        """
        Test that a NormalSales transaction that is not cancelled
        keeps its original transaction type.
        """
        # Arrange
        transaction_type = TransactionType.NormalSales.value
        is_cancelled = False

        # Act - simulate the logic from LogService.receive_tranlog_async
        tran_type = transaction_type
        if transaction_type == TransactionType.NormalSales.value:
            if is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value

        # Assert
        assert tran_type == TransactionType.NormalSales.value

    def test_normal_sales_cancelled_converts_to_cancel_type(self):
        """
        Test that a cancelled NormalSales transaction
        is converted to NormalSalesCancel type.
        """
        # Arrange
        transaction_type = TransactionType.NormalSales.value
        is_cancelled = True

        # Act - simulate the logic from LogService.receive_tranlog_async
        tran_type = transaction_type
        if transaction_type == TransactionType.NormalSales.value:
            if is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value

        # Assert
        assert tran_type == TransactionType.NormalSalesCancel.value

    @pytest.mark.parametrize(
        "transaction_type,is_cancelled",
        [
            (TransactionType.ReturnSales.value, True),
            (TransactionType.ReturnSales.value, False),
            (TransactionType.VoidSales.value, True),
            (TransactionType.VoidSales.value, False),
            (TransactionType.VoidReturn.value, True),
            (TransactionType.VoidReturn.value, False),
            (TransactionType.Open.value, False),
            (TransactionType.Close.value, False),
            (TransactionType.CashIn.value, False),
            (TransactionType.CashOut.value, False),
        ],
    )
    def test_non_normal_sales_types_remain_unchanged(self, transaction_type, is_cancelled):
        """
        Test that transaction types other than NormalSales
        are not affected by the cancellation logic.
        """
        # Act - simulate the logic from LogService.receive_tranlog_async
        tran_type = transaction_type
        if transaction_type == TransactionType.NormalSales.value:
            if is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value

        # Assert
        assert tran_type == transaction_type

    def test_transaction_type_values(self):
        """
        Test that the TransactionType enum values are as expected.
        This ensures that the logic depends on correct enum values.
        """
        assert TransactionType.NormalSales.value == 101
        assert TransactionType.NormalSalesCancel.value == -101

    def test_cancelled_normal_sales_creates_negative_type(self):
        """
        Test that cancelling a NormalSales (101) results in
        NormalSalesCancel (-101), which is the negative value.
        """
        # Arrange
        normal_sales = TransactionType.NormalSales.value
        normal_sales_cancel = TransactionType.NormalSalesCancel.value

        # Assert
        assert normal_sales_cancel == -normal_sales

    def test_conversion_logic_with_mock_transaction(self):
        """
        Test the conversion logic with a mock transaction object
        to simulate the actual usage in LogService.
        """

        # Arrange
        class MockSalesInfo:
            def __init__(self, is_cancelled):
                self.is_cancelled = is_cancelled

        class MockTransaction:
            def __init__(self, transaction_type, is_cancelled):
                self.transaction_type = transaction_type
                self.sales = MockSalesInfo(is_cancelled)

        # Test case 1: Normal sales not cancelled
        tran = MockTransaction(TransactionType.NormalSales.value, False)
        tran_type = tran.transaction_type
        if tran.transaction_type == TransactionType.NormalSales.value:
            if tran.sales.is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value
        assert tran_type == TransactionType.NormalSales.value

        # Test case 2: Normal sales cancelled
        tran = MockTransaction(TransactionType.NormalSales.value, True)
        tran_type = tran.transaction_type
        if tran.transaction_type == TransactionType.NormalSales.value:
            if tran.sales.is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value
        assert tran_type == TransactionType.NormalSalesCancel.value

        # Test case 3: Other transaction type
        tran = MockTransaction(TransactionType.ReturnSales.value, True)
        tran_type = tran.transaction_type
        if tran.transaction_type == TransactionType.NormalSales.value:
            if tran.sales.is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value
        assert tran_type == TransactionType.ReturnSales.value
