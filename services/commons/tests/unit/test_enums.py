# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.enums."""
import pytest

from kugel_common.enums import RoundMethod, TaxType, TransactionType


class TestTaxType:
    def test_values(self):
        assert TaxType.External.value == "External"
        assert TaxType.Internal.value == "Internal"
        assert TaxType.Exempt.value == "Exempt"

    def test_lookup_by_value(self):
        assert TaxType("External") is TaxType.External
        assert TaxType("Exempt") is TaxType.Exempt

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            TaxType("WrongValue")


class TestRoundMethod:
    def test_values(self):
        assert RoundMethod.Round.value == "Round"
        assert RoundMethod.Floor.value == "Floor"
        assert RoundMethod.Ceil.value == "Ceil"

    def test_three_members(self):
        assert len(list(RoundMethod)) == 3


class TestTransactionType:
    def test_known_values(self):
        assert TransactionType.NormalSales.value == 101
        assert TransactionType.NormalSalesCancel.value == -101
        assert TransactionType.ReturnSales.value == 102
        assert TransactionType.VoidSales.value == 201
        assert TransactionType.VoidReturn.value == 202
        assert TransactionType.Open.value == 301
        assert TransactionType.Close.value == 302
        assert TransactionType.CashIn.value == 401
        assert TransactionType.CashOut.value == 402
        assert TransactionType.FlashReport.value == 501
        assert TransactionType.DailyReport.value == 502

    def test_lookup_by_value(self):
        assert TransactionType(101) is TransactionType.NormalSales
        assert TransactionType(-101) is TransactionType.NormalSalesCancel

    def test_codes_are_unique(self):
        values = [m.value for m in TransactionType]
        assert len(values) == len(set(values))

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            TransactionType(99999)
