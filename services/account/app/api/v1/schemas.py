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
from app.api.common.schemas import BaseUserAccount, BaseUserAccountInDB, BaseLoginResponse, BaseSample


class UserAccount(BaseUserAccount):
    """
    User account model for API requests.

    Extends the BaseUserAccount to maintain separation between API versions
    while inheriting all base functionality. This allows for version-specific
    extensions to the model if needed in the future.
    """

    pass


class UserAccountInDB(BaseUserAccountInDB):
    """
    User account model for database storage.

    Extends the BaseUserAccountInDB to maintain a clean separation between
    API versions while inheriting all the necessary database fields.
    This model represents the complete user account data as stored in MongoDB.
    """

    pass


class LoginResponse(BaseLoginResponse):
    """
    Response model for successful login attempts.

    Contains the JWT access token and token type, extending the base
    login response model. Used in the token endpoint response.
    """

    pass


class Sample(BaseSample):
    """
    Sample model for demonstration and testing.

    This class can be extended with additional fields specific to this
    API version if needed. Currently inherits all functionality from BaseSample.
    """

    pass
