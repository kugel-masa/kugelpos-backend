# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type
from logging import getLogger

from kugel_common.utils.misc import get_app_time
from kugel_common.exceptions import (
    RepositoryException,
    CannotCreateException,
    ReplaceNotWorkException,
    UpdateNotWorkException,
    CannotDeleteException,
)

from app.models.documents.abstract_document import AbstractDocument
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

logger = getLogger(__name__)

Tdocument = TypeVar("Tdocument", bound=AbstractDocument)


class AbstractRepository(ABC, Generic[Tdocument]):
    """
    Abstract base repository class providing standard database operations.

    This class implements the repository pattern and serves as a base for all repositories
    in the application. It provides generic CRUD operations for document classes that
    extend AbstractDocument, along with search capabilities including filtering, sorting,
    and pagination.

    The repository uses MongoDB via Motor for asynchronous operations, and includes
    error handling, logging, and timestamp management.

    Type Parameters:
        Tdocument: A type variable bound to AbstractDocument, representing the document
                   model that a specific repository implementation will handle.
    """

    def __init__(self, collection_name: str, document_class: Type[Tdocument], db: AsyncIOMotorDatabase):
        """
        Initialize a new repository instance.

        Args:
            collection_name: Name of the MongoDB collection this repository will operate on
            document_class: Class of document model this repository will handle
            db: MongoDB database instance
        """
        self.collection_name = collection_name
        self.document_class = document_class
        self.db: AsyncIOMotorDatabase = db
        self.dbcollection: AsyncIOMotorCollection = None

    async def initialize(self):
        """
        Initialize the database collection connection.

        This method retrieves the MongoDB collection reference and should be called
        before any database operations are performed.

        Returns:
            None

        Raises:
            RepositoryException: If the collection cannot be initialized
        """
        try:
            self.dbcollection = self.db.get_collection(self.collection_name)
        except Exception as e:
            message = f"initialize failed: collection_name->{self.collection_name}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def create_async(self, document: Tdocument) -> Tdocument:
        """
        Create a new document in the database.

        This method inserts a new document into the collection and sets its creation
        timestamp automatically.

        Args:
            document: Document instance to be saved to the database

        Returns:
            The created document instance with any updates from the database

        Raises:
            CannotCreateException: If the document creation fails
            RepositoryException: For any other database operation errors
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            document.created_at = get_app_time()
            response = await self.dbcollection.insert_one(document.model_dump())
            if response.inserted_id is None:
                message = "inserted_id is None"
                raise CannotCreateException(message, self.collection_name, document, logger)
            logger.info(f"Document created in database: {document}")
            return document
        except CannotCreateException as e:
            raise e
        except Exception as e:
            message = f"Failed to save document to database: {document}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_list_async(self, filter: dict, max: int = 0) -> list[Tdocument]:
        """
        Retrieve a list of documents matching the specified filter.

        Args:
            filter: MongoDB query filter to select documents
            max: Maximum number of documents to return (0 for unlimited)

        Returns:
            List of document instances matching the filter

        Raises:
            RepositoryException: If the retrieval operation fails
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            if max == 0:
                result_set = await self.dbcollection.find(filter).to_list(None)
            else:
                result_set = await self.dbcollection.find(filter).limit(max).to_list(max)
            if result_set is None:
                logger.info(
                    f"No documents found in database for filter: {filter} of collection: {self.collection_name}"
                )
            return [self.__create_document(**result) for result in result_set]
        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_list_async_with_sort_and_paging(
        self, filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[Tdocument]:
        """
        Retrieve a paginated and sorted list of documents matching the specified filter.

        This method supports advanced querying with pagination and sorting capabilities.

        Args:
            filter: MongoDB query filter to select documents
            limit: Maximum number of documents to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of document instances matching the query parameters

        Raises:
            RepositoryException: If the retrieval operation fails
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            skip = (page - 1) * limit
            cursor = self.dbcollection.find(filter).skip(skip).limit(limit)
            if sort is not None:
                cursor = cursor.sort(sort)
            result_set = await cursor.to_list(limit)
            if result_set is None:
                logger.info(
                    f"No documents found in database for filter: {filter} of collection: {self.collection_name}"
                )

            return [self.__create_document(**result) for result in result_set]
        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter} sort->{sort} page->{page} limit->{limit} e.message->{e}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_one_async(self, filter: dict) -> Tdocument:
        """
        Retrieve a single document matching the specified filter.

        Args:
            filter: MongoDB query filter to select the document

        Returns:
            Document instance matching the filter, or None if not found

        Raises:
            RepositoryException: If the retrieval operation fails
        """
        logger.debug(f"get_one_async: filter->{filter}")
        if self.dbcollection is None:
            await self.initialize()
        try:
            result = await self.dbcollection.find_one(filter)
            if result is None:
                logger.info(f"No document found in database for filter: {filter} of collection: {self.collection_name}")
                return None
            return self.__create_document(**result)
        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def replace_one_async(self, filter: dict, document: Tdocument) -> Tdocument:
        """
        Replace an existing document in the database.

        This method completely replaces a document matching the filter with the new document,
        and updates the document's 'updated_at' timestamp.

        Args:
            filter: MongoDB query filter to select the document to replace
            document: New document instance to replace the existing document

        Returns:
            The updated document instance

        Raises:
            ReplaceNotWorkException: If the document replacement fails
            RepositoryException: For any other database operation errors
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            document.updated_at = get_app_time()
            response = await self.dbcollection.replace_one(filter, document.model_dump())
            if response.modified_count != 1:
                message = (
                    f"Document not replaced in database for filter: {filter} of collection: {self.collection_name}"
                )
                raise ReplaceNotWorkException(message, self.collection_name, filter, logger)
            return document
        except ReplaceNotWorkException as e:
            raise e
        except Exception as e:
            message = f"Failed to replace document in database: filter->{filter} document->{document}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def update_one_async(self, filter: dict, new_values: dict) -> Tdocument:
        """
        Update specific fields of a document in the database.

        This method modifies only the specified fields of a document matching the filter,
        and updates the document's 'updated_on' timestamp.

        Args:
            filter: MongoDB query filter to select the document to update
            new_values: Dictionary containing the fields to update and their new values

        Returns:
            The updated document instance

        Raises:
            UpdateNotWorkException: If the document update fails
            RepositoryException: For any other database operation errors
        """
        if self.dbcollection is None:
            await self.initilalize()
        try:
            new_values["updated_on"] = get_app_time()
            update_dict = {"$set": new_values}
            response = await self.dbcollection.update_one(filter, update_dict)
            if response.modified_count != 1:
                message = f"Document not updated in database for filter: {filter} of collection: {self.collection_name}"
                raise UpdateNotWorkException(message, self.collection_name, filter, logger)
            filter = self.__arrange_filter(filter, new_values)
            return await self.get_one_async(filter)
        except UpdateNotWorkException as e:
            raise e
        except Exception as e:
            message = f"Failed to update document in database: filter->{filter} new_values->{new_values}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def delete_async(self, search_dict: dict):
        """
        Delete a document from the database.

        Args:
            search_dict: MongoDB query filter to select the document to delete

        Returns:
            None

        Raises:
            CannotDeleteException: If the document deletion fails
            RepositoryException: For any other database operation errors
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            response = await self.dbcollection.delete_one(search_dict)
            if response.deleted_count != 1:
                message = f"Document not deleted in database for search_dict: {search_dict} of collection: {self.collection_name}"
                raise CannotDeleteException(message, self.collection_name, search_dict, logger)
            return
        except CannotDeleteException as e:
            raise e
        except Exception as e:
            message = f"Failed to delete document from app.database: search_dict->{search_dict}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def count_async(self, filter: dict) -> int:
        """
        Count documents matching the specified filter.

        Args:
            filter: MongoDB query filter to select documents to count

        Returns:
            Number of documents matching the filter

        Raises:
            RepositoryException: If the count operation fails
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            count = await self.dbcollection.count_documents(filter)
            return count
        except Exception as e:
            message = f"Failed to count documents in database: filter->{filter}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    def make_shard_key(self, keys: list[str]) -> str:
        """
        Create a composite shard key from multiple key values.

        This utility method creates a string representation of a shard key
        by joining multiple values with underscores.

        Args:
            keys: List of strings to combine into a shard key

        Returns:
            String representation of the composite shard key
        """
        return "_".join(keys)

    def __create_document(self, **kwargs) -> Tdocument:
        """
        Create a document instance from database fields.

        This private method instantiates a document of the repository's document class
        from the key-value pairs retrieved from the database.

        Args:
            **kwargs: Key-value pairs representing document fields

        Returns:
            An instance of the repository's document class
        """
        return self.document_class(**kwargs)

    def __arrange_filter(self, filter: dict, new_values: dict) -> dict:
        """
        Update filter dictionary with new values for accurate document retrieval after update.

        This private method ensures that after an update operation, the filter used to
        retrieve the updated document reflects the changes made.

        Args:
            filter: Original filter dictionary used for the update
            new_values: Dictionary of field updates applied to the document

        Returns:
            Updated filter dictionary
        """
        keys = list(filter.keys())
        # check if keys are in new_values
        for key in keys:
            if key in new_values:
                filter.update({key: new_values[key]})
        return filter
