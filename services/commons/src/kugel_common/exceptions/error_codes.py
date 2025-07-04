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
Definition of standardized error codes and error messages

This module defines a comprehensive set of error codes and corresponding
error messages in multiple languages for consistent error handling across
all microservices.
"""

# Base error categories (first 2 digits)
# 10: General errors
# 20: Authentication/Authorization errors
# 30: Input validation errors
# 40: Business rule errors
# 50: Database/Repository errors
# 60: External service integration errors
# 90: System errors

class ErrorCode:
    """
    Definition class for standardized error codes
    
    Code structure: XXYYZZ
    XX: Error category
    YY: Subcategory
    ZZ: Detail code
    
    Example: 304001 - Input validation error(30) > Discount related(40) > Insufficient amount(01)
    
    Number ranges reserved for each microservice:
    - 401xx-404xx: Cart service
    - 405xx: Master-data service
    - 406xx-407xx: Terminal service
    - 408xx-409xx: Account service
    - 410xx-411xx: Journal service
    - 412xx-413xx: Report service
    """
    
    # General errors (10YYZZ)
    GENERAL_ERROR = "100000"  # General error
    RESOURCE_NOT_FOUND = "100001"  # Resource not found
    
    # Authentication/Authorization errors (20YYZZ)
    AUTHENTICATION_ERROR = "200001"  # Authentication error
    AUTHORIZATION_ERROR = "200002"  # Authorization error
    
    # Input validation errors (30YYZZ)
    VALIDATION_ERROR = "300001"  # General validation error
    REQUIRED_FIELD_MISSING = "300002"  # Required field missing
    INVALID_FIELD_FORMAT = "300003"  # Invalid field format
    INVALID_OPERATION = "300004"  # Invalid operation
    
    # Business rule errors (40YYZZ)
    # 401xx-404xx: Reserved for Cart service
    # 405xx: Reserved for Master-data service
    # 406xx-407xx: Reserved for Terminal service
    # 408xx-409xx: Reserved for Account service
    # 410xx-411xx: Reserved for Journal service
    # 412xx-413xx: Reserved for Report service
    # 414xx-415xx: Reserved for Stock service
    
    # Database/Repository errors (50YYZZ)
    DATABASE_ERROR = "500001"  # General database error
    CANNOT_CREATE = "500002"  # Cannot create
    CANNOT_UPDATE = "500003"  # Cannot update
    CANNOT_DELETE = "500004"  # Cannot delete
    DUPLICATE_KEY = "500005"  # Duplicate key
    UPDATE_NOT_WORK = "500006"  # Update operation failed
    REPLACE_NOT_WORK = "500007"  # Replace operation failed
    DELETE_CHILD_EXIST = "500008"  # Cannot delete because child elements exist
    
    # External service integration errors (60YYZZ)
    EXTERNAL_SERVICE_ERROR = "600001"  # External service error
    
    # System errors (90YYZZ)
    SYSTEM_ERROR = "900001"  # System error
    UNEXPECTED_ERROR = "900999"  # Unexpected error


class ErrorMessage:
    """
    Multilingual definition class for standardized error messages
    
    Provides error messages in multiple languages for each defined error code.
    Supports fallback mechanisms to ensure messages are always available.
    """
    
    # Default language
    DEFAULT_LANGUAGE = "ja"
    
    # Supported languages
    SUPPORTED_LANGUAGES = ["ja", "en"]
    
    # Language-specific error message map
    MESSAGES = {
        # Japanese error messages
        "ja": {
            # General errors
            ErrorCode.GENERAL_ERROR: "一般エラーが発生しました",
            ErrorCode.RESOURCE_NOT_FOUND: "対象データが見つかりませんでした",
            
            # Authentication/Authorization errors
            ErrorCode.AUTHENTICATION_ERROR: "認証に失敗しました",
            ErrorCode.AUTHORIZATION_ERROR: "権限がありません",
            
            # Input validation errors
            ErrorCode.VALIDATION_ERROR: "入力データが無効です",
            ErrorCode.REQUIRED_FIELD_MISSING: "必須フィールドがありません",
            ErrorCode.INVALID_FIELD_FORMAT: "フィールドの形式が正しくありません",
            ErrorCode.INVALID_OPERATION: "操作が無効です",
            
            # Database/Repository errors
            ErrorCode.DATABASE_ERROR: "データベースエラーが発生しました",
            ErrorCode.CANNOT_CREATE: "データを作成できませんでした",
            ErrorCode.CANNOT_UPDATE: "データを更新できませんでした",
            ErrorCode.CANNOT_DELETE: "データを削除できませんでした",
            ErrorCode.DUPLICATE_KEY: "キーが重複しています",
            ErrorCode.UPDATE_NOT_WORK: "更新が機能しませんでした",
            ErrorCode.REPLACE_NOT_WORK: "置換が機能しませんでした",
            ErrorCode.DELETE_CHILD_EXIST: "子要素が存在するため削除できません",
            
            # External service integration errors
            ErrorCode.EXTERNAL_SERVICE_ERROR: "外部サービスエラーが発生しました",
            
            # System errors
            ErrorCode.SYSTEM_ERROR: "システムエラーが発生しました",
            ErrorCode.UNEXPECTED_ERROR: "予期しないエラーが発生しました"
        },
        
        # English error messages
        "en": {
            # General errors
            ErrorCode.GENERAL_ERROR: "General error occurred",
            ErrorCode.RESOURCE_NOT_FOUND: "Resource not found",
            
            # Authentication/Authorization errors
            ErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
            ErrorCode.AUTHORIZATION_ERROR: "Permission denied",
            
            # Input validation errors
            ErrorCode.VALIDATION_ERROR: "Invalid input data",
            ErrorCode.REQUIRED_FIELD_MISSING: "Required field is missing",
            ErrorCode.INVALID_FIELD_FORMAT: "Invalid field format",
            ErrorCode.INVALID_OPERATION: "Invalid operation",
            
            # Database/Repository errors
            ErrorCode.DATABASE_ERROR: "Database error occurred",
            ErrorCode.CANNOT_CREATE: "Cannot create data",
            ErrorCode.CANNOT_UPDATE: "Cannot update data",
            ErrorCode.CANNOT_DELETE: "Cannot delete data",
            ErrorCode.DUPLICATE_KEY: "Duplicate key",
            ErrorCode.UPDATE_NOT_WORK: "Update operation failed",
            ErrorCode.REPLACE_NOT_WORK: "Replace operation failed",
            ErrorCode.DELETE_CHILD_EXIST: "Cannot delete because child elements exist",
            
            # External service integration errors
            ErrorCode.EXTERNAL_SERVICE_ERROR: "External service error occurred",
            
            # System errors
            ErrorCode.SYSTEM_ERROR: "System error occurred",
            ErrorCode.UNEXPECTED_ERROR: "Unexpected error occurred"
        }
    }
    
    # Default error messages
    DEFAULT_ERROR_MESSAGES = {
        "ja": "不明なエラーが発生しました",
        "en": "An unknown error occurred"
    }
    
    @classmethod
    def get_message(cls, error_code, default_message=None, lang=None):
        """
        Get the message corresponding to an error code
        
        Args:
            error_code: Error code
            default_message: Default message (used if no message corresponds to the code)
            lang: Language code ("ja" or "en", if None, default language is used)
            
        Returns:
            The corresponding error message
        """
        # Use default language if not specified
        if lang is None:
            lang = cls.DEFAULT_LANGUAGE
            
        # Use default language if unsupported language is specified
        if lang not in cls.SUPPORTED_LANGUAGES:
            lang = cls.DEFAULT_LANGUAGE
        
        # Get message for error code in specified language
        message = cls.MESSAGES.get(lang, {}).get(error_code)
        
        # If message not found
        if message is None:
            # Use specified default message if available
            if default_message:
                return default_message
            
            # Try default language
            if lang != cls.DEFAULT_LANGUAGE:
                message = cls.MESSAGES.get(cls.DEFAULT_LANGUAGE, {}).get(error_code)
            
            # If still not found, use language-appropriate default error message
            if message is None:
                return cls.DEFAULT_ERROR_MESSAGES.get(lang, cls.DEFAULT_ERROR_MESSAGES.get(cls.DEFAULT_LANGUAGE))
        
        return message