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
Abstract repository pattern implementation for MongoDB

This module implements a generic repository pattern for MongoDB database access.
It provides a comprehensive set of CRUD operations and transaction management
for document models used throughout the application.
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClientSession
from pymongo.errors import DuplicateKeyError, OperationFailure
import asyncio
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import get_app_time
from kugel_common.exceptions import RepositoryException, CannotDeleteException, DuplicateKeyException
from kugel_common.schemas.pagination import PaginatedResult, Metadata

logger = getLogger(__name__)

Tdocument = TypeVar("Tdocument", bound=AbstractDocument)

class AbstractRepository(ABC, Generic[Tdocument]):
    """
    Generic abstract repository base class for MongoDB operations
    
    Provides a comprehensive set of asynchronous CRUD operations and transaction
    management for document models. This class is designed to be extended by
    concrete repository implementations for specific document types.
    
    Type Parameters:
        Tdocument: A type variable bound to AbstractDocument, representing
                  the specific document type this repository handles
    """

    def __init__(
        self,
        collection_name: str,
        document_class: Type[Tdocument],
        db: AsyncIOMotorDatabase,
    ):
        """
        Initialize a new repository instance
        
        Args:
            collection_name: Name of the MongoDB collection
            document_class: Class of the document model this repository handles
            db: MongoDB database connection instance
        """
        self.collection_name = collection_name
        self.dbcollection = None
        self.document_class = document_class
        self.db = db
        self.session: AsyncIOMotorClientSession = None

    async def initialize(self):
        """
        Initialize the database collection
        
        Connects to the specified collection in the database and prepares
        the repository for database operations.
        
        Raises:
            RepositoryException: If initialization fails
        """
        try:
            self.dbcollection = self.db.get_collection(self.collection_name)
        except Exception as e:
            message = f"initialize failed: collection_name->{self.collection_name}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def start_transaction(self) -> AsyncIOMotorClientSession:
        """
        Start a new database transaction
        
        Creates and returns a new transaction session that can be used
        for performing atomic operations across multiple documents.
        
        Returns:
            AsyncIOMotorClientSession: The newly created session object
            
        Raises:
            RepositoryException: If a transaction is already in progress
        """
        logger.debug(f"Starting transaction for collection: {self.collection_name}")
        if self.session is None:
            self.session = await self.db.client.start_session()
            self.session.start_transaction()
            return self.session
        else:
            raise RepositoryException(
                "Transaction already started", self.collection_name, logger
            )

    async def commit_transaction(self):
        """
        Commit the current transaction
        
        Finalizes all operations performed within the transaction and
        makes the changes permanent in the database.
        
        Raises:
            RepositoryException: If no transaction is in progress
        """
        logger.debug(f"Committing transaction for collection: {self.collection_name}")
        if self.session is not None:
            await self.session.commit_transaction()
            await self.session.end_session()
            self.session = None
        else:
            raise RepositoryException(
                "No transaction started", self.collection_name, logger
            )

    async def abort_transaction(self):
        """
        Abort the current transaction
        
        Cancels all operations performed within the transaction and
        rolls back any changes made.
        
        Raises:
            RepositoryException: If no transaction is in progress
        """
        logger.debug(f"Aborting transaction for collection: {self.collection_name}")
        if self.session is not None:
            await self.session.abort_transaction()
            await self.session.end_session()
            self.session = None
        else:
            raise RepositoryException(
                "No transaction started", self.collection_name, logger
            )

    def set_session(self, session: AsyncIOMotorClientSession):
        """
        Set an external transaction session for this repository
        
        Allows reusing an existing session across multiple repositories
        for coordinating transactions across collections.
        
        Args:
            session: The session object to use for database operations
        """
        logger.debug(f"Setting session for collection: {self.collection_name}")
        self.session = session

    async def create_async(self, document: Tdocument) -> bool:
        """
        Create a new document in the database
        
        Inserts a new document into the collection and sets its creation timestamp.
        
        Args:
            document: The document model instance to insert
            
        Returns:
            bool: True if document was successfully inserted, False otherwise
            
        Raises:
            DuplicateKeyException: If a document with the same key already exists
            RepositoryException: If any other database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            document.created_at = get_app_time()
            response = await self.dbcollection.insert_one(
                document.model_dump(), session=self.session
            )
            if response.inserted_id is None:
                return False
            return True
        except DuplicateKeyError as e:
            message = f"Duplicate key error: {e}, document: {document}"
            key = e.details.get("key", None)
            raise DuplicateKeyException(message, self.collection_name, key, logger) from e
        except Exception as e:
            message = f"Failed to save document to database: {document}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_all_async(self, max: int = 0) -> list[Tdocument]:
        """
        Retrieve all documents from the collection
        
        Fetches all documents in the collection, optionally limited to a maximum number.
        
        Args:
            max: Maximum number of documents to retrieve (0 for unlimited)
            
        Returns:
            list[Tdocument]: List of document model instances
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            if max == 0:
                result_set = await self.dbcollection.find({}).to_list(None)
            else:
                result_set = await self.dbcollection.find({}).limit(max).to_list(max)
            if result_set is None:
                logger.info(
                    f"No documents found in database for collection: {self.collection_name}"
                )
            return [self.__create_document(**result) for result in result_set]
        except Exception as e:
            message = f"Failed to get document from app.database"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_list_async(self, filter: dict, max: int = 0) -> list[Tdocument]:
        """
        Retrieve documents matching a filter from the collection
        
        Fetches documents that match the specified filter, optionally limited
        to a maximum number.
        
        Args:
            filter: Dictionary specifying the filter criteria
            max: Maximum number of documents to retrieve (0 for unlimited)
            
        Returns:
            list[Tdocument]: List of document model instances
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            if max == 0:
                result_set = await self.dbcollection.find(filter).to_list(None)
            else:
                result_set = (
                    await self.dbcollection.find(filter).limit(max).to_list(max)
                )
            if result_set is None:
                logger.info(
                    f"No documents found in database for filter: {filter} of collection: {self.collection_name}"
                )
            return [self.__create_document(**result) for result in result_set]
        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_list_async_with_sort_and_paging(
        self, filter: dict, limit: int = 0, page: int = 1, sort: list[tuple[str, int]] = None
    ) -> list[Tdocument]:
        """
        Retrieve documents with sorting and pagination
        
        Fetches documents that match the specified filter, sorted and paginated
        according to the provided parameters.
        
        Args:
            filter: Dictionary specifying the filter criteria
            limit: Maximum number of documents per page (0 for unlimited)
            page: Page number to retrieve (1-based index)
            sort: List of tuples specifying the sort order (field, direction)
            
        Returns:
            list[Tdocument]: List of document model instances
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            skip = (page - 1) * limit
            cursor = self.dbcollection.find(filter).skip(skip)
            if limit != 0:
                cursor = cursor.limit(limit)
            if sort is None:
                sort = [("created_at", -1)]
            cursor = cursor.sort(sort)
            result_set = await cursor.to_list(None if limit == 0 else limit)
            if result_set is None:
                logger.info(
                    f"No documents found in database for filter: {filter} of collection: {self.collection_name}"
                )
                result_set = []

            return [self.__create_document(**result) for result in result_set]
        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter} sort->{sort} page->{page} limit->{limit} e.message->{e}"
            raise RepositoryException(message, self.collection_name, logger, e) from e
    
    async def get_paginated_list_async(
        self, filter: dict, limit: int = 0, page: int = 1, sort: list[tuple[str, int]] = None
    ) -> PaginatedResult[Tdocument]:
        """
        Retrieve paginated documents with sorting
        
        Fetches documents that match the specified filter, sorted and paginated
        according to the provided parameters, and returns a paginated result.
        
        Args:
            filter: Dictionary specifying the filter criteria
            limit: Maximum number of documents per page (0 for unlimited)
            page: Page number to retrieve (1-based index)
            sort: List of tuples specifying the sort order (field, direction)
            
        Returns:
            PaginatedResult[Tdocument]: Paginated result containing metadata and data
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            total_count = await self.dbcollection.count_documents(filter)

            skip = (page - 1) * limit
            cursor = self.dbcollection.find(filter).skip(skip)

            if limit != 0:
                cursor = cursor.limit(limit)
            if sort is None:
                sort = [("created_at", -1)]
            cursor = cursor.sort(sort)
            result_set = await cursor.to_list(None if limit == 0 else limit)
            if result_set is None:
                logger.info(
                    f"No documents found in database for filter: {filter} of collection: {self.collection_name}"
                )
                result_set = []
            
            sort_str = ", ".join([f"{key}:{value}" for key, value in sort])
            return PaginatedResult(
                metadata=Metadata(
                    total=total_count,
                    page=page,
                    limit=limit,
                    sort=sort_str,
                    filter=filter
                ),
                data=[self.__create_document(**result) for result in result_set]
            )

        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter} sort->{sort} page->{page} limit->{limit} e.message->{e}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def get_one_async(self, filter: dict) -> Tdocument:
        """
        Retrieve a single document matching a filter
        
        Fetches a single document that matches the specified filter.
        
        Args:
            filter: Dictionary specifying the filter criteria
            
        Returns:
            Tdocument: The document model instance if found, None otherwise
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            result = await self.dbcollection.find_one(filter)
            if result is None:
                logger.debug(
                    f"Document not found in database for filter: {filter} of collection: {self.collection_name}"
                )
                return None
            return self.__create_document(**result)
        except Exception as e:
            message = f"Failed to get document from app.database: filter->{filter}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def replace_one_async(self, filter: dict, document: Tdocument) -> bool:
        """
        Replace a document in the database
        
        Replaces an existing document that matches the specified filter with
        the provided document model instance.
        
        Args:
            filter: Dictionary specifying the filter criteria
            document: The document model instance to replace with
            
        Returns:
            bool: True if document was successfully replaced, False otherwise
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            document.updated_at = get_app_time()
            response = await self.dbcollection.replace_one(
                filter, document.model_dump(), session=self.session
            )
            if response.modified_count != 1:
                logger.info(
                    f"Document not replaced in database for filter: {filter} of collection: {self.collection_name}"
                )
                return False
            return True
        except Exception as e:
            message = f"Failed to replace document in database: filter->{filter} document->{document}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def update_one_async(self, filter: dict, new_values: dict, max_retries: int = 3, retry_interval: float = 0.1) -> bool:
        """
        Update a document in the database
        
        Updates an existing document that matches the specified filter with
        the provided new values. Retries if WriteConflict (code 112) occurs.
        
        Args:
            filter: Dictionary specifying the filter criteria
            new_values: Dictionary of new values to update
            max_retries: Maximum number of retries for write conflict
            retry_interval: Wait time (seconds) between retries
        Returns:
            bool: True if document was successfully updated, False otherwise
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        attempt = 0
        while attempt < max_retries:
            try:
                new_values["updated_at"] = get_app_time()
                update_dict = {"$set": new_values}
                response = await self.dbcollection.update_one(
                    filter, update_dict, session=self.session
                )
                if response.modified_count != 1:
                    logger.info(
                        f"Document not updated in database for filter: {filter} of collection: {self.collection_name}"
                    )
                    return False
                return True
            except OperationFailure as e:
                if getattr(e, 'code', None) == 112:
                    attempt += 1
                    logger.warning(f"WriteConflict (code 112) on update_one_async (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(retry_interval * attempt)
                        continue
                    else:
                        message = f"WriteConflict (code 112) after {max_retries} retries: filter->{filter} new_values->{new_values}"
                        raise RepositoryException(message, self.collection_name, logger, e) from e
                else:
                    message = f"OperationFailure (code {getattr(e, 'code', None)}) on update_one_async: filter->{filter} new_values->{new_values}"
                    raise RepositoryException(message, self.collection_name, logger, e) from e
            except Exception as e:
                message = f"Failed to update document in database: filter->{filter} new_values->{new_values}"
                raise RepositoryException(message, self.collection_name, logger, e) from e

    async def delete_async(self, search_dict: dict) -> bool:
        """
        Delete a document from the database
        
        Deletes an existing document that matches the specified search criteria.
        
        Args:
            search_dict: Dictionary specifying the search criteria
            
        Returns:
            bool: True if document was successfully deleted, False otherwise
            
        Raises:
            CannotDeleteException: If the document could not be deleted
            RepositoryException: If any other database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            response = await self.dbcollection.find_one(search_dict)
            if response is None:
                logger.info(
                    f"Document not found in database for filter: {search_dict} of collection: {self.collection_name}"
                )
                return False
            response = await self.dbcollection.delete_one(
                search_dict, session=self.session
            )
            if response.deleted_count != 1:
                logger.info(
                    f"Document not deleted in database for filter: {search_dict} of collection: {self.collection_name}"
                )
                raise CannotDeleteException(
                    "Document not deleted", self.collection_name, search_dict, logger
                )
            return True
        except Exception as e:
            message = f"Failed to delete document from app.database: search_dict->{search_dict} e.message->{e}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def execute_pipeline(self, pipeline: list[dict]) -> list[dict]:
        """
        Execute an aggregation pipeline
        
        Runs the specified aggregation pipeline on the collection and returns
        the resulting documents.
        
        Args:
            pipeline: List of aggregation stages to execute
            
        Returns:
            list[dict]: List of resulting documents
            
        Raises:
            RepositoryException: If any database error occurs
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            result_set = await self.dbcollection.aggregate(pipeline).to_list(None)
            if result_set is None:
                logger.info(
                    f"No documents found in database for pipeline: {pipeline} of collection: {self.collection_name}"
                )
            return result_set
        except Exception as e:
            message = f"Failed to execute pipeline in app.database: pipeline->{pipeline}"
            raise RepositoryException(message, self.collection_name, logger, e) from e
    
    def make_shard_key(self, keys: list[str]) -> str:
        """
        Create a shard key from a list of keys
        
        Combines the specified keys into a single shard key string.
        
        Args:
            keys: List of key strings to combine
            
        Returns:
            str: The resulting shard key
        """
        return "_".join(keys)

    def __create_document(self, **kwargs) -> Tdocument:
        """
        Create a document model instance
        
        Instantiates a new document model using the provided keyword arguments.
        
        Args:
            kwargs: Dictionary of document field values
            
        Returns:
            Tdocument: The newly created document model instance
        """
        return self.document_class(**kwargs)
