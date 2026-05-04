"""
Unit tests for master-data service exception classes and error codes.
"""
import pytest
from unittest.mock import MagicMock
from fastapi import status

# Patch missing ItemNotFoundException in kugel_common.exceptions before
# app.exceptions.__init__ tries to import it.
import kugel_common.exceptions as _kc_exc

if not hasattr(_kc_exc, "ItemNotFoundException"):
    _kc_exc.ItemNotFoundException = type("ItemNotFoundException", (Exception,), {})

from app.exceptions.master_data_error_codes import MasterDataErrorCode, MasterDataErrorMessage
from app.exceptions.master_data_exceptions import (
    MasterDataNotFoundException,
    MasterDataAlreadyExistsException,
    MasterDataCannotCreateException,
    MasterDataCannotUpdateException,
    MasterDataCannotDeleteException,
    MasterDataValidationException,
    ProductNotFoundException,
    ProductCodeDuplicateException,
    ProductInvalidPriceException,
    ProductInvalidTaxRateException,
    PriceNotFoundException,
    PriceInvalidAmountException,
    PriceInvalidDateRangeException,
    CustomerNotFoundException,
    CustomerIdDuplicateException,
    StoreNotFoundException,
    StoreCodeDuplicateException,
    DepartmentNotFoundException,
    DepartmentCodeDuplicateException,
)


# ---------------------------------------------------------------------------
# RepositoryException-based classes (require collection_name)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exc_class,expected_code,expected_status",
    [
        (MasterDataNotFoundException, MasterDataErrorCode.MASTER_DATA_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (MasterDataAlreadyExistsException, MasterDataErrorCode.MASTER_DATA_ALREADY_EXISTS, status.HTTP_409_CONFLICT),
        (MasterDataCannotCreateException, MasterDataErrorCode.MASTER_DATA_CANNOT_CREATE, status.HTTP_400_BAD_REQUEST),
        (MasterDataCannotUpdateException, MasterDataErrorCode.MASTER_DATA_CANNOT_UPDATE, status.HTTP_400_BAD_REQUEST),
        (MasterDataCannotDeleteException, MasterDataErrorCode.MASTER_DATA_CANNOT_DELETE, status.HTTP_400_BAD_REQUEST),
    ],
)
class TestRepositoryExceptions:
    def test_instantiate_without_data_id(self, exc_class, expected_code, expected_status):
        exc = exc_class(message="test error", collection_name="test_collection")
        assert exc.error_code == expected_code
        assert exc.status_code == expected_status

    def test_instantiate_with_data_id(self, exc_class, expected_code, expected_status):
        exc = exc_class(message="test error", collection_name="col", data_id="123")
        assert exc.error_code == expected_code
        assert "data_id->123" in str(exc)

    def test_instantiate_with_original_exception(self, exc_class, expected_code, expected_status):
        original = ValueError("root cause")
        exc = exc_class(
            message="wrapper", collection_name="col", original_exception=original
        )
        assert exc.error_code == expected_code


