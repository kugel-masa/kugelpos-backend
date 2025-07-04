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
from fastapi import status
from kugel_common.schemas.api_response import ApiResponse

"""
Standard HTTP status code response definitions for use across all microservices.

This module provides consistent API response formats for various HTTP status codes,
ensuring uniform error handling and response structure throughout the application.
Each status code includes a description, response model, and example content.
"""

StatusCodes = {
    status.HTTP_400_BAD_REQUEST: {
        "description": "Bad request", 
        "model": ApiResponse, 
        "content": {
            "application/json": {
                "example": {"success": False, "code": 400, "message": "Bad request", "data": "400:Bad request"}
            }
        }
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Unauthorized", 
        "model": ApiResponse,
        "content": {
            "application/json": {
                "example": {"success": False, "code": 401, "message": "Unauthorized", "data": "401:Unauthorized"}
            }
        }
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Forbidden", 
        "model": ApiResponse,
        "content": {
            "application/json": {
                "example": {"success": False, "code": 403, "message": "Forbidden", "data": "403:Forbidden"}
            }
        }
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "Sample not found", 
        "model": ApiResponse,
        "content": {
            "application/json": {
                "example": {"success": False, "code": 404, "message": "Sample not found", "data": "404:Sample not found"}
            }
        }
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "description": "Unprocessable entity", 
        "model": ApiResponse,
        "content": {
            "application/json": {
                "example": {"success": False, "code": 422, "message": "Unprocessable entity", "data": "[{'type': 'missing', 'loc': ('body', 'pin'), 'msg': 'Field required', 'input': {'id': '1234', 'name': 'someone'}}]"}
            }
        },
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal server error", 
        "model": ApiResponse,
        "content": {
            "application/json": {
                "example": {"success": False, "code": 500, "message": "Internal server error", "data": "500:Internal server error"}
            }
        }
    }
}