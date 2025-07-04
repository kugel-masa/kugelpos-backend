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
Web service endpoints configuration

This module defines URLs for the various microservices in the application,
facilitating service discovery and inter-service communication.
"""
from pydantic_settings import BaseSettings

class WebServiceSettings(BaseSettings):
    """
    Web service settings class
    
    Contains configuration for microservice URLs used for inter-service
    communication within the application.
    
    Attributes:
        BASE_URL_DAPR: URL for the Dapr sidecar (service discovery)
        BASE_URL_MASTER_DATA: URL for the Master Data microservice
        BASE_URL_TERMINAL: URL for the Terminal microservice
        BASE_URL_CART: URL for the Cart microservice
        BASE_URL_REPORT: URL for the Report microservice
        BASE_URL_JOURNAL: URL for the Journal microservice
        BASE_URL_STOCK: URL for the Stock microservice
    """
    BASE_URL_DAPR: str = "http://localhost:3500/v1.0"
    BASE_URL_MASTER_DATA: str = "http://localhost:8002/api/v1"
    BASE_URL_TERMINAL: str = "http://localhost:8001/api/v1"
    BASE_URL_CART: str = "http://localhost:8003/api/v1"
    BASE_URL_REPORT: str = "http://localhost:8004/api/v1"
    BASE_URL_JOURNAL: str = "http://localhost:8005/api/v1"
    BASE_URL_STOCK: str = "http://localhost:8006/api/v1"