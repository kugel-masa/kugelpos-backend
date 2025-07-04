# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.exceptions.base_exceptions import ServiceException, RepositoryException
from .master_data_error_codes import MasterDataErrorCode, MasterDataErrorMessage
from fastapi import status

"""
master-data サービス固有の例外クラスを定義します
"""


# マスターデータ基本例外
class MasterDataNotFoundException(RepositoryException):
    """
    Exception raised when master data is not found.
    マスターデータが見つからない場合に発生する例外
    """

    def __init__(self, message, collection_name, data_id=None, logger=None, original_exception=None):
        if data_id:
            message = f"{message}: data_id->{data_id}"
        super().__init__(
            message,
            collection_name,
            logger,
            original_exception,
            MasterDataErrorCode.MASTER_DATA_NOT_FOUND,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.MASTER_DATA_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class MasterDataAlreadyExistsException(RepositoryException):
    """
    Exception raised when master data already exists.
    マスターデータがすでに存在する場合に発生する例外
    """

    def __init__(self, message, collection_name, data_id=None, logger=None, original_exception=None):
        if data_id:
            message = f"{message}: data_id->{data_id}"
        super().__init__(
            message,
            collection_name,
            logger,
            original_exception,
            MasterDataErrorCode.MASTER_DATA_ALREADY_EXISTS,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.MASTER_DATA_ALREADY_EXISTS),
            status_code=status.HTTP_409_CONFLICT,
        )


class MasterDataCannotCreateException(RepositoryException):
    """
    Exception raised when a master data cannot be created.
    マスターデータが作成できない場合に発生する例外
    """

    def __init__(self, message, collection_name, data_id=None, logger=None, original_exception=None):
        if data_id:
            message = f"{message}: data_id->{data_id}"
        super().__init__(
            message,
            collection_name,
            logger,
            original_exception,
            MasterDataErrorCode.MASTER_DATA_CANNOT_CREATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.MASTER_DATA_CANNOT_CREATE),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MasterDataCannotUpdateException(RepositoryException):
    """
    Exception raised when a master data cannot be updated.
    マスターデータが更新できない場合に発生する例外
    """

    def __init__(self, message, collection_name, data_id=None, logger=None, original_exception=None):
        if data_id:
            message = f"{message}: data_id->{data_id}"
        super().__init__(
            message,
            collection_name,
            logger,
            original_exception,
            MasterDataErrorCode.MASTER_DATA_CANNOT_UPDATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.MASTER_DATA_CANNOT_UPDATE),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MasterDataCannotDeleteException(RepositoryException):
    """
    Exception raised when a master data cannot be deleted.
    マスターデータが削除できない場合に発生する例外
    """

    def __init__(self, message, collection_name, data_id=None, logger=None, original_exception=None):
        if data_id:
            message = f"{message}: data_id->{data_id}"
        super().__init__(
            message,
            collection_name,
            logger,
            original_exception,
            MasterDataErrorCode.MASTER_DATA_CANNOT_DELETE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.MASTER_DATA_CANNOT_DELETE),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MasterDataValidationException(ServiceException):
    """
    Exception raised when master data validation fails.
    マスターデータの検証が失敗した場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.MASTER_DATA_VALIDATION_ERROR,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.MASTER_DATA_VALIDATION_ERROR),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


# 商品マスター関連例外
class ProductNotFoundException(ServiceException):
    """
    Exception raised when a product is not found.
    商品が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRODUCT_NOT_FOUND,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRODUCT_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ProductCodeDuplicateException(ServiceException):
    """
    Exception raised when a product code is duplicate.
    商品コードが重複している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRODUCT_CODE_DUPLICATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRODUCT_CODE_DUPLICATE),
            status_code=status.HTTP_409_CONFLICT,
        )


class ProductInvalidPriceException(ServiceException):
    """
    Exception raised when a product price is invalid.
    商品価格が無効な場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRODUCT_INVALID_PRICE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRODUCT_INVALID_PRICE),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ProductInvalidTaxRateException(ServiceException):
    """
    Exception raised when a product tax rate is invalid.
    商品税率が無効な場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRODUCT_INVALID_TAX_RATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRODUCT_INVALID_TAX_RATE),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# 価格マスター関連例外
class PriceNotFoundException(ServiceException):
    """
    Exception raised when a price is not found.
    価格が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRICE_NOT_FOUND,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRICE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class PriceInvalidAmountException(ServiceException):
    """
    Exception raised when a price amount is invalid.
    価格金額が無効な場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRICE_INVALID_AMOUNT,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRICE_INVALID_AMOUNT),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class PriceInvalidDateRangeException(ServiceException):
    """
    Exception raised when a price date range is invalid.
    価格の適用期間が無効な場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.PRICE_INVALID_DATE_RANGE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.PRICE_INVALID_DATE_RANGE),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# 顧客マスター関連例外
class CustomerNotFoundException(ServiceException):
    """
    Exception raised when a customer is not found.
    顧客が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.CUSTOMER_NOT_FOUND,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.CUSTOMER_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class CustomerIdDuplicateException(ServiceException):
    """
    Exception raised when a customer ID is duplicate.
    顧客IDが重複している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.CUSTOMER_ID_DUPLICATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.CUSTOMER_ID_DUPLICATE),
            status_code=status.HTTP_409_CONFLICT,
        )


# 店舗マスター関連例外
class StoreNotFoundException(ServiceException):
    """
    Exception raised when a store is not found.
    店舗が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.STORE_NOT_FOUND,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.STORE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class StoreCodeDuplicateException(ServiceException):
    """
    Exception raised when a store code is duplicate.
    店舗コードが重複している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.STORE_CODE_DUPLICATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.STORE_CODE_DUPLICATE),
            status_code=status.HTTP_409_CONFLICT,
        )


# 部門マスター関連例外
class DepartmentNotFoundException(ServiceException):
    """
    Exception raised when a department is not found.
    部門が見つからない場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.DEPARTMENT_NOT_FOUND,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.DEPARTMENT_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class DepartmentCodeDuplicateException(ServiceException):
    """
    Exception raised when a department code is duplicate.
    部門コードが重複している場合に発生する例外
    """

    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message,
            logger,
            original_exception,
            MasterDataErrorCode.DEPARTMENT_CODE_DUPLICATE,
            MasterDataErrorMessage.get_message(MasterDataErrorCode.DEPARTMENT_CODE_DUPLICATE),
            status_code=status.HTTP_409_CONFLICT,
        )
