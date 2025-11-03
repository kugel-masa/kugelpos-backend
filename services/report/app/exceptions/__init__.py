# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
report サービスの例外モジュール
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

# report サービス固有の例外クラスをインポート
from app.exceptions.report_exceptions import (
    ReportNotFoundException,
    ReportValidationException,
    ReportGenerationException,
    ReportTypeException,
    ReportScopeException,
    ReportDateException,
    ReportDataException,
    TerminalNotClosedException,
    LogsMissingException,
    LogCountMismatchException,
    TransactionMissingException,
    CashInOutMissingException,
    OpenCloseLogMissingException,
    VerificationFailedException,
    ReceiptGenerationException,
    JournalGenerationException,
    ExportException,
    ImportException,
    DailyInfoException,
    ExternalServiceException,
    CategoryMasterDataNotFoundException,
)