# ---------------------------------------------------------------------------
# ServiceException-based classes (no collection_name)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exc_class,expected_code,expected_status",
    [
        (MasterDataValidationException, MasterDataErrorCode.MASTER_DATA_VALIDATION_ERROR, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (ProductNotFoundException, MasterDataErrorCode.PRODUCT_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (ProductCodeDuplicateException, MasterDataErrorCode.PRODUCT_CODE_DUPLICATE, status.HTTP_409_CONFLICT),
        (ProductInvalidPriceException, MasterDataErrorCode.PRODUCT_INVALID_PRICE, status.HTTP_400_BAD_REQUEST),
        (ProductInvalidTaxRateException, MasterDataErrorCode.PRODUCT_INVALID_TAX_RATE, status.HTTP_400_BAD_REQUEST),
        (PriceNotFoundException, MasterDataErrorCode.PRICE_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (PriceInvalidAmountException, MasterDataErrorCode.PRICE_INVALID_AMOUNT, status.HTTP_400_BAD_REQUEST),
        (PriceInvalidDateRangeException, MasterDataErrorCode.PRICE_INVALID_DATE_RANGE, status.HTTP_400_BAD_REQUEST),
        (CustomerNotFoundException, MasterDataErrorCode.CUSTOMER_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (CustomerIdDuplicateException, MasterDataErrorCode.CUSTOMER_ID_DUPLICATE, status.HTTP_409_CONFLICT),
        (StoreNotFoundException, MasterDataErrorCode.STORE_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (StoreCodeDuplicateException, MasterDataErrorCode.STORE_CODE_DUPLICATE, status.HTTP_409_CONFLICT),
        (DepartmentNotFoundException, MasterDataErrorCode.DEPARTMENT_NOT_FOUND, status.HTTP_404_NOT_FOUND),
        (DepartmentCodeDuplicateException, MasterDataErrorCode.DEPARTMENT_CODE_DUPLICATE, status.HTTP_409_CONFLICT),
    ],
)
class TestServiceExceptions:
    def test_instantiate_with_message(self, exc_class, expected_code, expected_status):
        exc = exc_class(message="test error")
        assert exc.error_code == expected_code
        assert exc.status_code == expected_status

    def test_instantiate_with_original_exception(self, exc_class, expected_code, expected_status):
        original = ValueError("root cause")
        exc = exc_class(message="wrapper", original_exception=original)
        assert exc.error_code == expected_code


# ---------------------------------------------------------------------------
# MasterDataErrorMessage.get_message fallback paths
# ---------------------------------------------------------------------------

class TestMasterDataErrorMessage:
    def test_get_message_known_code_ja(self):
        msg = MasterDataErrorMessage.get_message(
            MasterDataErrorCode.MASTER_DATA_NOT_FOUND, lang="ja"
        )
        assert msg is not None
        assert len(msg) > 0

    def test_get_message_known_code_en(self):
        msg = MasterDataErrorMessage.get_message(
            MasterDataErrorCode.MASTER_DATA_NOT_FOUND, lang="en"
        )
        assert msg == "Master data not found"

    def test_get_message_default_language_used_when_none(self):
        """lang=None should use DEFAULT_LANGUAGE (ja)."""
        msg = MasterDataErrorMessage.get_message(
            MasterDataErrorCode.PRODUCT_NOT_FOUND, lang=None
        )
        assert msg is not None

    def test_get_message_unsupported_lang_falls_back(self):
        """Unsupported language falls back to DEFAULT_LANGUAGE."""
        msg = MasterDataErrorMessage.get_message(
            MasterDataErrorCode.PRODUCT_NOT_FOUND, lang="zz"
        )
        assert msg is not None

    def test_get_message_unknown_code_with_default_message(self):
        """Unknown code with default_message returns that default."""
        msg = MasterDataErrorMessage.get_message(
            "999999", default_message="custom fallback"
        )
        assert msg == "custom fallback"

    def test_get_message_unknown_code_without_default_message(self):
        """Unknown code without default_message returns system default."""
        msg = MasterDataErrorMessage.get_message("999999")
        assert msg is not None
        assert len(msg) > 0

    def test_get_message_unknown_code_non_default_lang_retries_default(self):
        """Unknown code in 'en' retries with default lang (ja), then falls back."""
        msg = MasterDataErrorMessage.get_message("999999", lang="en")
        assert msg is not None

    def test_extend_messages_merges_into_common(self):
        """extend_messages adds master-data codes to CommonErrorMessage."""
        from kugel_common.exceptions.error_codes import ErrorMessage as CommonErrorMessage

        # After module import, extend_messages was already called.
        # Verify master-data codes exist in common messages.
        assert MasterDataErrorCode.MASTER_DATA_NOT_FOUND in CommonErrorMessage.MESSAGES["ja"]
        assert MasterDataErrorCode.MASTER_DATA_NOT_FOUND in CommonErrorMessage.MESSAGES["en"]
