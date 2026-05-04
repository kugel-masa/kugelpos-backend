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

from app.exceptions.terminal_error_codes import TerminalErrorCode, TerminalErrorMessage
from app.exceptions.terminal_exceptions import (
    TerminalNotFoundException,
    TerminalAlreadyExistsException,
    TerminalStatusException,
    TerminalOpenException,
    TerminalCloseException,
    TerminalAlreadyOpenedException,
    TerminalAlreadyClosedException,
    TerminalBusyException,
    TerminalFunctionModeException,
    TerminalNotSignedInException,
    TerminalAlreadySignedInException,
    TerminalSignedOutException,
    SignInOutException,
    SignInRequiredException,
    InvalidCredentialsException,
    CashInOutException,
    CashAmountInvalidException,
    CashDrawerClosedException,
    OverMaxAmountException,
    UnderMinAmountException,
    PhysicalAmountMismatchException,
    TenantNotFoundException,
    TenantAlreadyExistsException,
    TenantUpdateException,
    TenantDeleteException,
    TenantConfigException,
    TenantCreateException,
    StoreNotFoundException,
    StoreAlreadyExistsException,
    StoreUpdateException,
    StoreDeleteException,
    StoreConfigException,
    BusinessDateException,
    ExternalServiceException,
    MasterDataServiceException,
    CartServiceException,
    JournalServiceException,
    ReportServiceException,
    InternalErrorException,
    UnexpectedErrorException,
)


# ---------------------------------------------------------------------------
# Test all 27 exception classes can be instantiated
# ---------------------------------------------------------------------------

ALL_EXCEPTIONS = [
    TerminalNotFoundException,
    TerminalAlreadyExistsException,
    TerminalStatusException,
    TerminalOpenException,
    TerminalCloseException,
    TerminalAlreadyOpenedException,
    TerminalAlreadyClosedException,
    TerminalBusyException,
    TerminalFunctionModeException,
    TerminalNotSignedInException,
    TerminalAlreadySignedInException,
    TerminalSignedOutException,
    SignInOutException,
    SignInRequiredException,
    InvalidCredentialsException,
    CashInOutException,
    CashAmountInvalidException,
    CashDrawerClosedException,
    OverMaxAmountException,
    UnderMinAmountException,
    PhysicalAmountMismatchException,
    TenantNotFoundException,
    TenantAlreadyExistsException,
    TenantUpdateException,
    TenantDeleteException,
    TenantConfigException,
    TenantCreateException,
    StoreNotFoundException,
    StoreAlreadyExistsException,
    StoreUpdateException,
    StoreDeleteException,
    StoreConfigException,
    BusinessDateException,
    ExternalServiceException,
    MasterDataServiceException,
    CartServiceException,
    JournalServiceException,
    ReportServiceException,
    InternalErrorException,
    UnexpectedErrorException,
]


class TestTerminalExceptionsInstantiation:
    @pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS, ids=lambda c: c.__name__)
    def test_instantiate_with_message(self, exc_class):
        """Each exception can be instantiated with just a message string."""
        exc = exc_class("test error message")
        assert str(exc) == "test error message"
        assert exc.error_code is not None
        assert exc.user_message is not None
        assert exc.status_code is not None

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS, ids=lambda c: c.__name__)
    def test_instantiate_with_original_exception(self, exc_class):
        """Each exception can be instantiated with an original exception."""
        original = ValueError("original cause")
        exc = exc_class("test error", original_exception=original)
        assert exc.original_exception is original


# ---------------------------------------------------------------------------
# Test TerminalErrorMessage.get_message
# ---------------------------------------------------------------------------

class TestTerminalErrorMessage:
    def test_get_message_default_language(self):
        """get_message with no lang returns Japanese message (default)."""
        msg = TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_NOT_FOUND)
        assert msg == "端末が見つかりません"

    def test_get_message_english(self):
        """get_message with lang='en' returns English message."""
        msg = TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_NOT_FOUND, lang="en")
        assert msg == "Terminal not found"

    def test_get_message_unsupported_language_falls_back(self):
        """Unsupported language falls back to default language (Japanese)."""
        msg = TerminalErrorMessage.get_message(TerminalErrorCode.TERMINAL_NOT_FOUND, lang="fr")
        # Should fall back to Japanese
        assert msg == "端末が見つかりません"

    def test_get_message_missing_code_with_default(self):
        """Unknown error code with default_message returns default_message."""
        msg = TerminalErrorMessage.get_message("UNKNOWN_CODE", default_message="custom fallback")
        assert msg == "custom fallback"

    def test_get_message_missing_code_no_default(self):
        """Unknown error code without default returns generic default error message."""
        msg = TerminalErrorMessage.get_message("UNKNOWN_CODE")
        # Should return the DEFAULT_ERROR_MESSAGES for default language
        assert msg is not None
        assert len(msg) > 0

    def test_get_message_missing_code_en_falls_back_to_default_lang(self):
        """Unknown code in 'en' tries default language, then generic fallback."""
        msg = TerminalErrorMessage.get_message("UNKNOWN_CODE", lang="en")
        assert msg is not None
        assert len(msg) > 0

    def test_get_message_all_error_codes_have_ja_messages(self):
        """Every error code defined in TerminalErrorCode has a Japanese message."""
        code_attrs = [
            attr for attr in dir(TerminalErrorCode)
            if not attr.startswith("_") and isinstance(getattr(TerminalErrorCode, attr), str)
        ]
        for attr in code_attrs:
            code = getattr(TerminalErrorCode, attr)
            msg = TerminalErrorMessage.get_message(code, lang="ja")
            assert msg is not None, f"Missing ja message for {attr} ({code})"

    def test_get_message_all_error_codes_have_en_messages(self):
        """Every error code defined in TerminalErrorCode has an English message."""
        code_attrs = [
            attr for attr in dir(TerminalErrorCode)
            if not attr.startswith("_") and isinstance(getattr(TerminalErrorCode, attr), str)
        ]
        for attr in code_attrs:
            code = getattr(TerminalErrorCode, attr)
            msg = TerminalErrorMessage.get_message(code, lang="en")
            assert msg is not None, f"Missing en message for {attr} ({code})"
