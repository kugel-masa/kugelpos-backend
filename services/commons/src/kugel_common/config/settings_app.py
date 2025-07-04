"""
Application general settings configuration

This module defines general application-wide settings that affect core business logic
behavior, such as rounding methods and numbering sequences.
"""
from pydantic_settings import BaseSettings
from kugel_common.enums import RoundMethod

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
    """
    ROUND_METHOD_FOR_DISCOUNT: str = RoundMethod.Round.value
    RECEIPT_NO_START_VALUE: int = 111111
    RECEIPT_NO_END_VALUE: int = 999999
    SLACK_WEBHOOK_URL: str = ""