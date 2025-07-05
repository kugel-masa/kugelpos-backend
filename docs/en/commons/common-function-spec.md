# Kugel Commons Common Function Specification

## Overview

Kugel Commons (`kugel_common`) is a library that provides common functionality used across microservices in the Kugelpos POS system. It provides unified handling of cross-cutting concerns such as database abstraction, authentication, exception handling, HTTP communication, and configuration management.

**Version**: 0.1.9  
**Architecture**: Microservices foundation  
**Language Support**: Japanese and English support (Japanese as default)

## Module Structure

### Main Modules

```
kugel_common/
├── config/          # Configuration management
├── database/        # MongoDB abstraction
├── models/          # Data models and repository pattern
├── schemas/         # API schemas
├── exceptions/      # Exception handling
├── utils/           # Utilities
├── middleware/      # Middleware
├── security.py      # Authentication and authorization
├── enums.py         # Enumeration definitions
└── status_codes.py  # HTTP status codes
```

## 1. Configuration Management (config/)

### Unified Configuration Architecture

`settings.py` provides unified management of the following configuration classes:

#### AppSettings
- **Common Application Settings**
  - Rounding methods (for tax calculations)
  - Receipt number generation method
  - Slack integration settings

#### DatetimeSettings
- **Date and Time Settings**
  - Timezone management
  - Date/time format standardization

#### TaxSettings
- **Tax Calculation Settings**
  - Tax rate settings
  - Tax calculation rules
  - Rounding methods

#### AuthSettings
- **Authentication Settings**
  - JWT settings (secret key, algorithm, expiration)
  - Authentication server settings

#### StampDutySettings
- **Stamp Duty Settings**
  - Stamp duty master data (based on Japanese tax law)
  - Correspondence table of amount thresholds and stamp duty amounts
  - 14 tiers of stamp duty classifications (from 50,000 yen to over 1 billion yen)

#### WebServiceSettings
- **Inter-Service Communication Settings**
  - Base URLs for each service
  - Service discovery settings

#### DBSettings
- **MongoDB Connection Settings**
  - Connection string
  - Connection pool settings (max 100, min 10 connections)
  - Timeout settings

#### DBCollectionCommonSettings
- **Standard Collection Names**
  - Unified common collection names

### Configuration Features

- **Environment Variable Support**: Integration with `.env` files
- **Connection Pooling**: Efficient database connection management
- **Timeout Settings**: Response time control for database operations
- **Service Discovery**: Automatic URL resolution using BASE_URL patterns

## 2. Database Abstraction (database/)

### MongoDB Asynchronous Operations (`database.py`)

```python
# Main features
- Singleton client management
- Automatic retry with exponential backoff
- Connection pool management
- Database and collection operations
- Automatic index creation
```

#### Implementation Features

- **Connection Management**: Unified connection management using singleton pattern
- **Error Handling**: Automatic retry with exponential backoff
- **Connection Pool**: Configurable pool size and idle timeout
- **Transactions**: Full MongoDB transaction support

### Repository Pattern (`abstract_repository.py`)

```python
class AbstractRepository(Generic[T]):
    """Generic repository providing type-safe CRUD operations"""
    
    async def find_by_id_async(self, id: str) -> Optional[T]
    async def find_by_filter_async(self, filter_dict: dict) -> List[T]
    async def create_async(self, entity: T) -> T
    async def update_async(self, entity: T) -> T
    async def delete_async(self, id: str) -> bool
    async def paginate_async(self, page: int, limit: int, **kwargs) -> PaginatedResult[T]
```

#### Main Features

- **Type Safety**: Type-safe CRUD operations using Python Generics
- **Transactions**: Multi-document transaction support
- **Pagination**: Built-in pagination functionality
- **Retry Mechanism**: Automatic retry for WriteConflict (MongoDB code 112)
- **Bulk Operations**: Aggregation pipeline support

### Document Models

#### BaseDocumentModel
```python
class BaseDocumentModel(BaseModel):
    """Base class for all documents (Pydantic)"""
    
    class Config:
        extra = "forbid"
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }
```

#### AbstractDocument
```python
class AbstractDocument(BaseDocumentModel):
    """Base document class with common fields"""
    
    shard_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    etag: Optional[str] = None
```

