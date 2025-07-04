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
from pydantic import ConfigDict

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel

class StoreInfoDocument(AbstractDocument):
    """
    Document model representing store information.
    
    This class extends AbstractDocument to store and manage information about a retail store,
    including its code, name, operational status, and current business date.
    """
    store_code: Optional[str] = None
    store_name: Optional[str] = None
    status: Optional[str] = None
    business_date: Optional[str] = None
    tags: Optional[list[str]] = None

    # camel case
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)