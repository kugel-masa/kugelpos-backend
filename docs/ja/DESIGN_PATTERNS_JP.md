# Kugel POS デザインパターン詳細解説

## 目次
1. [概要](#概要)
2. [ステートマシンパターン](#ステートマシンパターン)
3. [プラグインアーキテクチャ](#プラグインアーキテクチャ)
4. [リポジトリパターン](#リポジトリパターン)
5. [サーキットブレーカーパターン](#サーキットブレーカーパターン)
6. [ストラテジーパターン](#ストラテジーパターン)
7. [その他のパターン](#その他のパターン)

## 概要

Kugel POSシステムでは、保守性、拡張性、テスタビリティを高めるために、複数のデザインパターンを効果的に組み合わせて使用しています。本ドキュメントでは、実際のコードを参照しながら、各パターンの実装について詳しく解説します。

## ステートマシンパターン

### 概要
カートサービスでは、ショッピングカートのライフサイクル管理にステートマシンパターンを採用しています。これにより、カートの状態に応じた操作の制御と、不正な操作の防止を実現しています。

### 実装場所
- `/services/cart/app/services/cart_state_manager.py`
- `/services/cart/app/services/states/`

### クラス構造

```python
# abstract_state.py - すべての状態の基底クラス
class AbstractState(ABC):
    """
    カート状態の抽象基底クラス
    各状態で許可される操作を定義
    """
    
    @abstractmethod
    def check_event_sequence(self, event: str) -> bool:
        """指定されたイベントがこの状態で実行可能かチェック"""
        pass
```

### 状態遷移図

```
┌─────────┐     ┌──────┐     ┌──────────────┐     ┌────────┐     ┌───────────┐
│ Initial │ --> │ Idle │ --> │ EnteringItem │ --> │ Paying │ --> │ Completed │
└─────────┘     └──┬───┘     └──────┬───────┘     └───┬────┘     └───────────┘
                   │                 │                 │
                   └─────────────────┴─────────────────┴──> ┌───────────┐
                                                            │ Cancelled │
                                                            └───────────┘
```

### 具体的な実装例

#### 1. 状態管理クラス

```python
# cart_state_manager.py
class CartStateManager:
    """
    カートの状態遷移を管理するクラス
    """
    
    def __init__(self):
        # 各状態のインスタンスを生成
        self.initial_state = InitialState()
        self.idle_state = IdleState()
        self.entering_item_state = EnteringItemState()
        self.paying_state = PayingState()
        self.completed_state = CompletedState()
        self.cancelled_state = CancelledState()
        
        # 初期状態を設定
        self.current_state = self.initial_state
    
    def set_state(self, state: str):
        """状態を設定する"""
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
        """現在の状態で指定されたイベントが実行可能かチェック"""
        return self.current_state.check_event_sequence(event)
```

#### 2. 具体的な状態クラスの例

```python
# idle_state.py
class IdleState(AbstractState):
    """
    アイドル状態の実装
    商品追加、取引キャンセルなどが可能
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
    商品入力中状態の実装
    商品操作、支払開始、取引キャンセルなどが可能
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

#### 3. 状態遷移の実行例

```python
# cart_service.py での使用例
async def add_item_to_cart(self, cart_id: str, item_data: dict):
    # 現在の状態で商品追加が可能かチェック
    if not self.state_manager.check_event_sequence(CartEvent.ADD_ITEM_TO_CART.value):
        raise CartOperationNotAllowedException(
            f"Cannot add item in {self.state_manager.current_state} state"
        )
    
    # 商品を追加
    await self._add_item_logic(cart_id, item_data)
    
    # 状態を更新（Idle → EnteringItem）
    if self.state_manager.current_state == self.state_manager.idle_state:
        self.state_manager.set_state(CartStatus.EnteringItem.value)
```

### メリット
- 複雑な状態遷移ロジックの整理
- 不正な操作の防止
- 新しい状態の追加が容易
- 各状態の責任が明確

## プラグインアーキテクチャ

### 概要
カートサービスとレポートサービスでは、機能を動的に拡張できるプラグインアーキテクチャを採用しています。

### 実装場所
- カートサービス: `/services/cart/app/services/strategies/`
- レポートサービス: `/services/report/app/services/plugins/`

### プラグイン設定ファイル

```json
// plugins.json
{
    "payment_strategies": [
        {
            "module": "app.services.strategies.payments.cash",
            "class": "PaymentByCash",
            "args": ["01"],
            "kwargs": {},
            "description": "現金支払い処理"
        },
        {
            "module": "app.services.strategies.payments.cashless",
            "class": "PaymentByCashless",
            "args": ["02", "03", "04"],
            "kwargs": {},
            "description": "キャッシュレス支払い処理"
        }
    ],
    "sales_promotions": [
        {
            "module": "app.services.strategies.sales_promo.sales_promo_sample",
            "class": "SalesPromoSample",
            "args": [],
            "kwargs": {},
            "description": "販売促進サンプル"
        }
    ],
    "receipt_data": [
        {
            "module": "app.services.strategies.receipt_data.receipt_data_sample",
            "class": "ReceiptDataSample",
            "args": [],
            "kwargs": {},
            "description": "レシートデータカスタマイズサンプル"
        }
    ]
}
```

### プラグインマネージャーの実装

```python
# cart_strategy_manager.py
class CartStrategyManager:
    """
    プラグインを動的にロードして管理するクラス
    """
    
    def __init__(self):
        self.payment_strategies = {}
        self.sales_promotions = []
        self.receipt_data_strategies = []
        self._load_strategies()
    
    def _load_strategies(self):
        """plugins.jsonからプラグインをロード"""
        plugin_file = Path(__file__).parent / "strategies" / "plugins.json"
        
        with open(plugin_file, 'r', encoding='utf-8') as f:
            plugins = json.load(f)
        
        # 支払い戦略をロード
        for config in plugins.get("payment_strategies", []):
            self._load_payment_strategy(config)
        
        # 販売促進をロード
        for config in plugins.get("sales_promotions", []):
            self._load_sales_promotion(config)
    
    def _load_payment_strategy(self, config: dict):
        """支払い戦略を動的にロード"""
        try:
            # モジュールを動的インポート
            module = importlib.import_module(config["module"])
            # クラスを取得
            strategy_class = getattr(module, config["class"])
            # インスタンスを生成
            instance = strategy_class(*config.get("args", []), **config.get("kwargs", {}))
            
            # 各支払いコードに対して戦略を登録
            for payment_code in config.get("args", []):
                self.payment_strategies[payment_code] = instance
                
            logger.info(f"Loaded payment strategy: {config['class']}")
            
        except Exception as e:
            logger.error(f"Failed to load payment strategy: {config['class']}: {e}")
```

### プラグインインターフェース

```python
# abstract_payment.py
class AbstractPayment(ABC):
    """
    支払い戦略の抽象基底クラス
    すべての支払い方法はこのインターフェースを実装する
    """
    
    @abstractmethod
    async def pay(self, cart_doc, payment_code: str, amount: Decimal, detail: dict):
        """支払い処理を実行"""
        pass
    
    @abstractmethod
    async def refund(self, cart_doc, payment_index: int):
        """返金処理を実行"""
        pass
    
    @abstractmethod
    async def cancel(self, cart_doc, payment_index: int):
        """支払いキャンセル処理を実行"""
        pass
```

### プラグインの実装例

```python
# cash.py - 現金支払いプラグイン
class PaymentByCash(AbstractPayment):
    """
    現金支払いの実装
    お釣り計算などの現金特有の処理を含む
    """
    
    def __init__(self, *payment_codes):
        self.payment_codes = payment_codes
    
    async def pay(self, cart_doc, payment_code: str, amount: Decimal, detail: dict):
        # 支払い情報を作成
        payment = await self.create_cart_payment_async(
            cart_doc, payment_code, amount, detail
        )
        
        # 現金特有の処理：お釣り計算
        self.update_cart_change(cart_doc, payment)
        
        # カート残高を更新
        self.update_cart_balance(cart_doc, payment.amount)
        
        # 支払い情報を追加
        cart_doc.payments.append(payment)
        
        return cart_doc
    
    def update_cart_change(self, cart_doc, payment):
        """お釣りを計算して更新"""
        if payment.deposit_amount > payment.amount:
            cart_doc.change_amount += (payment.deposit_amount - payment.amount)
```

### プラグインの使用

```python
# cart_service.py
async def add_payment(self, cart_id: str, payment_data: dict):
    """支払いを追加"""
    # 支払い方法に対応する戦略を取得
    payment_strategy = self.strategy_manager.get_payment_strategy(
        payment_data["payment_code"]
    )
    
    if not payment_strategy:
        raise InvalidPaymentMethodException(
            f"Payment method {payment_data['payment_code']} not supported"
        )
    
    # 戦略を使用して支払い処理を実行
    cart_doc = await payment_strategy.pay(
        cart_doc,
        payment_data["payment_code"],
        payment_data["amount"],
        payment_data.get("detail", {})
    )
```

### メリット
- 新しい支払い方法や機能の追加が設定ファイルの編集で可能
- コア機能とプラグインの分離
- テストが容易（モックプラグインの作成）
- 顧客固有のカスタマイズが可能

## リポジトリパターン

### 概要
データアクセス層を抽象化し、ビジネスロジックとデータベース操作を分離するパターンです。

### 実装場所
- 共通: `/services/commons/src/kugel_common/models/repositories/abstract_repository.py`
- 各サービス: `*/app/models/repositories/`

### 抽象リポジトリの実装

```python
# abstract_repository.py
class AbstractRepository(ABC, Generic[Tdocument]):
    """
    汎用的なリポジトリの抽象基底クラス
    すべてのCRUD操作を定義
    """
    
    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str, 
                 document_class: Type[Tdocument]):
        self.database = database
        self.collection_name = collection_name
        self.document_class = document_class
        self.dbcollection = database[collection_name]
        self.session: Optional[AsyncIOMotorClientSession] = None
    
    async def create_async(self, document: Tdocument) -> bool:
        """ドキュメントを作成"""
        try:
            # タイムスタンプを設定
            document.created_at = get_app_time()
            document.updated_at = document.created_at
            
            # MongoDBに挿入
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
        """IDでドキュメントを検索"""
        document = await self.dbcollection.find_one(
            {"_id": id}, 
            session=self.session
        )
        
        if document:
            return self.document_class(**document)
        
        return None
    
    async def update_async(self, id: str, document: Tdocument) -> bool:
        """ドキュメントを更新"""
        # 更新タイムスタンプを設定
        document.updated_at = get_app_time()
        
        # 楽観的ロックのリトライロジック
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
        """ページネーション付き検索"""
        # 総件数を取得
        total_count = await self.dbcollection.count_documents(
            filter_dict, 
            session=self.session
        )
        
        # ページネーション計算
        skip = (page - 1) * size
        
        # クエリ実行
        cursor = self.dbcollection.find(
            filter_dict, 
            session=self.session
        ).skip(skip).limit(size)
        
        if sort:
            cursor = cursor.sort(sort)
        
        # 結果を変換
        documents = []
        async for doc in cursor:
            documents.append(self.document_class(**doc))
        
        return documents, total_count
    
    @asynccontextmanager
    async def transaction(self):
        """トランザクション管理"""
        async with await self.database.client.start_session() as session:
            async with session.start_transaction():
                self.session = session
                try:
                    yield self
                finally:
                    self.session = None
```

### 具体的なリポジトリの実装例

```python
# cart_repository.py
class CartRepository(AbstractRepository[CartDocument]):
    """
    カート専用のリポジトリ実装
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, "cart", CartDocument)
    
    async def find_active_cart_by_terminal_async(
        self, 
        terminal_id: str
    ) -> Optional[CartDocument]:
        """端末のアクティブなカートを検索"""
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
        """カートのステータスのみを更新（部分更新）"""
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
        """カートに商品を追加（配列への追加）"""
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

### リポジトリの使用例

```python
# cart_service.py
class CartService:
    def __init__(self, cart_repository: CartRepository):
        self.cart_repository = cart_repository
    
    async def create_new_cart(self, terminal_id: str) -> CartDocument:
        """新しいカートを作成"""
        # ビジネスロジック：カートの初期化
        cart = CartDocument(
            terminal_id=terminal_id,
            status=CartStatus.Initial.value,
            items=[],
            total_amount=Decimal("0"),
            created_by="system"
        )
        
        # リポジトリを使用してデータベースに保存
        success = await self.cart_repository.create_async(cart)
        
        if not success:
            raise CartCreationFailedException("Failed to create cart")
        
        return cart
    
    async def add_item_with_transaction(
        self, 
        cart_id: str, 
        item_data: dict
    ) -> CartDocument:
        """トランザクション内で商品を追加"""
        async with self.cart_repository.transaction():
            # カートを取得
            cart = await self.cart_repository.find_by_id_async(cart_id)
            
            if not cart:
                raise CartNotFoundException(f"Cart {cart_id} not found")
            
            # ビジネスロジック：商品の追加
            line_item = self._create_line_item(item_data)
            cart.items.append(line_item)
            cart.total_amount += line_item.amount
            
            # カートを更新
            success = await self.cart_repository.update_async(cart_id, cart)
            
            if not success:
                raise CartUpdateFailedException("Failed to update cart")
            
            return cart
```

### メリット
- データアクセスロジックの一元化
- ビジネスロジックとデータベース操作の分離
- テストが容易（モックリポジトリの作成）
- データベースの変更に対する影響を最小化
- トランザクション管理の簡素化

## サーキットブレーカーパターン

### 概要
外部サービスの障害が連鎖的に広がることを防ぐパターンです。一定回数失敗すると回路を開き、しばらくの間リクエストを遮断します。

### 実装場所
- **リトライ付きHTTPクライアント**: `/services/commons/src/kugel_common/utils/http_client_helper.py`
- **サーキットブレーカー付きDaprクライアント**: `/services/commons/src/kugel_common/utils/dapr_client_helper.py`
- **レガシー実装**: 
  - `/services/cart/app/utils/pubsub_manager.py` (DaprClientHelperに移行済み)
  - `/services/journal/app/utils/state_store_manager.py` (DaprClientHelperに移行済み)

### 実装詳細

#### リトライ付きHTTPクライアント

```python
# http_client_helper.py
class HttpClientHelper:
    """
    HTTP通信用の統一クライアント（リトライロジック内蔵）
    """
    
    def __init__(self, service_name: str, circuit_breaker_threshold: int = 3, 
                 circuit_breaker_timeout: int = 60):
        self.service_name = service_name
        self.base_url = self._get_service_url(service_name)
        
        # サーキットブレーカー設定
        self._circuit_open = False
        self._failure_count = 0
        self._failure_threshold = circuit_breaker_threshold
        self._last_failure_time = 0
        self._reset_timeout = circuit_breaker_timeout
        
        # HTTPクライアント設定
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )

    def _check_circuit_breaker(self) -> bool:
        """
        サーキットブレーカーの状態をチェック
        """
        if self._circuit_open:
            if (time.time() - self._last_failure_time) > self._reset_timeout:
                logger.info(f"Circuit breaker reset for {self.service_name}")
                self._circuit_open = False
                self._failure_count = 0
                return True
            return False
        return True

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        リトライとサーキットブレーカー付きHTTPリクエスト
        """
        if not self._check_circuit_breaker():
            raise HttpClientError(
                status_code=503,
                response_text=f"Circuit breaker open for {self.service_name}"
            )
        
        for attempt in range(3):  # 3回リトライ
            try:
                response = await self._client.request(method, endpoint, **kwargs)
                
                if response.status_code < 500:
                    self._handle_success()
                    return response
                
                # 5xxエラーはリトライ対象
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # エクスポネンシャルバックオフ
                    continue
                
                self._handle_failure()
                raise HttpClientError(response.status_code, response.text)
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                self._handle_failure()
                raise HttpClientError(503, str(e))
```

#### サーキットブレーカー付きDaprクライアント

```python
# dapr_client_helper.py
class DaprClientHelper:
    """
    Dapr通信用の統一クライアント（サーキットブレーカー内蔵）
    """
    
    def __init__(self, circuit_breaker_threshold: int = 3, 
                 circuit_breaker_timeout: int = 60):
        self.dapr_port = int(os.getenv("DAPR_HTTP_PORT", 3500))
        self.base_url = f"http://localhost:{self.dapr_port}"
        
        # HttpClientHelperを使用（サーキットブレーカーが含まれる）
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0)
        )
        
        # サーキットブレーカー設定を保持
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_timeout = circuit_breaker_timeout
        self._failure_counts = {}  # トピック/キーごとの失敗カウント
        self._circuit_states = {}  # トピック/キーごとのサーキット状態

    async def publish_event(self, pubsub_name: str, topic: str, data: dict) -> bool:
        """
        サーキットブレーカー付きでイベントを公開
        """
        circuit_key = f"pubsub_{pubsub_name}_{topic}"
        
        # サーキットブレーカーチェック
        if not self._check_circuit(circuit_key):
            logger.warning(f"Circuit breaker open for {circuit_key}")
            return False
        
        try:
            endpoint = f"/v1.0/publish/{pubsub_name}/{topic}"
            response = await self.client.post(endpoint, json=data)
            
            if response.status_code == 204:
                self._handle_success(circuit_key)
                return True
            else:
                self._handle_failure(circuit_key)
                return False
                
        except Exception as e:
            self._handle_failure(circuit_key)
            logger.error(f"Failed to publish event: {e}")
            return False
```

#### 既存のPubSubManagerの移行

```python
# pubsub_manager.py（新実装）
class PubSubManager:
    """
    DaprClientHelperを使用したPub/Sub管理
    """
    
    def __init__(self, pubsub_name: str = "pubsub-tranlog-report"):
        self.pubsub_name = pubsub_name
        self._dapr_client = DaprClientHelper(
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60
        )
    
    def _check_circuit_breaker(self) -> bool:
        """
        サーキットブレーカーの状態をチェック
        Returns:
            True: 回路が閉じている（正常）
            False: 回路が開いている（遮断中）
        """
        if self._circuit_open:
            current_time = time.time()
            # タイムアウト経過後は回路を閉じる
            if (current_time - self._last_failure_time) > self._reset_timeout:
                logger.info("Circuit breaker reset - closing circuit")
                self._circuit_open = False
                self._failure_count = 0
                return True
            return False
        return True
    
    def _handle_failure(self):
        """失敗を記録し、必要に応じて回路を開く"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self._failure_threshold:
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )
            self._circuit_open = True
    
    def _handle_success(self):
        """成功を記録し、失敗カウントをリセット"""
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
        イベントを非同期で公開
        
        Returns:
            Tuple[bool, Optional[str]]: (成功/失敗, エラーメッセージ)
        """
        # サーキットブレーカーチェック
        if not self._check_circuit_breaker():
            logger.warning(f"Circuit breaker is open - rejecting publish to {topic}")
            return False, "Circuit breaker is open"
        
        try:
            # Dapr Pub/Sub APIを呼び出し
            url = f"{self.base_url}/v1.0/publish/{self.pubsub_name}/{topic}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=event_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 204:
                    # 成功
                    self._handle_success()
                    logger.info(f"Successfully published event to {topic}")
                    return True, None
                else:
                    # 失敗
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

### 使用例

```python
# cart_service_event.py
class CartServiceEvent:
    """
    カートサービスのイベント処理
    """
    
    def __init__(self):
        self.pubsub_manager = PubSubManager()
    
    async def publish_transaction_completed(
        self, 
        transaction_data: dict
    ) -> bool:
        """
        取引完了イベントを公開
        サーキットブレーカーにより保護される
        """
        # イベントデータを準備
        event_data = {
            "event_type": "transaction_completed",
            "transaction_id": transaction_data["id"],
            "timestamp": datetime.utcnow().isoformat(),
            "data": transaction_data
        }
        
        # Pub/Subマネージャーを使用して公開
        success, error = await self.pubsub_manager.publish_event_async(
            topic="tranlog_report",
            event_data=event_data
        )
        
        if not success:
            # エラーハンドリング（ただし例外は投げない）
            logger.warning(
                f"Failed to publish transaction event: {error}. "
                f"Transaction {transaction_data['id']} will continue without event."
            )
            # 監視システムに通知
            await self._notify_monitoring_system(transaction_data["id"], error)
        
        return success
    
    async def _notify_monitoring_system(
        self, 
        transaction_id: str, 
        error: str
    ):
        """監視システムにエラーを通知"""
        # Slack通知やメトリクス記録など
        pass
```

### サーキットブレーカーの状態遷移

```
┌────────┐  失敗が閾値未満   ┌────────┐  失敗が閾値以上  ┌────────┐
│ Closed │ ←───────────── │  Half  │ ───────────→ │  Open  │
│ (正常) │                │  Open  │                │ (遮断) │
└────────┘                └────────┘                └────────┘
    ↑                                                     │
    └─────────────── タイムアウト経過 ─────────────────┘
```

### メリット
- カスケード障害の防止
- システムの復旧時間の短縮
- 無駄なリトライの削減
- 障害の早期検知

## ストラテジーパターン

### 概要
アルゴリズムをカプセル化し、実行時に切り替え可能にするパターンです。支払い処理と税計算で使用されています。

### 実装場所
- 支払い戦略: `/services/cart/app/services/strategies/payments/`
- 税計算: `/services/cart/app/services/logics/calc_tax_logic.py`

### 支払い戦略の実装

#### 抽象戦略

```python
# abstract_payment.py
class AbstractPayment(ABC):
    """
    支払い戦略の抽象基底クラス
    """
    
    @abstractmethod
    async def pay(
        self, 
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartDocument:
        """支払い処理を実行"""
        pass
    
    @abstractmethod
    async def refund(
        self, 
        cart_doc: CartDocument,
        payment_index: int
    ) -> CartDocument:
        """返金処理を実行"""
        pass
    
    async def create_cart_payment_async(
        self,
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartPayment:
        """支払い情報を作成する共通メソッド"""
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
        """カート残高を更新する共通メソッド"""
        cart_doc.payment_total += amount
        cart_doc.balance = cart_doc.total_amount - cart_doc.payment_total
```

#### 具体的な戦略実装

```python
# cash.py - 現金支払い戦略
class PaymentByCash(AbstractPayment):
    """
    現金支払いの実装
    特徴：お釣り計算が必要
    """
    
    async def pay(
        self, 
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartDocument:
        # 支払い情報を作成
        payment = await self.create_cart_payment_async(
            cart_doc, payment_code, amount, detail
        )
        
        # 現金特有の処理：お釣り計算
        self.update_cart_change(cart_doc, payment)
        
        # 共通処理：残高更新
        self.update_cart_balance(cart_doc, payment.amount)
        
        # 支払い情報を追加
        cart_doc.payments.append(payment)
        
        return cart_doc
    
    def update_cart_change(
        self, 
        cart_doc: CartDocument, 
        payment: CartPayment
    ):
        """お釣りを計算"""
        # 預かり金額が支払い金額より多い場合
        if payment.deposit_amount > payment.amount:
            change = payment.deposit_amount - payment.amount
            cart_doc.change_amount += change
            logger.info(f"Change calculated: {change}")
    
    async def refund(
        self, 
        cart_doc: CartDocument,
        payment_index: int
    ) -> CartDocument:
        """現金の返金処理"""
        if payment_index >= len(cart_doc.payments):
            raise InvalidPaymentIndexException()
        
        payment = cart_doc.payments[payment_index]
        
        # 返金マークを付ける
        payment.is_refunded = True
        payment.refund_amount = payment.amount
        
        # 残高を調整
        cart_doc.payment_total -= payment.amount
        cart_doc.balance = cart_doc.total_amount - cart_doc.payment_total
        
        # お釣りも調整
        if cart_doc.change_amount > 0:
            cart_doc.change_amount = max(0, cart_doc.change_amount - payment.amount)
        
        return cart_doc

# cashless.py - キャッシュレス支払い戦略
class PaymentByCashless(AbstractPayment):
    """
    キャッシュレス支払いの実装
    特徴：過払いチェック、お釣りなし
    """
    
    async def pay(
        self, 
        cart_doc: CartDocument,
        payment_code: str,
        amount: Decimal,
        detail: dict
    ) -> CartDocument:
        # 支払い情報を作成
        payment = await self.create_cart_payment_async(
            cart_doc, payment_code, amount, detail
        )
        
        # キャッシュレス特有の処理：過払いチェック
        self.check_deposit_over(cart_doc, payment.deposit_amount)
        
        # 共通処理：残高更新
        self.update_cart_balance(cart_doc, payment.amount)
        
        # 支払い情報を追加
        cart_doc.payments.append(payment)
        
        return cart_doc
    
    def check_deposit_over(
        self, 
        cart_doc: CartDocument, 
        deposit_amount: Decimal
    ):
        """キャッシュレスでは過払いを許可しない"""
        remaining_balance = cart_doc.total_amount - cart_doc.payment_total
        
        if deposit_amount > remaining_balance:
            raise OverPaymentException(
                f"Cashless payment cannot exceed balance. "
                f"Balance: {remaining_balance}, Deposit: {deposit_amount}"
            )
```

### 税計算戦略の実装

```python
# calc_tax_logic.py
class CalcTaxLogic:
    """
    税計算ロジック（ストラテジーパターンを内部で使用）
    """
    
    def calculate_tax(
        self,
        amount: Decimal,
        tax_rate: Decimal,
        tax_type: TaxType,
        rounding_method: RoundingMethod = RoundingMethod.ROUND_DOWN
    ) -> TaxCalculationResult:
        """
        税タイプに応じて適切な計算戦略を選択
        """
        if tax_type == TaxType.EXCLUSIVE:
            # 外税計算戦略
            return self._calculate_exclusive_tax(
                amount, tax_rate, rounding_method
            )
        elif tax_type == TaxType.INCLUSIVE:
            # 内税計算戦略
            return self._calculate_inclusive_tax(
                amount, tax_rate, rounding_method
            )
        elif tax_type == TaxType.EXEMPT:
            # 非課税戦略
            return self._calculate_exempt_tax(amount)
        else:
            raise InvalidTaxTypeException(f"Unknown tax type: {tax_type}")
    
    def _calculate_exclusive_tax(
        self,
        amount: Decimal,
        tax_rate: Decimal,
        rounding_method: RoundingMethod
    ) -> TaxCalculationResult:
        """外税計算：税額を価格に加算"""
        tax_amount = amount * tax_rate / 100
        
        # 端数処理
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
        """内税計算：税額が価格に含まれている"""
        # 税抜き価格を計算
        subtotal = amount / (1 + tax_rate / 100)
        subtotal = self._apply_rounding(subtotal, rounding_method)
        
        # 税額を逆算
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
        """非課税：税額なし"""
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
        """端数処理戦略"""
        if method == RoundingMethod.ROUND_DOWN:
            return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
        elif method == RoundingMethod.ROUND_UP:
            return value.quantize(Decimal("1"), rounding=ROUND_UP)
        elif method == RoundingMethod.ROUND_HALF_UP:
            return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        else:
            return value
```

### 戦略の選択と使用

```python
# cart_service.py
class CartService:
    """
    カートサービス（戦略を使用）
    """
    
    def __init__(self):
        self.strategy_manager = CartStrategyManager()
        self.tax_calculator = CalcTaxLogic()
    
    async def process_payment(
        self,
        cart_id: str,
        payment_request: PaymentRequest
    ) -> CartDocument:
        """支払い処理（適切な戦略を選択して実行）"""
        # カートを取得
        cart = await self.cart_repository.find_by_id_async(cart_id)
        
        # 支払い方法に対応する戦略を取得
        payment_strategy = self.strategy_manager.get_payment_strategy(
            payment_request.payment_code
        )
        
        if not payment_strategy:
            raise UnsupportedPaymentMethodException(
                f"Payment method {payment_request.payment_code} not supported"
            )
        
        # 戦略を実行
        cart = await payment_strategy.pay(
            cart,
            payment_request.payment_code,
            payment_request.amount,
            payment_request.detail
        )
        
        # カートを保存
        await self.cart_repository.update_async(cart_id, cart)
        
        return cart
    
    def calculate_item_tax(
        self,
        item: LineItem,
        tax_master: TaxMaster
    ) -> LineItem:
        """商品の税計算（税計算戦略を使用）"""
        # 税計算戦略を実行
        tax_result = self.tax_calculator.calculate_tax(
            amount=item.price * item.quantity,
            tax_rate=tax_master.rate,
            tax_type=tax_master.tax_type,
            rounding_method=tax_master.rounding_method
        )
        
        # 結果を商品に反映
        item.tax_amount = tax_result.tax_amount
        item.total_amount = tax_result.total
        item.tax_rate = tax_result.tax_rate
        
        return item
```

### メリット
- アルゴリズムの切り替えが容易
- 新しい戦略の追加が既存コードに影響しない
- 各戦略のテストが独立して行える
- 条件分岐の削減

## その他のパターン

### ファクトリーパターン

プラグインマネージャーがファクトリーとして機能：

```python
# cart_strategy_manager.py
class CartStrategyManager:
    """
    戦略オブジェクトのファクトリー
    """
    
    def get_payment_strategy(self, payment_code: str) -> Optional[AbstractPayment]:
        """支払いコードに基づいて適切な戦略を返す"""
        return self.payment_strategies.get(payment_code)
    
    def create_sales_promotion(self, promo_type: str) -> Optional[AbstractSalesPromo]:
        """プロモーションタイプに基づいてインスタンスを生成"""
        for promo in self.sales_promotions:
            if promo.promo_type == promo_type:
                return promo
        return None
```

### テンプレートメソッドパターン

抽象基底クラスで処理の流れを定義：

```python
# abstract_state.py
class AbstractState(ABC):
    """
    状態の抽象基底クラス（テンプレートメソッド）
    """
    
    def process_event(self, event: str, context: dict) -> dict:
        """イベント処理のテンプレートメソッド"""
        # 1. イベントが許可されているかチェック
        if not self.check_event_sequence(event):
            raise EventNotAllowedException()
        
        # 2. 前処理
        self.pre_process(event, context)
        
        # 3. メイン処理（サブクラスで実装）
        result = self.execute_event(event, context)
        
        # 4. 後処理
        self.post_process(event, context, result)
        
        return result
    
    @abstractmethod
    def check_event_sequence(self, event: str) -> bool:
        """許可されたイベントかチェック（サブクラスで実装）"""
        pass
    
    @abstractmethod
    def execute_event(self, event: str, context: dict) -> dict:
        """イベントを実行（サブクラスで実装）"""
        pass
    
    def pre_process(self, event: str, context: dict):
        """前処理（オプション）"""
        logger.info(f"Processing event: {event}")
    
    def post_process(self, event: str, context: dict, result: dict):
        """後処理（オプション）"""
        logger.info(f"Event processed: {event}")
```

### シングルトンパターン

状態管理マネージャーの実装：

```python
# state_store_manager.py
class StateStoreManager:
    """
    シングルトンパターンを使用した状態管理
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
        """状態を取得"""
        # シングルトンなので、アプリケーション全体で同じインスタンスを使用
        pass
```

## まとめ

Kugel POSシステムでは、これらのデザインパターンを組み合わせることで：

1. **保守性**: 各コンポーネントの責任が明確で、変更の影響範囲が限定的
2. **拡張性**: 新機能の追加が既存コードへの影響を最小限に抑えられる
3. **テスタビリティ**: 各パターンが独立しているため、単体テストが容易
4. **柔軟性**: ビジネス要件の変化に素早く対応可能

これらのパターンは、実際のビジネス要件（多様な支払い方法、複雑な税制、カスタマイズ可能なレポートなど）に対応するために選択され、実装されています。