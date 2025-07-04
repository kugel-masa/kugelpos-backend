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
Slack notification utility module

Provides functionality to send notifications to Slack channels,
especially in case of errors or critical situations.
"""

import aiohttp
import json
import logging
import platform
from typing import Optional, Dict, Any, Union
from datetime import datetime

from kugel_common.config.settings import settings

logger = logging.getLogger(__name__)

# Get Slack webhook URL from settings
# Skip notification if SLACK_WEBHOOK_URL is not set in environment
SLACK_WEBHOOK_URL = getattr(settings, "SLACK_WEBHOOK_URL", None)

async def send_slack_notification(
    message: str, 
    title: str = "Error Notification", 
    level: str = "error",
    error_details: Optional[Union[str, Exception]] = None,
    additional_fields: Optional[Dict[str, Any]] = None,
    service: str = None,
    footer: str = None
) -> bool:
    """
    Send an asynchronous notification to Slack
    
    Args:
        message: Notification message body
        title: Title of the notification
        level: Notification level (error, warning, info, etc.)
        error_details: Error details (exception object or detailed message)
        additional_fields: Additional field information
        service: Service name (auto-detected if None)
        footer: Custom footer for the notification (uses service name if None)
    
    Returns:
        bool: Whether the notification was successfully sent
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL is not configured. Slack notification skipped.")
        return False
    
    # Auto-detect service name if not provided
    if not service:
        service = platform.node()
    
    # Set footer based on service name if not explicitly provided
    if not footer:
        footer = f"Kugelpos {service.capitalize()} Service"
        
    # Set color based on error level
    colors = {
        "error": "#ff0000",      # Red
        "fatal": "#9b0000",      # Dark red
        "warning": "#ffcc00",    # Yellow
        "info": "#0099ff"        # Blue
    }
    
    color = colors.get(level.lower(), "#717171")  # Default is gray
    
    # Get current time
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create notification body
    fields = [
        {
            "title": "Time",
            "value": now,
            "short": True
        },
        {
            "title": "Level",
            "value": level.upper(),
            "short": True
        }
    ]

    # Add service info if available and not already in additional fields
    if service and not (additional_fields and "Service" in additional_fields):
        fields.append({
            "title": "Service",
            "value": service,
            "short": True
        })
    
    # Add error details if available
    if error_details:
        error_text = str(error_details)
        fields.append({
            "title": "Details",
            "value": error_text[:1000] + ("..." if len(error_text) > 1000 else ""),
            "short": False
        })
    
    # Add additional fields if available
    if additional_fields:
        for k, v in additional_fields.items():
            fields.append({
                "title": k,
                "value": str(v),
                "short": len(str(v)) < 50  # Display inline if value is short
            })
    
    # Create payload
    payload = {
        "attachments": [
            {
                "fallback": f"{title}: {message}",
                "color": color,
                "title": title,
                "text": message,
                "fields": fields,
                "footer": footer,
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SLACK_WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.debug(f"Slack notification sent successfully: {title}")
                    return True
                else:
                    response_text = await response.text()
                    logger.error(f"Failed to send Slack notification (status={response.status}): {response_text}")
                    return False
    except Exception as e:
        logger.error(f"Error occurred while sending Slack notification: {str(e)}")
        return False


async def send_fatal_error_notification(
    message: str, 
    error: Optional[Exception] = None,
    service: str = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send notification to Slack when a fatal error occurs
    
    Args:
        message: Error message
        error: Exception object
        service: Service name where the error occurred (auto-detected if None)
        context: Error context (related information)
    
    Returns:
        bool: Whether the notification was successfully sent
    """
    additional_fields = {}
    
    # Add context information if available
    if context:
        for k, v in context.items():
            additional_fields[k] = v
    
    return await send_slack_notification(
        message=message,
        title="❌ Fatal Error",
        level="fatal",
        error_details=error,
        additional_fields=additional_fields,
        service=service
    )


async def send_error_notification(
    message: str, 
    error: Optional[Exception] = None,
    service: str = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send notification to Slack when an error occurs
    
    Args:
        message: Error message
        error: Exception object
        service: Service name where the error occurred (auto-detected if None)
        context: Error context (related information)
    
    Returns:
        bool: Whether the notification was successfully sent
    """
    additional_fields = {}
    
    # Add context information if available
    if context:
        for k, v in context.items():
            additional_fields[k] = v
    
    return await send_slack_notification(
        message=message,
        title="🔴 Error",
        level="error",
        error_details=error,
        additional_fields=additional_fields,
        service=service
    )


async def send_warning_notification(
    message: str,
    service: str = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send a warning notification to Slack
    
    Args:
        message: Warning message
        service: Service name where the warning occurred (auto-detected if None)
        context: Additional context information
        
    Returns:
        bool: Whether the notification was successfully sent
    """
    additional_fields = {}
    
    # Add context information if available
    if context:
        for k, v in context.items():
            additional_fields[k] = v
            
    return await send_slack_notification(
        message=message,
        title="⚠️ Warning",
        level="warning",
        additional_fields=additional_fields,
        service=service
    )


async def send_info_notification(
    message: str,
    service: str = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send an informational notification to Slack
    
    Args:
        message: Informational message
        service: Service name (auto-detected if None)
        context: Additional context information
        
    Returns:
        bool: Whether the notification was successfully sent
    """
    additional_fields = {}
    
    # Add context information if available
    if context:
        for k, v in context.items():
            additional_fields[k] = v
            
    return await send_slack_notification(
        message=message,
        title="ℹ️ Information",
        level="info",
        additional_fields=additional_fields,
        service=service
    )