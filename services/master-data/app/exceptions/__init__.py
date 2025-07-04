# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
master-data サービスの例外モジュール
"""
from kugel_common.exceptions import (
    # 基本例外
    AppException,
    DatabaseException,
    RepositoryException,
    ServiceException,
    # リポジトリ例外
    NotFoundException,
    CannotCreateException,
    CannotDeleteException,
    UpdateNotWorkException,
    ReplaceNotWorkException,
    DeleteChildExistException,
    AlreadyExistException,
    DuplicateKeyException,
    LoadDataNoExistException,
    # サービス例外
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    ItemNotFoundException,
    BadRequestBodyException,
    InvalidRequestDataException,
    EventBadSequenceException,
    StrategyPluginException,
)

# master-dataサービス固有のエラーコードとメッセージ
from .master_data_error_codes import MasterDataErrorCode, MasterDataErrorMessage

# master-data固有の例外
from .master_data_exceptions import (
    # マスターデータ基本例外
    MasterDataNotFoundException,
    MasterDataAlreadyExistsException,
    MasterDataCannotCreateException,
    MasterDataCannotUpdateException,
    MasterDataCannotDeleteException,
    MasterDataValidationException,
    # 商品マスター関連例外
    ProductNotFoundException,
    ProductCodeDuplicateException,
    ProductInvalidPriceException,
    ProductInvalidTaxRateException,
    # 価格マスター関連例外
    PriceNotFoundException,
    PriceInvalidAmountException,
    PriceInvalidDateRangeException,
    # 顧客マスター関連例外
    CustomerNotFoundException,
    CustomerIdDuplicateException,
    # 店舗マスター関連例外
    StoreNotFoundException,
    StoreCodeDuplicateException,
    # 部門マスター関連例外
    DepartmentNotFoundException,
    DepartmentCodeDuplicateException,
)
