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
from typing import Optional
from pydantic import BaseModel, ConfigDict
from kugel_common.utils.misc import to_lower_camel

# Base Schema Model
class BaseSchemmaModel(BaseModel):
    """
    Base Schema Model
    
    The fundamental class for all API schema models. Provides configuration
    for JSON serialization in camelCase format, ensuring consistent API response
    and request formatting.
    """
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

# Metadata
class Metadata(BaseSchemmaModel):
    """
    Metadata Model
    
    Represents metadata for paginated API responses.
    Includes total count, current page, items per page, sort criteria,
    and filter conditions.
    """
    total: int
    page: int
    limit: int
    sort: Optional[str]
    filter: Optional[dict]
