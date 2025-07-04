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
Base document model definition module

This module provides the foundation for all document models used throughout the application,
establishing consistent patterns for database interaction and serialization.
"""
from pydantic import BaseModel
from datetime import datetime

class BaseDocumentModel(BaseModel):
    """
    Base class for all document models in the application
    
    This class extends Pydantic's BaseModel to provide a common foundation
    for all database document models. It specifically avoids using field aliases
    since these models are intended for direct database interaction rather than
    external API representation.
    """
    # model_config = ConfigDict(populate_by_name=True) 
    # -> do not use alias for the document model
    #    because the document model is used for the database

    pass