#### Specialized Documents
- **TerminalInfoDocument**: Terminal information
- **StaffMasterDocument**: Staff master
- **StoreInfoDocument**: Store information
- **UserInfoDocument**: User information

## 3. Exception Handling (exceptions/)

### Hierarchical Exception Structure

```
AppException (Base exception)
├── DatabaseException (Database layer)
├── RepositoryException (Data access layer)
└── ServiceException (Business logic layer)
```

### Error Code System (XXYYZZ format)

- **XX**: Error category
  - 10: General errors
  - 20: Authentication errors
  - 30: Validation errors
  - 40: Business logic errors
  - 50: Database errors
  - 60: External service errors
  - 90: System errors

- **YY**: Subcategory (service-specific range allocation)
- **ZZ**: Specific error code

### Implementation Example

```python
class ValidationException(AppException):
    """Validation error"""
    error_code = 30001
    
    def __init__(self, message: str, user_message: str = None, details: dict = None):
        super().__init__(message, user_message, details)
        self.status_code = 400
```

### Feature Highlights

- **Multi-language Support**: Japanese and English error messages
- **Structured Logging**: Consistent error logging
- **User-Friendly**: Separation of system errors and user errors
- **HTTP Integration**: Automatic HTTP status code mapping

## 4. API and Schema Management (schemas/)

### Standardized API Response (`api_response.py`)

```python
class ApiResponse(BaseModel, Generic[T]):
    """Unified API response format"""
    
    success: bool
    code: int                    # HTTP status code
    message: str                 # System message
    user_error: Optional[UserError] = None  # User-facing error
    data: Optional[T] = None     # Generic payload
    metadata: Optional[Metadata] = None     # Pagination information
    operation: Optional[str] = None         # Operation tracking
```

### Pagination Support

```python
class PaginatedResult(BaseModel, Generic[T]):
    """Generic pagination response"""
    
    data: List[T]      # Using 'data' instead of 'items'
    page: int
    limit: int
    total_pages: int   # Using 'total_pages' instead of 'has_next/has_prev'
    total_items: int   # Total item count
```

### Field Naming Conventions

- **Database**: snake_case (direct MongoDB operations)
- **API**: camelCase (using `to_lower_camel()` utility)

## 5. Security Features (security.py)

### Dual Authentication System

#### 1. OAuth2/JWT Authentication
```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """User authentication via JWT token"""
    
    # JWT verification (using jose library)
    # Tenant isolation
    # Service account support
    # Superuser permission check
    # Returns dictionary format (containing user_id, username, tenant_id, etc.)
```

#### 2. API Key Authentication
```python
async def get_current_terminal_from_api_key(
    api_key: str = Header(..., alias="X-API-KEY"),
    terminal_id: str = Query(...)
) -> TerminalInfoDocument:
    """Terminal authentication via API key"""
    
    # Terminal ID format: {tenant_id}-{store_code}-{terminal_no}
    # API key verification
    # Inter-service terminal information retrieval
    # Returns TerminalInfoDocument type
```

### Multi-Tenant Security

- **Tenant Isolation**: Database-level separation by tenant_id
- **Terminal ID Format**: Unified format `{tenant_id}-{store_code}-{terminal_no}`
- **Security Dependencies**: Authentication via FastAPI dependency injection
- **Pub/Sub Authentication**: Special authentication handling for notification callbacks

### Additional Security Functions

#### get_service_account_info
```python
def get_service_account_info() -> dict:
    """Get service account information"""
    
    # Returns dictionary containing service name and tenant ID
    # Service account information for JWT token generation
```

## 6. Communication Utilities (utils/)

### HTTP Client Helper (`http_client_helper.py`)

```python
class HttpClientHelper:
    """Asynchronous HTTP client (httpx-based)"""
    
    # Connection pool management
    # Configurable retry mechanism
    # Service discovery functionality
    # Asynchronous context management
    # Shared client pool
```

#### Main Features

- **Async HTTP**: High-performance HTTP communication based on httpx library
- **Retry Logic**: Configurable retry count and backoff
- **Service Discovery**: Automatic URL resolution for microservices
- **Context Management**: Proper resource cleanup
- **Client Pool**: Shared instances for performance improvement

### Dapr Integration (`dapr_client_helper.py`)

```python
class DaprClientHelper:
    """Unified Dapr client (Pub/Sub & State Store)"""
    
    # Circuit breaker functionality
    # Automatic retry mechanism
    # State management operations
    # Event publishing functionality
```

