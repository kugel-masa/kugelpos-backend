"""
Application general settings configuration

This module defines general application-wide settings that affect core business logic
behavior, such as rounding methods and numbering sequences.
"""
from pydantic_settings import BaseSettings
from kugel_common.enums import RoundMethod
from kugel_common.utils.log_utils import DEFAULT_LOG_STRIP_FIELDS

class AppSettings(BaseSettings):
    """
    General application settings class
    
    Contains configuration for basic application behaviors that are common
    across all services in the application.
    
    Attributes:
        ROUND_METHOD_FOR_DISCOUNT: Rounding method used for discount calculations
        RECEIPT_NO_START_VALUE: Starting value for receipt number sequences
        RECEIPT_NO_END_VALUE: Ending value for receipt number sequences (cycles back to start)
        SLACK_WEBHOOK_URL: URL for Slack webhook notifications
        REQUEST_LOG_STRIP_FIELDS: Comma-separated body fields the request-log
            middleware replaces with a metadata marker. Set it to a single
            space to turn stripping off: an empty value is dropped by
            env_ignore_empty and leaves the default in place
        REQUEST_LOG_MAX_BODY_BYTES: Size ceiling for a logged request/response
            body; larger bodies are stored as a truncation marker (0 disables)
    """
    ROUND_METHOD_FOR_DISCOUNT: str = RoundMethod.Round.value
    RECEIPT_NO_START_VALUE: int = 111111
    RECEIPT_NO_END_VALUE: int = 999999
    SLACK_WEBHOOK_URL: str = ""

    # Request-log body budget (issue #155). The signed cart snapshot is the
    # field that motivated this: it carries the whole cart document on every
    # mutating call, into both the log file and the `request_log` collection.
    # The ceiling is a backstop for everything else that grows.
    REQUEST_LOG_STRIP_FIELDS: str = ",".join(DEFAULT_LOG_STRIP_FIELDS)
    REQUEST_LOG_MAX_BODY_BYTES: int = 32768