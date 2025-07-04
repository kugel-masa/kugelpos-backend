# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from app.services.alert_service import AlertService

# Global alert service instance
_alert_service: Optional[AlertService] = None


def set_alert_service(alert_service: Optional[AlertService]) -> None:
    """Set the global alert service instance"""
    global _alert_service
    _alert_service = alert_service


def get_alert_service() -> Optional[AlertService]:
    """Get the global alert service instance"""
    return _alert_service
