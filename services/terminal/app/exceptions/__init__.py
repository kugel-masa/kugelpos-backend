# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
terminal サービスの例外モジュール
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
    BadRequestBodyException,
    InvalidRequestDataException,
    EventBadSequenceException,
    StrategyPluginException,
)

# terminalサービス固有のエラーコードとメッセージ
from .terminal_error_codes import TerminalErrorCode, TerminalErrorMessage

# terminal固有の例外
from .terminal_exceptions import (
    # 端末基本操作関連の例外
    TerminalNotFoundException,
    TerminalAlreadyExistsException,
    # 端末状態関連の例外
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
    # サインイン関連の例外
    SignInOutException,
    SignInRequiredException,
    InvalidCredentialsException,
    # 金銭出納関連の例外
    CashInOutException,
    CashAmountInvalidException,
    CashDrawerClosedException,
    OverMaxAmountException,
    UnderMinAmountException,
    PhysicalAmountMismatchException,
    # テナント関連の例外
    TenantNotFoundException,
    TenantAlreadyExistsException,
    TenantUpdateException,
    TenantDeleteException,
    TenantConfigException,
    TenantCreateException,
    # 店舗関連の例外
    StoreNotFoundException,
    StoreAlreadyExistsException,
    StoreUpdateException,
    StoreDeleteException,
    StoreConfigException,
    BusinessDateException,
    # 外部サービス関連の例外
    ExternalServiceException,
    MasterDataServiceException,
    CartServiceException,
    JournalServiceException,
    ReportServiceException,
    # その他の例外
    InternalErrorException,
    UnexpectedErrorException,
)
