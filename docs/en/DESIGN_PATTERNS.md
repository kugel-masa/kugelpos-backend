# Kugel POS Design Patterns - Detailed Guide

## Table of Contents
1. [Overview](#overview)
2. [State Machine Pattern](#state-machine-pattern)
3. [Plugin Architecture](#plugin-architecture)
4. [Repository Pattern](#repository-pattern)
5. [Circuit Breaker Pattern](#circuit-breaker-pattern)
6. [Strategy Pattern](#strategy-pattern)
7. [Other Patterns](#other-patterns)

## Overview

The Kugel POS system effectively combines multiple design patterns to enhance maintainability, extensibility, and testability. This document provides a detailed explanation of each pattern's implementation with actual code references.

## State Machine Pattern

### Overview
The cart service adopts the State Machine pattern for managing the shopping cart lifecycle. This enables controlled operations based on cart state and prevents invalid operations.

### Implementation Location
- `/services/cart/app/services/cart_state_manager.py`
- `/services/cart/app/services/states/`

### Class Structure

```python
# abstract_state.py - Base class for all states
class AbstractState(ABC):
    """
    Abstract base class for cart states
    Defines allowed operations for each state
    """
    
    @abstractmethod
    def check_event_sequence(self, event: str) -> bool:
        """Check if the specified event can be executed in this state"""
        pass
```

### State Transition Diagram

```
┌─────────┐     ┌──────┐     ┌──────────────┐     ┌────────┐     ┌───────────┐
│ Initial │ --> │ Idle │ --> │ EnteringItem │ --> │ Paying │ --> │ Completed │
└─────────┘     └──┬───┘     └──────┬───────┘     └───┬────┘     └───────────┘
                   │                 │                 │
                   └─────────────────┴─────────────────┴──> ┌───────────┐
                                                            │ Cancelled │
                                                            └───────────┘
```

### Concrete Implementation Examples

#### 1. State Manager Class

```python
# cart_state_manager.py
class CartStateManager:
    """
    Manages cart state transitions
    """
    
    def __init__(self):
        # Create instances of each state
        self.initial_state = InitialState()
        self.idle_state = IdleState()
        self.entering_item_state = EnteringItemState()
        self.paying_state = PayingState()
        self.completed_state = CompletedState()
        self.cancelled_state = CancelledState()
        
        # Set initial state
        self.current_state = self.initial_state
    
    def set_state(self, state: str):
        """Set the state"""
        if state == CartStatus.Initial.value:
            self.current_state = self.initial_state
        elif state == CartStatus.Idle.value:
            self.current_state = self.idle_state
        elif state == CartStatus.EnteringItem.value:
            self.current_state = self.entering_item_state
        elif state == CartStatus.Paying.value:
            self.current_state = self.paying_state
        elif state == CartStatus.Completed.value:
            self.current_state = self.completed_state
        elif state == CartStatus.Cancelled.value:
            self.current_state = self.cancelled_state
    
    def check_event_sequence(self, event: str) -> bool:
        """Check if the specified event can be executed in the current state"""
        return self.current_state.check_event_sequence(event)
```

#### 2. Concrete State Class Examples

```python
# idle_state.py
class IdleState(AbstractState):
    """
    Idle state implementation
    Allows adding items, canceling transactions, etc.
    """
    
    def check_event_sequence(self, event: str) -> bool:
        allowed_events = [
            CartEvent.ADD_ITEM_TO_CART.value,
            CartEvent.GET_CART.value,
            CartEvent.CANCEL_TRANSACTION.value,
            CartEvent.SUSPEND_TRANSACTION.value
        ]
        return event in allowed_events

# entering_item_state.py
class EnteringItemState(AbstractState):
    """
    Entering item state implementation
    Allows item operations, starting payment, canceling transactions, etc.
    """
    
    def check_event_sequence(self, event: str) -> bool:
        allowed_events = [
            CartEvent.ADD_ITEM_TO_CART.value,
            CartEvent.DELETE_ITEM_FROM_CART.value,
            CartEvent.UPDATE_ITEM_IN_CART.value,
            CartEvent.ADD_DISCOUNT_TO_CART.value,
            CartEvent.START_PAYMENT.value,
            CartEvent.CANCEL_TRANSACTION.value,
            CartEvent.GET_CART.value
        ]
        return event in allowed_events
```

#### 3. State Transition Execution Example

```python
# Usage example in cart_service.py
async def add_item_to_cart(self, cart_id: str, item_data: dict):
    # Check if adding items is allowed in the current state
    if not self.state_manager.check_event_sequence(CartEvent.ADD_ITEM_TO_CART.value):
        raise CartOperationNotAllowedException(
            f"Cannot add item in {self.state_manager.current_state} state"
        )
    
    # Add the item
    await self._add_item_logic(cart_id, item_data)
    
    # Update state (Idle → EnteringItem)
    if self.state_manager.current_state == self.state_manager.idle_state:
        self.state_manager.set_state(CartStatus.EnteringItem.value)
```

### Benefits
- Organizes complex state transition logic
- Prevents invalid operations
- Easy to add new states
- Clear responsibilities for each state

## Plugin Architecture

### Overview
The cart service and report service adopt a plugin architecture that allows dynamic extension of functionality.

### Implementation Location
- Cart Service: `/services/cart/app/services/strategies/`
- Report Service: `/services/report/app/services/plugins/`

### Plugin Configuration File

```json
// plugins.json
{
    "payment_strategies": [
        {
            "module": "app.services.strategies.payments.cash",
            "class": "PaymentByCash",
            "args": ["01"],
            "kwargs": {},
            "description": "Cash payment processing"
        },
        {
            "module": "app.services.strategies.payments.cashless",
            "class": "PaymentByCashless",
            "args": ["02", "03", "04"],
            "kwargs": {},
            "description": "Cashless payment processing"
        }
    ],
    "sales_promotions": [
        {
            "module": "app.services.strategies.sales_promo.sales_promo_sample",
            "class": "SalesPromoSample",
            "args": [],
            "kwargs": {},
            "description": "Sales promotion sample"
        }
    ],
    "receipt_data": [
        {
            "module": "app.services.strategies.receipt_data.receipt_data_sample",
            "class": "ReceiptDataSample",
            "args": [],
            "kwargs": {},
            "description": "Receipt data customization sample"
        }
    ]
}
```

### Plugin Manager Implementation

```python
# cart_strategy_manager.py
class CartStrategyManager:
    """
    Dynamically loads and manages plugins
    """
    
    def __init__(self):
        self.payment_strategies = {}
        self.sales_promotions = []
        self.receipt_data_strategies = []
        self._load_strategies()
    
    def _load_strategies(self):
        """Load plugins from plugins.json"""
        plugin_file = Path(__file__).parent / "strategies" / "plugins.json"
        
        with open(plugin_file, 'r', encoding='utf-8') as f:
            plugins = json.load(f)
        
        # Load payment strategies
        for config in plugins.get("payment_strategies", []):
            self._load_payment_strategy(config)
        
        # Load sales promotions
        for config in plugins.get("sales_promotions", []):
            self._load_sales_promotion(config)
    
    def _load_payment_strategy(self, config: dict):
        """Dynamically load payment strategy"""
        try:
            # Dynamic module import
            module = importlib.import_module(config["module"])
            # Get class
            strategy_class = getattr(module, config["class"])
            # Create instance
            instance = strategy_class(*config.get("args", []), **config.get("kwargs", {}))
            
            # Register strategy for each payment code
            for payment_code in config.get("args", []):
                self.payment_strategies[payment_code] = instance
                
            logger.info(f"Loaded payment strategy: {config['class']}")
            
        except Exception as e:
            logger.error(f"Failed to load payment strategy: {config['class']}: {e}")
```

### Plugin Interface

```python
# abstract_payment.py
class AbstractPayment(ABC):
    """
    Abstract base class for payment strategies
    All payment methods must implement this interface
    """
    
    @abstractmethod
    async def pay(self, cart_doc, payment_code: str, amount: Decimal, detail: dict):
        """Execute payment processing"""
        pass
    
    @abstractmethod
    async def refund(self, cart_doc, payment_index: int):
        """Execute refund processing"""
        pass
    
    @abstractmethod
    async def cancel(self, cart_doc, payment_index: int):
        """Execute payment cancellation"""
        pass
```

### Plugin Implementation Example

```python
# cash.py - Cash payment plugin
class PaymentByCash(AbstractPayment):
    """
    Cash payment implementation
    Includes cash-specific processing like change calculation
    """
    
    def __init__(self, *payment_codes):
        self.payment_codes = payment_codes
    
    async def pay(self, cart_doc, payment_code: str, amount: Decimal, detail: dict):
        # Create payment information
        payment = await self.create_cart_payment_async(
            cart_doc, payment_code, amount, detail
        )
        
        # Cash-specific processing: change calculation
        self.update_cart_change(cart_doc, payment)
        
        # Update cart balance
        self.update_cart_balance(cart_doc, payment.amount)
        
        # Add payment information
        cart_doc.payments.append(payment)
        
        return cart_doc
    
    def update_cart_change(self, cart_doc, payment):
        """Calculate and update change"""
        if payment.deposit_amount > payment.amount:
            cart_doc.change_amount += (payment.deposit_amount - payment.amount)
```

### Using Plugins

```python
# cart_service.py
async def add_payment(self, cart_id: str, payment_data: dict):
    """Add payment"""
    # Get strategy for payment method
    payment_strategy = self.strategy_manager.get_payment_strategy(
        payment_data["payment_code"]
    )
    
    if not payment_strategy:
        raise InvalidPaymentMethodException(
            f"Payment method {payment_data['payment_code']} not supported"
        )
    
    # Execute payment processing using strategy
    cart_doc = await payment_strategy.pay(
        cart_doc,
        payment_data["payment_code"],
        payment_data["amount"],
        payment_data.get("detail", {})
    )
```

### Benefits
- Add new payment methods or features by editing configuration files
- Separation of core functionality and plugins
- Easy testing (create mock plugins)
- Customer-specific customization possible

## Repository Pattern

### Overview
A pattern that abstracts the data access layer and separates business logic from database operations.

### Implementation Location
- Common: `/services/commons/src/kugel_common/models/repositories/abstract_repository.py`
- Each Service: `*/app/models/repositories/`

### Abstract Repository Implementation

```python
# abstract_repository.py
class AbstractRepository(ABC, Generic[Tdocument]):
    """
    Generic abstract base class for repositories
    Defines all CRUD operations
    """
    
    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str, 
                 document_class: Type[Tdocument]):
        self.database = database
        self.collection_name = collection_name
        self.document_class = document_class
        self.dbcollection = database[collection_name]
        self.session: Optional[AsyncIOMotorClientSession] = None
    
    async def create_async(self, document: Tdocument) -> bool:
        """Create a document"""
        try:
            # Set timestamps
            document.created_at = get_app_time()
            document.updated_at = document.created_at
            
            # Insert into MongoDB
            response = await self.dbcollection.insert_one(
                document.model_dump(by_alias=True, exclude_none=True),
                session=self.session
            )
            
            return response.inserted_id is not None
            
        except DuplicateKeyError:
            raise KeyDuplicationException(
                error_code=ErrorCode.KEY_DUPLICATION.value,
                detail=f"Document with key already exists"
            )
    
    async def find_by_id_async(self, id: str) -> Optional[Tdocument]:
        """Find document by ID"""
        document = await self.dbcollection.find_one(
            {"_id": id}, 
            session=self.session
        )
        
        if document:
            return self.document_class(**document)
        
        return None
    
    async def update_async(self, id: str, document: Tdocument) -> bool:
        """Update document"""
        # Set update timestamp
        document.updated_at = get_app_time()
        
        # Optimistic locking retry logic
        for attempt in range(3):
            try:
                result = await self.dbcollection.replace_one(
                    {"_id": id},
                    document.model_dump(by_alias=True, exclude_none=True),
                    session=self.session
                )
                
                return result.modified_count > 0
                
            except OperationFailure as e:
                if "WriteConflict" in str(e) and attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                raise
    
    async def find_with_pagination_async(
        self, 
        filter_dict: dict,
        page: int = 1,
        size: int = 20,
        sort: Optional[List[Tuple[str, int]]] = None
    ) -> Tuple[List[Tdocument], int]:
        """Search with pagination"""
        # Get total count
        total_count = await self.dbcollection.count_documents(
            filter_dict, 
            session=self.session
        )
        
        # Calculate pagination
        skip = (page - 1) * size
        
        # Execute query
        cursor = self.dbcollection.find(
            filter_dict, 
            session=self.session
        ).skip(skip).limit(size)
        
        if sort:
            cursor = cursor.sort(sort)
        
        # Convert results
        documents = []
        async for doc in cursor:
            documents.append(self.document_class(**doc))
        
        return documents, total_count
    
    @asynccontextmanager
    async def transaction(self):
        """Transaction management"""
        async with await self.database.client.start_session() as session:
            async with session.start_transaction():
                self.session = session
                try:
                    yield self
                finally:
                    self.session = None
```

### Concrete Repository Implementation Example

```python
# cart_repository.py
class CartRepository(AbstractRepository[CartDocument]):
    """
    Cart-specific repository implementation
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, "cart", CartDocument)
    
    async def find_active_cart_by_terminal_async(
        self, 
        terminal_id: str
    ) -> Optional[CartDocument]:
        """Find active cart for terminal"""
        filter_dict = {
            "terminal_id": terminal_id,
            "status": {"$in": [
                CartStatus.Idle.value,
                CartStatus.EnteringItem.value,
                CartStatus.Paying.value
            ]}
        }
        
        cart = await self.dbcollection.find_one(
            filter_dict, 
            session=self.session
        )
        
        if cart:
            return CartDocument(**cart)
        
        return None
    
    async def update_cart_status_async(
        self, 
        cart_id: str, 
        status: str
    ) -> bool:
        """Update only cart status (partial update)"""
        update_dict = {
            "$set": {
                "status": status,
                "updated_at": get_app_time()
            }
        }
        
        result = await self.dbcollection.update_one(
            {"_id": cart_id},
            update_dict,
            session=self.session
        )
        
        return result.modified_count > 0
    
    async def add_item_to_cart_async(
        self, 
        cart_id: str, 
        item: LineItem
    ) -> bool:
        """Add item to cart (append to array)"""
        update_dict = {
            "$push": {"items": item.model_dump()},
            "$set": {"updated_at": get_app_time()}
        }
        
        result = await self.dbcollection.update_one(
            {"_id": cart_id},
            update_dict,
            session=self.session
        )
        
        return result.modified_count > 0
```

### Repository Usage Example

```python
# cart_service.py
class CartService:
    def __init__(self, cart_repository: CartRepository):
        self.cart_repository = cart_repository
    
    async def create_new_cart(self, terminal_id: str) -> CartDocument:
        """Create a new cart"""
        # Business logic: Initialize cart
        cart = CartDocument(
            terminal_id=terminal_id,
            status=CartStatus.Initial.value,
            items=[],
            total_amount=Decimal("0"),
            created_by="system"
        )
        
        # Save to database using repository
        success = await self.cart_repository.create_async(cart)
        
        if not success:
            raise CartCreationFailedException("Failed to create cart")
        
        return cart
    
    async def add_item_with_transaction(
        self, 
        cart_id: str, 
        item_data: dict
    ) -> CartDocument:
        """Add item within a transaction"""
        async with self.cart_repository.transaction():
            # Get cart
            cart = await self.cart_repository.find_by_id_async(cart_id)
            
            if not cart:
                raise CartNotFoundException(f"Cart {cart_id} not found")
            
            # Business logic: Add item
            line_item = self._create_line_item(item_data)
            cart.items.append(line_item)
            cart.total_amount += line_item.amount
            
            # Update cart
            success = await self.cart_repository.update_async(cart_id, cart)
            
            if not success:
                raise CartUpdateFailedException("Failed to update cart")
            
            return cart
```

### Benefits
- Centralized data access logic
- Separation of business logic and database operations
- Easy testing (create mock repositories)
- Minimizes impact of database changes
- Simplified transaction management

## Circuit Breaker Pattern

### Overview
A pattern that prevents cascading failures from external service failures. After a certain number of failures, it opens the circuit and blocks requests for a period.

### Implementation Locations
- **HTTP Client with Retry**: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- **Dapr Client with Circuit Breaker**: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`
- **Legacy Implementations**: 
  - `/services/cart/app/utils/pubsub_manager.py` (migrated to DaprClientHelper)
  - `/services/journal/app/utils/state_store_manager.py` (migrated to DaprClientHelper)

### Implementation Details

#### HTTP Client with Retry Logic

```python
# http_client_helper.py
class HttpClientHelper:
    """
    Unified HTTP client with built-in retry logic
    """
    
    def __init__(self, base_url: str = "", timeout: int = 30, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = 1  # Initial retry delay
        
        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
    
    async def _make_request(self, method: str, url: str, **kwargs):
        """Execute request with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
        
        raise HttpClientError(f"Request failed after {self.max_retries} attempts")
```

#### Dapr Client with Circuit Breaker Implementation

```python
# dapr_client_helper.py
class DaprClientHelper:
    """
    Unified Dapr client with circuit breaker pattern
    """
    
    def __init__(self, circuit_breaker_threshold: int = 3, circuit_breaker_timeout: int = 60):
        # Dapr HTTP endpoint configuration
        dapr_http_port = os.getenv("DAPR_HTTP_PORT", "3500")
        self.base_url = f"http://localhost:{dapr_http_port}"
        
        # Circuit breaker configuration
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
    
    def _check_circuit_breaker(self) -> bool:
        """
        Check circuit breaker state
        Returns:
            True: Circuit is closed (normal)
            False: Circuit is open (blocking)
        """
        if self._circuit_open:
            current_time = time.time()
            # Close circuit after timeout
            if (current_time - self._last_failure_time) > self._reset_timeout:
                logger.info("Circuit breaker reset - closing circuit")
                self._circuit_open = False
                self._failure_count = 0
                return True
            return False
        return True
    
    def _handle_failure(self):
        """Record failure and open circuit if necessary"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self._failure_threshold:
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )
            self._circuit_open = True
    
    def _handle_success(self):
        """Record success and reset failure count"""
        if self._failure_count > 0:
            logger.info("Circuit breaker - resetting failure count after success")
        self._failure_count = 0
        self._circuit_open = False
    
    async def publish_event_async(
        self, 
        topic: str, 
        event_data: dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Publish event asynchronously
        
        Returns:
            Tuple[bool, Optional[str]]: (success/failure, error message)
        """
        # Check circuit breaker
        if not self._check_circuit_breaker():
            logger.warning(f"Circuit breaker is open - rejecting publish to {topic}")
            return False, "Circuit breaker is open"
        
        try:
            # Call Dapr Pub/Sub API
            url = f"{self.base_url}/v1.0/publish/{self.pubsub_name}/{topic}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=event_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 204:
                    # Success
                    self._handle_success()
                    logger.info(f"Successfully published event to {topic}")
                    return True, None
                else:
                    # Failure
                    self._handle_failure()
                    error_msg = f"Failed to publish: {response.status_code}"
                    logger.error(error_msg)
                    return False, error_msg
                    
        except httpx.TimeoutException:
            self._handle_failure()
            error_msg = "Timeout while publishing event"
            logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            self._handle_failure()
            error_msg = f"Error publishing event: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
```

### Usage Example

```python
# cart_service_event.py
class CartServiceEvent:
    """
    Cart service event processing
    """
    
    def __init__(self):
        self.pubsub_manager = PubSubManager()
    
    async def publish_transaction_completed(
        self, 
        transaction_data: dict
    ) -> bool:
        """
        Publish transaction completion event
        Protected by circuit breaker
        """
        # Prepare event data
        event_data = {
            "event_type": "transaction_completed",
            "transaction_id": transaction_data["id"],
            "timestamp": datetime.utcnow().isoformat(),
            "data": transaction_data
        }
        
        # Publish using Pub/Sub manager
        success, error = await self.pubsub_manager.publish_event_async(
            topic="tranlog_report",
            event_data=event_data
        )
        
        if not success:
            # Error handling (but don't throw exception)
            logger.warning(
                f"Failed to publish transaction event: {error}. "
                f"Transaction {transaction_data['id']} will continue without event."
            )
            # Notify monitoring system
            await self._notify_monitoring_system(transaction_data["id"], error)
        
        return success
    
    async def _notify_monitoring_system(
        self, 
        transaction_id: str, 
        error: str
    ):
        """Notify monitoring system of error"""
        # Slack notification, metrics recording, etc.
        pass
```

### Circuit Breaker State Transitions

```
┌────────┐  Failures < Threshold  ┌────────┐  Failures >= Threshold ┌────────┐
│ Closed │ ←─────────────────── │  Half  │ ────────────────────→ │  Open  │
│(Normal)│                      │  Open  │                        │(Blocked)│
└────────┘                      └────────┘                        └────────┘
    ↑                                                                  │
    └────────────────── Timeout Elapsed ───────────────────────────────┘
```

### Benefits
- Prevents cascading failures from propagating through the system
- Reduces recovery time by automatically detecting service recovery
- Eliminates wasteful retries to failing services
- Early failure detection and notification
- Non-blocking implementation allows graceful degradation

## Strategy Pattern

### Overview
A pattern that encapsulates algorithms and makes them interchangeable at runtime. Used for payment processing and tax calculation.

### Implementation Location
- Payment Strategies: `/services/cart/app/services/strategies/payments/`
- Tax Calculation: `/services/cart/app/services/logics/calc_tax_logic.py`

### Payment Strategy Implementation

#### Abstract Strategy

```python
# abstract_payment.py
class AbstractPayment(ABC):
    """
    Abstract base class for payment strategies
    """
    
    @abstractmethod
    async def pay(
        self, 
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartDocument:
        """Execute payment processing"""
        pass
    
    @abstractmethod
    async def refund(
        self, 
        cart_doc: CartDocument,
        payment_index: int
    ) -> CartDocument:
        """Execute refund processing"""
        pass
    
    async def create_cart_payment_async(
        self,
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartPayment:
        """Common method to create payment information"""
        return CartPayment(
            payment_code=payment_code,
            amount=amount,
            deposit_amount=detail.get("deposit_amount", amount),
            payment_detail=detail,
            sequence=len(cart_doc.payments) + 1
        )
    
    def update_cart_balance(
        self, 
        cart_doc: CartDocument, 
        amount: Decimal
    ):
        """Common method to update cart balance"""
        cart_doc.payment_total += amount
        cart_doc.balance = cart_doc.total_amount - cart_doc.payment_total
```

#### Concrete Strategy Implementations

```python
# cash.py - Cash payment strategy
class PaymentByCash(AbstractPayment):
    """
    Cash payment implementation
    Feature: Requires change calculation
    """
    
    async def pay(
        self, 
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartDocument:
        # Create payment information
        payment = await self.create_cart_payment_async(
            cart_doc, payment_code, amount, detail
        )
        
        # Cash-specific processing: change calculation
        self.update_cart_change(cart_doc, payment)
        
        # Common processing: update balance
        self.update_cart_balance(cart_doc, payment.amount)
        
        # Add payment information
        cart_doc.payments.append(payment)
        
        return cart_doc
    
    def update_cart_change(
        self, 
        cart_doc: CartDocument, 
        payment: CartPayment
    ):
        """Calculate change"""
        # If deposit amount is more than payment amount
        if payment.deposit_amount > payment.amount:
            change = payment.deposit_amount - payment.amount
            cart_doc.change_amount += change
            logger.info(f"Change calculated: {change}")
    
    async def refund(
        self, 
        cart_doc: CartDocument,
        payment_index: int
    ) -> CartDocument:
        """Cash refund processing"""
        if payment_index >= len(cart_doc.payments):
            raise InvalidPaymentIndexException()
        
        payment = cart_doc.payments[payment_index]
        
        # Mark as refunded
        payment.is_refunded = True
        payment.refund_amount = payment.amount
        
        # Adjust balance
        cart_doc.payment_total -= payment.amount
        cart_doc.balance = cart_doc.total_amount - cart_doc.payment_total
        
        # Adjust change
        if cart_doc.change_amount > 0:
            cart_doc.change_amount = max(0, cart_doc.change_amount - payment.amount)
        
        return cart_doc

# cashless.py - Cashless payment strategy
class PaymentByCashless(AbstractPayment):
    """
    Cashless payment implementation
    Features: Overpayment check, no change
    """
    
    async def pay(
        self, 
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartDocument:
        # Create payment information
        payment = await self.create_cart_payment_async(
            cart_doc, payment_code, amount, detail
        )
        
        # Cashless-specific processing: overpayment check
        self.check_deposit_over(cart_doc, payment.deposit_amount)
        
        # Common processing: update balance
        self.update_cart_balance(cart_doc, payment.amount)
        
        # Add payment information
        cart_doc.payments.append(payment)
        
        return cart_doc
    
    def check_deposit_over(
        self, 
        cart_doc: CartDocument, 
        deposit_amount: Decimal
    ):
        """Cashless doesn't allow overpayment"""
        remaining_balance = cart_doc.total_amount - cart_doc.payment_total
        
        if deposit_amount > remaining_balance:
            raise OverPaymentException(
                f"Cashless payment cannot exceed balance. "
                f"Balance: {remaining_balance}, Deposit: {deposit_amount}"
            )
```

### Tax Calculation Strategy Implementation

```python
# calc_tax_logic.py
class CalcTaxLogic:
    """
    Tax calculation logic (uses strategy pattern internally)
    """
    
    def calculate_tax(
        self,
        amount: Decimal,
        tax_rate: Decimal,
        tax_type: TaxType,
        rounding_method: RoundingMethod = RoundingMethod.ROUND_DOWN
    ) -> TaxCalculationResult:
        """
        Select appropriate calculation strategy based on tax type
        """
        if tax_type == TaxType.EXCLUSIVE:
            # Exclusive tax calculation strategy
            return self._calculate_exclusive_tax(
                amount, tax_rate, rounding_method
            )
        elif tax_type == TaxType.INCLUSIVE:
            # Inclusive tax calculation strategy
            return self._calculate_inclusive_tax(
                amount, tax_rate, rounding_method
            )
        elif tax_type == TaxType.EXEMPT:
            # Tax-exempt strategy
            return self._calculate_exempt_tax(amount)
        else:
            raise InvalidTaxTypeException(f"Unknown tax type: {tax_type}")
    
    def _calculate_exclusive_tax(
        self,
        amount: Decimal,
        tax_rate: Decimal,
        rounding_method: RoundingMethod
    ) -> TaxCalculationResult:
        """Exclusive tax: Add tax to price"""
        tax_amount = amount * tax_rate / 100
        
        # Apply rounding
        tax_amount = self._apply_rounding(tax_amount, rounding_method)
        
        return TaxCalculationResult(
            subtotal=amount,
            tax_amount=tax_amount,
            total=amount + tax_amount,
            tax_rate=tax_rate,
            tax_type=TaxType.EXCLUSIVE
        )
    
    def _calculate_inclusive_tax(
        self,
        amount: Decimal,
        tax_rate: Decimal,
        rounding_method: RoundingMethod
    ) -> TaxCalculationResult:
        """Inclusive tax: Tax included in price"""
        # Calculate price without tax
        subtotal = amount / (1 + tax_rate / 100)
        subtotal = self._apply_rounding(subtotal, rounding_method)
        
        # Calculate tax amount
        tax_amount = amount - subtotal
        
        return TaxCalculationResult(
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=amount,
            tax_rate=tax_rate,
            tax_type=TaxType.INCLUSIVE
        )
    
    def _calculate_exempt_tax(
        self,
        amount: Decimal
    ) -> TaxCalculationResult:
        """Tax-exempt: No tax"""
        return TaxCalculationResult(
            subtotal=amount,
            tax_amount=Decimal("0"),
            total=amount,
            tax_rate=Decimal("0"),
            tax_type=TaxType.EXEMPT
        )
    
    def _apply_rounding(
        self,
        value: Decimal,
        method: RoundingMethod
    ) -> Decimal:
        """Rounding strategy"""
        if method == RoundingMethod.ROUND_DOWN:
            return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
        elif method == RoundingMethod.ROUND_UP:
            return value.quantize(Decimal("1"), rounding=ROUND_UP)
        elif method == RoundingMethod.ROUND_HALF_UP:
            return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        else:
            return value
```

### Strategy Selection and Usage

```python
# cart_service.py
class CartService:
    """
    Cart service (uses strategies)
    """
    
    def __init__(self):
        self.strategy_manager = CartStrategyManager()
        self.tax_calculator = CalcTaxLogic()
    
    async def process_payment(
        self,
        cart_id: str,
        payment_request: PaymentRequest
    ) -> CartDocument:
        """Payment processing (select and execute appropriate strategy)"""
        # Get cart
        cart = await self.cart_repository.find_by_id_async(cart_id)
        
        # Get strategy for payment method
        payment_strategy = self.strategy_manager.get_payment_strategy(
            payment_request.payment_code
        )
        
        if not payment_strategy:
            raise UnsupportedPaymentMethodException(
                f"Payment method {payment_request.payment_code} not supported"
            )
        
        # Execute strategy
        cart = await payment_strategy.pay(
            cart,
            payment_request.payment_code,
            payment_request.amount,
            payment_request.detail
        )
        
        # Save cart
        await self.cart_repository.update_async(cart_id, cart)
        
        return cart
    
    def calculate_item_tax(
        self,
        item: LineItem,
        tax_master: TaxMaster
    ) -> LineItem:
        """Item tax calculation (uses tax calculation strategy)"""
        # Execute tax calculation strategy
        tax_result = self.tax_calculator.calculate_tax(
            amount=item.price * item.quantity,
            tax_rate=tax_master.rate,
            tax_type=tax_master.tax_type,
            rounding_method=tax_master.rounding_method
        )
        
        # Apply results to item
        item.tax_amount = tax_result.tax_amount
        item.total_amount = tax_result.total
        item.tax_rate = tax_result.tax_rate
        
        return item
```

### Benefits
- Easy algorithm switching
- Adding new strategies doesn't affect existing code
- Each strategy can be tested independently
- Reduces conditional branching

## Dapr Integration Pattern

### Overview
Dapr (Distributed Application Runtime) provides building blocks for microservices. Kugelpos uses Dapr for pub/sub messaging and state management with a unified client approach.

### Implementation
- **Unified Client**: `DaprClientHelper` in commons library
- **Service Integration**: All services use the same client interface
- **Building Blocks Used**:
  - Pub/Sub for event-driven communication
  - State Store for distributed state management

### Pub/Sub Implementation

```python
# Using DaprClientHelper for publishing
from kugel_common.utils.dapr_client_helper import get_dapr_client

async def publish_transaction_event(transaction_data: dict):
    async with get_dapr_client() as client:
        success = await client.publish_event(
            pubsub_name="pubsub",
            topic_name="tranlog_report",
            event_data={
                "transaction_id": transaction_data["id"],
                "amount": transaction_data["total_amount"],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    return success
```

### State Store Implementation

```python
# Using DaprClientHelper for state management
async def save_idempotency_state(message_id: str, processed: bool):
    async with get_dapr_client() as client:
        return await client.save_state(
            store_name="statestore",
            key=f"processed_{message_id}",
            value={"processed": processed, "timestamp": datetime.utcnow().isoformat()}
        )

async def check_idempotency(message_id: str) -> bool:
    async with get_dapr_client() as client:
        state = await client.get_state(
            store_name="statestore",
            key=f"processed_{message_id}"
        )
        return state is not None and state.get("processed", False)
```

### Benefits of Dapr Integration
- **Service Mesh Features**: Built-in service discovery, load balancing
- **Abstraction**: Swappable implementations (Redis, RabbitMQ, etc.)
- **Observability**: Distributed tracing, metrics
- **Security**: mTLS between services
- **Resilience**: Built-in retry policies

## Other Patterns

### Factory Pattern

Plugin managers function as factories:

```python
# cart_strategy_manager.py
class CartStrategyManager:
    """
    Factory for strategy objects
    """
    
    def get_payment_strategy(self, payment_code: str) -> Optional[AbstractPayment]:
        """Return appropriate strategy based on payment code"""
        return self.payment_strategies.get(payment_code)
    
    def create_sales_promotion(self, promo_type: str) -> Optional[AbstractSalesPromo]:
        """Create instance based on promotion type"""
        for promo in self.sales_promotions:
            if promo.promo_type == promo_type:
                return promo
        return None
```

### Template Method Pattern

Abstract base classes define the flow of processing:

```python
# abstract_state.py
class AbstractState(ABC):
    """
    Abstract base class for states (template method)
    """
    
    def process_event(self, event: str, context: dict) -> dict:
        """Template method for event processing"""
        # 1. Check if event is allowed
        if not self.check_event_sequence(event):
            raise EventNotAllowedException()
        
        # 2. Pre-processing
        self.pre_process(event, context)
        
        # 3. Main processing (implemented by subclasses)
        result = self.execute_event(event, context)
        
        # 4. Post-processing
        self.post_process(event, context, result)
        
        return result
    
    @abstractmethod
    def check_event_sequence(self, event: str) -> bool:
        """Check if event is allowed (implemented by subclasses)"""
        pass
    
    @abstractmethod
    def execute_event(self, event: str, context: dict) -> dict:
        """Execute event (implemented by subclasses)"""
        pass
    
    def pre_process(self, event: str, context: dict):
        """Pre-processing (optional)"""
        logger.info(f"Processing event: {event}")
    
    def post_process(self, event: str, context: dict, result: dict):
        """Post-processing (optional)"""
        logger.info(f"Event processed: {event}")
```

### Singleton Pattern

State store manager implementation:

```python
# state_store_manager.py
class StateStoreManager:
    """
    State management using singleton pattern
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.store_name = "statestore"
        self.dapr_port = int(os.getenv("DAPR_HTTP_PORT", 3500))
        self.base_url = f"http://localhost:{self.dapr_port}"
        self._initialized = True
        
        logger.info("StateStoreManager initialized")
    
    async def get_state(self, key: str) -> Optional[dict]:
        """Get state"""
        # Uses same instance throughout application due to singleton
        pass
```

## Summary

The Kugel POS system combines these design patterns to achieve:

1. **Maintainability**: Clear responsibilities for each component with limited impact scope for changes
2. **Extensibility**: Adding new features minimizes impact on existing code
3. **Testability**: Each pattern is independent, making unit testing easy
4. **Flexibility**: Quick adaptation to changing business requirements

These patterns were selected and implemented to address actual business requirements (diverse payment methods, complex tax systems, customizable reports, etc.).