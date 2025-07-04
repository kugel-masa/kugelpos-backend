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
from pydantic import BaseModel
from typing import Optional, Any, Union
from kugel_common.models.documents.abstract_document import AbstractDocument

class RequestLog(AbstractDocument):
    """
    API Request Log Document Model
    
    This class extends AbstractDocument to provide a comprehensive data structure
    for recording details of API requests and responses. It stores information 
    about the request source, content, response, and processing time, used for
    auditing and debugging purposes.
    """
    class ClientInfo(BaseModel):
        """
        Client Information Model
        
        Stores information about the client that sent the API request.
        """
        ip_address: str

    class RequestInfo(BaseModel):
        """
        Request Information Model
        
        Stores details about the received API request, including method,
        URL, body content, and acceptance time.
        """
        method: str
        url: str
        body: Optional[Union[list[Any], dict[str, Any]]] = None
        accept_time: str

    class ResponseInfo(BaseModel):
        """
        Response Information Model
        
        Stores details about the API response, including status code,
        processing time, and response body.
        """
        status_code: int
        process_time_ms: int
        body: Optional[Union[list[Any], dict[str, Any]]] = None

    class StaffInfo(BaseModel):
        """
        Staff Information Model
        
        Stores identification information of the staff member who processed the request.
        """
        id: str
        name: str

    class UserInfo(BaseModel):
        """
        User Information Model
        
        Stores identification and permission information of the user who sent the request.
        """
        tenant_id: str
        username: str
        is_superuser: bool

    class TerminalInfo(BaseModel):
        """
        Terminal Information Model
        
        Stores identification and status information of the terminal from which 
        the request was sent.
        """
        tenant_id: str
        store_code: str
        terminal_no: int
        business_date: str
        open_counter: int
    
    tenant_id: Optional[str] = None
    client_info: ClientInfo
    request_info: RequestInfo
    response_info: ResponseInfo
    staff_info: Optional[StaffInfo] = None
    user_info: Optional[UserInfo] = None
    terminal_info: Optional[TerminalInfo] = None