# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime, timedelta
from typing import Optional

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.utils.misc import get_app_time


class AbstractDocument(BaseDocumentModel):
    """
    Abstract base document class that serves as the foundation for all document models in the system.

    This class extends the BaseDocumentModel from kugel_common and adds common metadata fields
    and functionality that are needed across all document types, such as creation/update timestamps,
    caching information, and document versioning support via etag.
    """

    shard_key: Optional[str] = None  # Database sharding key for horizontal partitioning
    created_at: Optional[datetime] = None  # Timestamp when the document was first created
    updated_at: Optional[datetime] = None  # Timestamp when the document was last updated
    cached_on: Optional[datetime] = None  # Timestamp when the document was last cached
    etag: Optional[str] = None  # Entity tag for optimistic concurrency control

    def is_expired(self, minutes: int) -> bool:
        """
        Check if the cached version of this document has expired based on a time threshold.

        Args:
            minutes: The number of minutes after which a cached document is considered expired

        Returns:
            True if the document's cache is older than the specified minutes, False otherwise
        """
        return get_app_time() - self.cached_on > timedelta(minutes=minutes)
