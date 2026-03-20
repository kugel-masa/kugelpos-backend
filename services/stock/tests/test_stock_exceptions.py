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
import pytest

from app.exceptions.stock_exceptions import (
    StockNotFoundError,
    InsufficientStockError,
    StockValidationError,
    StockAccessDeniedError,
    StockDatabaseError,
    StockUpdateFailedError,
    StockUpdateValidationError,
    StockUpdateConflictError,
    SnapshotCreationFailedError,
    SnapshotNotFoundError,
    ExternalServiceError,
    PubSubError,
    StateStoreError,
    TransactionProcessingError,
    TransactionValidationError,
    TransactionDuplicateError,
)
from app.exceptions.stock_error_codes import (
    StockErrorCode,
    StockErrorMessage,
    get_message,
    extend_messages,
)


# ---------------------------------------------------------------------------
# All 15 exception classes: instantiate with message, verify no crash
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exc_class,expected_code",
    [
        (StockNotFoundError, StockErrorCode.STOCK_NOT_FOUND),
        (InsufficientStockError, StockErrorCode.INSUFFICIENT_STOCK),
        (StockValidationError, StockErrorCode.STOCK_VALIDATION_ERROR),
        (StockAccessDeniedError, StockErrorCode.STOCK_ACCESS_DENIED),
        (StockDatabaseError, StockErrorCode.STOCK_DATABASE_ERROR),
        (StockUpdateFailedError, StockErrorCode.STOCK_UPDATE_FAILED),
        (StockUpdateValidationError, StockErrorCode.STOCK_UPDATE_VALIDATION_ERROR),
        (StockUpdateConflictError, StockErrorCode.STOCK_UPDATE_CONFLICT),
        (SnapshotCreationFailedError, StockErrorCode.SNAPSHOT_CREATION_FAILED),
        (SnapshotNotFoundError, StockErrorCode.SNAPSHOT_NOT_FOUND),
        (ExternalServiceError, StockErrorCode.EXTERNAL_SERVICE_ERROR),
        (PubSubError, StockErrorCode.PUBSUB_ERROR),
        (StateStoreError, StockErrorCode.STATE_STORE_ERROR),
        (TransactionProcessingError, StockErrorCode.TRANSACTION_PROCESSING_ERROR),
        (TransactionValidationError, StockErrorCode.TRANSACTION_VALIDATION_ERROR),
        (TransactionDuplicateError, StockErrorCode.TRANSACTION_DUPLICATE),
    ],
)
class TestStockExceptions:
    def test_instantiate_with_message(self, exc_class, expected_code):
        """Each exception can be instantiated with just a message string."""
        exc = exc_class(message="test error")
        assert exc.error_code == expected_code

    def test_instantiate_with_original_exception(self, exc_class, expected_code):
        """Each exception accepts an optional original_exception."""
        original = ValueError("root cause")
        exc = exc_class(message="wrapper", original_exception=original)
        assert exc.error_code == expected_code


# ---------------------------------------------------------------------------
# StockErrorMessage / get_message / extend_messages fallback paths
# ---------------------------------------------------------------------------

class TestStockErrorCodes:
    def test_get_message_known_code_ja(self):
        """Known error code returns Japanese message by default."""
        msg = get_message(StockErrorCode.STOCK_NOT_FOUND, lang="ja")
        assert msg == "在庫情報が見つかりません"

    def test_get_message_known_code_en(self):
        """Known error code returns English message."""
        msg = get_message(StockErrorCode.STOCK_NOT_FOUND, lang="en")
        assert msg == "Stock not found"

    def test_get_message_unknown_code_falls_back_to_ja(self):
        """Unknown code with unknown lang falls back to ja, then to formatted fallback."""
        msg = get_message("999999", lang="xx")
        # lang "xx" not in merged messages, falls to ja fallback
        # "999999" not in ja either, so returns formatted fallback
        assert "999999" in msg

    def test_get_message_unknown_code_default_fallback(self):
        """Unknown code in 'ja' returns formatted fallback string."""
        msg = get_message("999999", lang="ja")
        assert "999999" in msg

    def test_extend_messages_merges_common_and_stock(self):
        """extend_messages includes both common and stock-specific codes."""
        merged = extend_messages()
        # Common code should be present
        assert "100000" in merged["ja"]
        # Stock code should be present
        assert StockErrorCode.STOCK_NOT_FOUND in merged["ja"]

    def test_extend_messages_new_lang_in_stock(self):
        """If StockErrorMessage has a language not in common, it gets added.
        (Covers line 128: merged_messages[lang] = {})
        """
        # Temporarily add a new language to StockErrorMessage
        original = StockErrorMessage.MESSAGES.copy()
        try:
            StockErrorMessage.MESSAGES["fr"] = {
                StockErrorCode.STOCK_NOT_FOUND: "Stock introuvable",
            }
            merged = extend_messages()
            assert "fr" in merged
            assert merged["fr"][StockErrorCode.STOCK_NOT_FOUND] == "Stock introuvable"
        finally:
            StockErrorMessage.MESSAGES.clear()
            StockErrorMessage.MESSAGES.update(original)

    def test_get_message_unknown_lang_falls_back(self):
        """get_message with unknown lang falls back to ja default.
        (Covers line 151: fallback path in get_message)
        """
        msg = get_message(StockErrorCode.STOCK_NOT_FOUND, lang="zz")
        # "zz" not in merged, falls to ja
        assert msg == "在庫情報が見つかりません"
