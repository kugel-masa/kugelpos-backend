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
"""
例外クラスモジュール
"""

# Base exceptions
from .base_exceptions import AppException, DatabaseException, RepositoryException, ServiceException

# Repository exceptions
from .repository_exceptions import (
    NotFoundException, 
    CannotCreateException, 
    CannotDeleteException,
    UpdateNotWorkException,
    ReplaceNotWorkException,
    DeleteChildExistException,
    AlreadyExistException,
    DuplicateKeyException,
    LoadDataNoExistException
)

# Service exceptions
from .service_exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    BadRequestBodyException,
    InvalidRequestDataException,
    EventBadSequenceException,
    StrategyPluginException
)

# Exception handlers
from .exception_handlers import register_exception_handlers

__all__ = [
    # Base exceptions
    'AppException', 'DatabaseException', 'RepositoryException', 'ServiceException',
    
    # Repository exceptions
    'NotFoundException', 'CannotCreateException', 'CannotDeleteException',
    'UpdateNotWorkException', 'ReplaceNotWorkException', 'DeleteChildExistException',
    'AlreadyExistException', 'DuplicateKeyException', 'LoadDataNoExistException',
    
    # Service exceptions
    'DocumentNotFoundException', 'DocumentAlreadyExistsException', 
    'BadRequestBodyException', 'InvalidRequestDataException', 'EventBadSequenceException',
    'StrategyPluginException',
    
    # Exception handlers
    'register_exception_handlers'
]