#### Circuit Breaker Implementation

- **State Transitions**: Closed → Open → Half-Open pattern
- **Threshold Settings**: Configurable failure count (default: 3 times)
- **Recovery**: Automatic recovery after timeout (default: 60 seconds)
- **Logging**: Comprehensive state transition logging

## 7. Middleware and Logging (middleware/)

### Request Log Middleware (`log_requests.py`)

```python
class RequestLogMiddleware:
    """Comprehensive request/response logging"""
    
    # Request/response details, timing, authentication info
    # Dual storage (file logs + database)
    # Multi-database (common DB + tenant-specific DB)
    # Context capture (user, terminal, staff, client)
    # WebSocket support (log bypass)
```

#### Feature Details

- **Processing Time**: Millisecond-precision timing measurement
- **Body Capture**: Request and response body logging
- **Error Handling**: Graceful handling of logging failures
- **Privacy**: Sanitization of sensitive information

## 8. Business Logic Support

### Transaction Types (`enums.py`)

```python
class TransactionType(Enum):
    """Transaction types"""
    
    # Sales operations (string values)
    NORMAL_SALE = "101"      # Normal sale
    RETURN_SALE = "102"      # Return
    VOID_SALE = "201"        # Void sale
    VOID_RETURN = "202"      # Void return
    
    # Terminal operations
    TERMINAL_OPEN = "301"    # Open
    TERMINAL_CLOSE = "302"   # Close
    
    # Cash operations
    CASH_IN = "401"          # Cash in
    CASH_OUT = "402"         # Cash out
    
    # Reports
    FLASH_REPORT = "501"     # Flash report
    DAILY_REPORT = "502"     # Daily report
```

### Tax Calculation and Rounding

```python
class TaxType(Enum):
    """Tax types"""
    EXTERNAL = "EXTERNAL"  # External tax (added)
    INTERNAL = "INTERNAL"  # Internal tax (included)
    EXEMPT = "EXEMPT"      # Tax exempt

class RoundMethod(Enum):
    """Rounding methods (RoundMethod, not RoundingMethod)"""
    ROUND = "ROUND"  # Round
    FLOOR = "FLOOR"  # Floor
    CEIL = "CEIL"    # Ceiling
```

### Time Management (`misc.py`)

```python
def get_current_time() -> datetime:
    """Get unified application time"""
    return datetime.now(get_timezone())

def to_iso_string(dt: datetime) -> str:
    """Generate ISO format timestamp"""
    return dt.isoformat()
```

## 9. Receipt Functionality (receipt/)

### Abstract Receipt Data (`abstract_receipt_data.py`)

```python
class AbstractReceiptData(ABC):
    """Abstract base class for receipt data"""
    
    @abstractmethod
    def make_receipt_data(self) -> ReceiptData:
        """Generate receipt data (main method)"""
        pass
    
    @abstractmethod
    def make_receipt_header(self) -> str:
        """Generate receipt header"""
        pass
    
    @abstractmethod
    def make_receipt_body(self) -> str:
        """Generate receipt body"""
        pass
    
    @abstractmethod
    def make_receipt_footer(self) -> str:
        """Generate receipt footer"""
        pass
```

### Receipt Data Model (`receipt_data_model.py`)

```python
class ReceiptData(BaseModel):
    """Receipt data class (ReceiptData, not ReceiptDataModel)"""
    
    tenant_id: str
    terminal_id: str
    business_date: str
    generate_date_time: str
    tranlog_id: str
    receipt_text: str
    journal_text: str
```

## 10. Additional Features

### verify_pubsub_notification_auth
```python
async def verify_pubsub_notification_auth(
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> dict:
    """Verify authentication for Pub/Sub notification callbacks"""
    
    # Accepts either JWT token or PUBSUB_NOTIFY_API_KEY
    # Returns: {"auth_type": "jwt"|"api_key", "service": str, "tenant_id": str}
```

### get_tenant_id_with_security
```python
async def get_tenant_id_with_security(
    terminal_id: str = Path(...),
    api_key: Optional[str] = Security(api_key_header), 
    token: Optional[str] = Depends(oauth2_scheme),
    is_terminal_service: Optional[bool] = False
) -> str:
    """Get tenant ID using terminal_id from path parameter"""
```

