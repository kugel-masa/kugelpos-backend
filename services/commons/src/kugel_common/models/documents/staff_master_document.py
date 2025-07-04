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
from kugel_common.utils.misc import to_lower_camel  
from kugel_common.models.documents.abstract_document import AbstractDocument

class StaffMasterDocument(AbstractDocument):
    """
    Document model representing store staff information.
    
    This class extends AbstractDocument to store and manage information about retail staff members,
    including their ID, name, PIN for authentication, and deletion status. Used for staff 
    authentication and identification throughout the POS system.
    """
    tenant_id: Optional[str] = None
    store_code: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    pin: Optional[str] = None
    is_deleted: Optional[bool] = False

    # camel case
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)