### get_terminal_info_with_api_key
```python
async def get_terminal_info_with_api_key(
    terminal_id: str = Query(...),
    api_key: str = Security(api_key_header),
    is_terminal_service: Optional[bool] = False
) -> TerminalInfoDocument:
    """Get complete terminal information with API key authentication"""
```

## Summary

The Kugel Commons library provides a robust foundation for microservices architecture:

### Key Values

- **Consistent Data Access**: Asynchronous MongoDB repository pattern (methods with `_async` suffix)
- **Comprehensive Error Handling**: Structured exception handling with multi-language support (with `details` parameter)
- **Secure Communication**: Dual authentication with tenant isolation (dictionary return values)
- **Resilient Architecture**: Circuit breaker and retry mechanisms
- **Standardized APIs**: Consistent response format and pagination (using `data` field)
- **Comprehensive Logging**: Request/response auditing with context
- **Configuration Management**: Environment-based settings with sensible defaults (including stamp duty settings)

This library effectively abstracts common concerns while maintaining flexibility for service-specific requirements, making it an excellent foundation for the POS microservices ecosystem.

## Usage Examples

### 1. Repository Pattern Usage

```python
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from motor.motor_asyncio import AsyncIOMotorDatabase

class ItemStoreMasterRepository(AbstractRepository[ItemStoreMasterDocument]):
    """Example repository implementation for store-specific item master"""
    
    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str, store_code: str):
        # Pass collection name, document class, and DB instance to AbstractRepository constructor
        super().__init__("item_store_master", ItemStoreMasterDocument, db)
        self.tenant_id = tenant_id
        self.store_code = store_code
    
    async def get_item_store_by_code(self, item_code: str) -> ItemStoreMasterDocument:
        """Get store-specific item information by item code"""
        filter = {
            "tenant_id": self.tenant_id, 
            "store_code": self.store_code, 
            "item_code": item_code
        }
        # Use get_one_async method from AbstractRepository
        return await self.get_one_async(filter)
    
    async def create_item_store_async(self, item_store_doc: ItemStoreMasterDocument) -> ItemStoreMasterDocument:
        """Create new store-specific item"""
        item_store_doc.tenant_id = self.tenant_id
        item_store_doc.store_code = self.store_code
        # Use create_async method from AbstractRepository
        success = await self.create_async(item_store_doc)
        if success:
            return item_store_doc
        else:
            raise Exception("Failed to create item store")

```

### 2. Authentication Usage

```python
from kugel_common.security import get_current_user
from fastapi import Depends

@app.get("/api/v1/protected")
async def protected_endpoint(current_user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {current_user.get('username')}"}
```

### 3. Error Handling

```python
from kugel_common.exceptions import InvalidRequestDataException
import logging

logger = logging.getLogger(__name__)

def validate_item_code(item_code: str):
    if not item_code or len(item_code) < 3:
        # InvalidRequestDataException takes 3 arguments
        raise InvalidRequestDataException(
            "Item code must be at least 3 characters",  # System message
            logger=logger,  # Logger (optional)
            original_exception=None  # Original exception (optional)
        )
        
# Or, general error handling in service layer
from kugel_common.exceptions import ServiceException
from kugel_common.exceptions.error_codes import ErrorCode, ErrorMessage

def process_item(item_code: str):
    if not item_code:
        raise ServiceException(
            message="Item code is required",
            logger=logger,
            error_code=ErrorCode.VALIDATION_ERROR,
            user_message=ErrorMessage.get_message(ErrorCode.VALIDATION_ERROR),
            status_code=422
        )
```

### 4. HTTP Communication

```python
from kugel_common.utils.http_client_helper import HttpClientHelper

async def call_other_service():
    # HttpClientHelper is implemented with singleton pattern
    client = HttpClientHelper()
    
    # get method takes url and service_name separately
    response = await client.get(
        url="/api/v1/data",
        service_name="cart",  # Specify service name to resolve base URL
        timeout=30.0  # Timeout (optional)
    )
    return response.json()
```

### 5. Dapr Integration

```python
from kugel_common.utils.dapr_client_helper import get_dapr_client

async def publish_event(event_data: dict):
    async with get_dapr_client() as client:
        await client.publish_event(
            "pubsub",
            "transaction_complete",
            event_data
        )
```