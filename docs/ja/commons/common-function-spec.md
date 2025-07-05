# Kugel Commons 共通機能仕様書

## 概要

Kugel Commons（`kugel_common`）は、Kugelpos POSシステムのマイクロサービス群で共通して使用される機能を提供するライブラリです。データベース抽象化、認証、例外処理、HTTP通信、設定管理などの横断的関心事を統一的に扱います。

**バージョン**: 0.1.9  
**アーキテクチャ**: マイクロサービス基盤  
**言語サポート**: 日本語・英語対応（日本語がデフォルト）

## モジュール構成

### 主要モジュール

```
kugel_common/
├── config/          # 設定管理
├── database/        # MongoDB抽象化
├── models/          # データモデル・リポジトリパターン
├── schemas/         # API スキーマ
├── exceptions/      # 例外処理
├── utils/           # ユーティリティ
├── middleware/      # ミドルウェア
├── security.py      # 認証・認可
├── enums.py         # 列挙型定義
└── status_codes.py  # HTTPステータスコード
```

## 1. 設定管理（config/）

### 統合設定アーキテクチャ

`settings.py`で以下の設定クラスを統合管理：

#### AppSettings
- **アプリケーション共通設定**
  - 端数処理方法（税計算用）
  - レシート番号生成方式
  - Slack統合設定

#### DatetimeSettings
- **日時設定**
  - タイムゾーン管理
  - 日時フォーマット標準化

#### TaxSettings
- **税計算設定**
  - 税率設定
  - 税計算ルール
  - 端数処理方法

#### AuthSettings
- **認証設定**
  - JWT設定（秘密鍵、アルゴリズム、有効期限）
  - 認証サーバー設定

#### StampDutySettings
- **印紙税設定**
  - 印紙税マスタデータ（日本の税法に基づく）
  - 金額閾値と印紙税額の対応表
  - 14段階の印紙税区分（5万円以上～10億円以上）

#### WebServiceSettings
- **サービス間通信設定**
  - 各サービスのベースURL
  - サービス発見設定

#### DBSettings
- **MongoDB接続設定**
  - 接続文字列
  - 接続プール設定（最大100、最小10接続）
  - タイムアウト設定

#### DBCollectionCommonSettings
- **標準コレクション名**
  - 共通コレクション名の統一

### 設定の特徴

- **環境変数サポート**: `.env`ファイルとの連携
- **接続プール**: 効率的なデータベース接続管理
- **タイムアウト設定**: データベース操作の応答時間制御
- **サービス発見**: BASE_URLパターンによる自動URL解決

## 2. データベース抽象化（database/）

### MongoDB非同期操作 (`database.py`)

```python
# 主要機能
- シングルトンクライアント管理
- 自動リトライ機能（指数バックオフ）
- 接続プール管理
- データベース・コレクション操作
- インデックス自動作成
```

#### 実装の特徴

- **接続管理**: シングルトンパターンで接続を統一管理
- **エラーハンドリング**: 指数バックオフによる自動リトライ
- **接続プール**: 設定可能なプールサイズとアイドルタイムアウト
- **トランザクション**: MongoDB トランザクション完全サポート

### リポジトリパターン (`abstract_repository.py`)

```python
class AbstractRepository(Generic[T]):
    """型安全なCRUD操作を提供する汎用リポジトリ"""
    
    async def find_by_id_async(self, id: str) -> Optional[T]
    async def find_by_filter_async(self, filter_dict: dict) -> List[T]
    async def create_async(self, entity: T) -> T
    async def update_async(self, entity: T) -> T
    async def delete_async(self, id: str) -> bool
    async def paginate_async(self, page: int, limit: int, **kwargs) -> PaginatedResult[T]
```

#### 主要機能

- **型安全性**: Python Genericsによる型安全なCRUD操作
- **トランザクション**: マルチドキュメントトランザクション対応
- **ページネーション**: 組み込みページネーション機能
- **リトライ機能**: WriteConflict（MongoDB コード112）の自動リトライ
- **一括操作**: 集約パイプラインサポート

### ドキュメントモデル

#### BaseDocumentModel
```python
class BaseDocumentModel(BaseModel):
    """全てのドキュメントの基底クラス（Pydantic）"""
    
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
    """共通フィールドを持つドキュメント基底クラス"""
    
    shard_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    etag: Optional[str] = None
```

#### 特化ドキュメント
- **TerminalInfoDocument**: 端末情報
- **StaffMasterDocument**: スタッフマスタ
- **StoreInfoDocument**: 店舗情報
- **UserInfoDocument**: ユーザー情報

## 3. 例外処理（exceptions/）

### 階層的例外構造

```
AppException (基底例外)
├── DatabaseException (データベース層)
├── RepositoryException (データアクセス層)
└── ServiceException (ビジネスロジック層)
```

### エラーコード体系（XXYYZZ形式）

- **XX**: エラーカテゴリ
  - 10: 一般エラー
  - 20: 認証エラー
  - 30: バリデーションエラー
  - 40: ビジネスロジックエラー
  - 50: データベースエラー
  - 60: 外部サービスエラー
  - 90: システムエラー

- **YY**: サブカテゴリ（サービス固有の範囲割当）
- **ZZ**: 具体的なエラーコード

### 実装例

```python
class ValidationException(AppException):
    """バリデーションエラー"""
    error_code = 30001
    
    def __init__(self, message: str, user_message: str = None, details: dict = None):
        super().__init__(message, user_message, details)
        self.status_code = 400
```

### 機能の特徴

- **多言語対応**: 日本語・英語のエラーメッセージ
- **構造化ログ**: 一貫したエラーログ記録
- **ユーザーフレンドリー**: システムエラーとユーザーエラーの分離
- **HTTP統合**: HTTPステータスコードの自動マッピング

## 4. APIとスキーマ管理（schemas/）

### 標準化APIレスポンス (`api_response.py`)

```python
class ApiResponse(BaseModel, Generic[T]):
    """統一APIレスポンス形式"""
    
    success: bool
    code: int                    # HTTPステータスコード
    message: str                 # システムメッセージ
    user_error: Optional[UserError] = None  # ユーザー向けエラー
    data: Optional[T] = None     # 汎用ペイロード
    metadata: Optional[Metadata] = None     # ページネーション情報
    operation: Optional[str] = None         # 操作トラッキング
```

### ページネーション対応

```python
class PaginatedResult(BaseModel, Generic[T]):
    """汎用ページネーションレスポンス"""
    
    data: List[T]      # items ではなく data
    page: int
    limit: int
    total_pages: int   # has_next/has_prev ではなく total_pages
    total_items: int   # 総アイテム数
```

### フィールド命名規則

- **データベース**: snake_case（MongoDB直接操作）
- **API**: camelCase（`to_lower_camel()`ユーティリティ使用）

## 5. セキュリティ機能（security.py）

### 二重認証システム

#### 1. OAuth2/JWT認証
```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """JWT トークンによるユーザー認証"""
    
    # JWT検証（jose ライブラリ使用）
    # テナント分離
    # サービスアカウント対応
    # スーパーユーザー権限チェック
    # 戻り値は辞書形式（user_id, username, tenant_id等を含む）
```

#### 2. APIキー認証
```python
async def get_current_terminal_from_api_key(
    api_key: str = Header(..., alias="X-API-KEY"),
    terminal_id: str = Query(...)
) -> TerminalInfoDocument:
    """端末APIキーによる認証"""
    
    # 端末ID形式: {tenant_id}-{store_code}-{terminal_no}
    # APIキー検証
    # サービス間端末情報取得
    # 戻り値はTerminalInfoDocument型
```

### マルチテナントセキュリティ

- **テナント分離**: データベースレベルでのtenant_id分離
- **端末ID形式**: `{tenant_id}-{store_code}-{terminal_no}`統一フォーマット
- **セキュリティ依存**: FastAPI依存注入による認証
- **Pub/Sub認証**: 通知コールバック用の特別な認証処理

### 追加のセキュリティ関数

#### get_service_account_info
```python
def get_service_account_info() -> dict:
    """サービスアカウント情報の取得"""
    
    # サービス名とテナントIDを含む辞書を返す
    # JWTトークン生成用のサービスアカウント情報
```

## 6. 通信ユーティリティ（utils/）

### HTTPクライアントヘルパー (`http_client_helper.py`)

```python
class HttpClientHelper:
    """非同期HTTPクライアント（httpx基盤）"""
    
    # 接続プール管理
    # 設定可能なリトライ機能
    # サービス発見機能
    # 非同期コンテキスト管理
    # クライアントプール共有
```

#### 主要機能

- **非同期HTTP**: httpxライブラリベースの高性能HTTP通信
- **リトライロジック**: 設定可能なリトライ回数とバックオフ
- **サービス発見**: マイクロサービス用自動URL解決
- **コンテキスト管理**: 適切なリソースクリーンアップ
- **クライアントプール**: パフォーマンス向上のための共有インスタンス

### Dapr統合 (`dapr_client_helper.py`)

```python
class DaprClientHelper:
    """統一Daprクライアント（Pub/Sub・State Store）"""
    
    # サーキットブレーカー機能
    # 自動リトライ機能
    # 状態管理操作
    # イベント発行機能
```

#### サーキットブレーカー実装

- **状態遷移**: Closed → Open → Half-Open パターン
- **閾値設定**: 設定可能な失敗回数（デフォルト: 3回）
- **回復機能**: タイムアウト後の自動回復（デフォルト: 60秒）
- **ログ出力**: 包括的な状態遷移ログ

## 7. ミドルウェア・ログ（middleware/）

### リクエストログミドルウェア (`log_requests.py`)

```python
class RequestLogMiddleware:
    """包括的リクエスト・レスポンスログ"""
    
    # リクエスト/レスポンス詳細、タイミング、認証情報
    # 二重保存（ファイルログ + データベース）
    # マルチデータベース（共通DB + テナント別DB）
    # コンテキスト取得（ユーザー、端末、スタッフ、クライアント）
    # WebSocket対応（ログバイパス）
```

#### 機能詳細

- **処理時間**: ミリ秒精度のタイミング計測
- **ボディ取得**: リクエスト・レスポンスボディのログ記録
- **エラーハンドリング**: ログ記録失敗の優雅な処理
- **プライバシー**: 機密情報のサニタイズ処理

## 8. ビジネスロジック支援

### トランザクション種別 (`enums.py`)

```python
class TransactionType(Enum):
    """トランザクション種別"""
    
    # 販売操作（文字列値）
    NORMAL_SALE = "101"      # 通常販売
    RETURN_SALE = "102"      # 返品
    VOID_SALE = "201"        # 販売取消
    VOID_RETURN = "202"      # 返品取消
    
    # 端末操作
    TERMINAL_OPEN = "301"    # 開店
    TERMINAL_CLOSE = "302"   # 閉店
    
    # 現金操作
    CASH_IN = "401"          # 現金入金
    CASH_OUT = "402"         # 現金出金
    
    # レポート
    FLASH_REPORT = "501"     # 中間報告
    DAILY_REPORT = "502"     # 日次報告
```

### 税計算・端数処理

```python
class TaxType(Enum):
    """税種別"""
    EXTERNAL = "EXTERNAL"  # 外税（加算）
    INTERNAL = "INTERNAL"  # 内税（含む）
    EXEMPT = "EXEMPT"      # 非課税

class RoundMethod(Enum):
    """端数処理方法（RoundingMethodではなくRoundMethod）"""
    ROUND = "ROUND"  # 四捨五入
    FLOOR = "FLOOR"  # 切り捨て
    CEIL = "CEIL"   # 切り上げ
```

### 時刻管理 (`misc.py`)

```python
def get_current_time() -> datetime:
    """アプリケーション統一時刻取得"""
    return datetime.now(get_timezone())

def to_iso_string(dt: datetime) -> str:
    """ISO形式タイムスタンプ生成"""
    return dt.isoformat()
```

## 9. レシート機能（receipt/）

### 抽象レシートデータ (`abstract_receipt_data.py`)

```python
class AbstractReceiptData(ABC):
    """レシートデータの抽象基底クラス"""
    
    @abstractmethod
    def make_receipt_data(self) -> ReceiptData:
        """レシートデータ生成（メインメソッド）"""
        pass
    
    @abstractmethod
    def make_receipt_header(self) -> str:
        """レシートヘッダー生成"""
        pass
    
    @abstractmethod
    def make_receipt_body(self) -> str:
        """レシートボディ生成"""
        pass
    
    @abstractmethod
    def make_receipt_footer(self) -> str:
        """レシートフッター生成"""
        pass
```

### レシートデータモデル (`receipt_data_model.py`)

```python
class ReceiptData(BaseModel):
    """レシートデータクラス（ReceiptDataModel ではなく ReceiptData）"""
    
    tenant_id: str
    terminal_id: str
    business_date: str
    generate_date_time: str
    tranlog_id: str
    receipt_text: str
    journal_text: str
```

## 10. 追加の機能

### verify_pubsub_notification_auth
```python
async def verify_pubsub_notification_auth(
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> dict:
    """Pub/Sub通知コールバックの認証検証"""
    
    # JWTトークンまたはPUBSUB_NOTIFY_API_KEYを受け入れる
    # 戻り値: {"auth_type": "jwt"|"api_key", "service": str, "tenant_id": str}
```

### get_tenant_id_with_security
```python
async def get_tenant_id_with_security(
    terminal_id: str = Path(...),
    api_key: Optional[str] = Security(api_key_header), 
    token: Optional[str] = Depends(oauth2_scheme),
    is_terminal_service: Optional[bool] = False
) -> str:
    """パスパラメータからterminal_idを使用してテナントID取得"""
```

### get_terminal_info_with_api_key
```python
async def get_terminal_info_with_api_key(
    terminal_id: str = Query(...),
    api_key: str = Security(api_key_header),
    is_terminal_service: Optional[bool] = False
) -> TerminalInfoDocument:
    """APIキー認証で完全な端末情報を取得"""
```

## まとめ

Kugel Commonsライブラリは、マイクロサービスアーキテクチャの強固な基盤を提供します：

### 主要価値

- **一貫したデータアクセス**: 非同期MongoDBリポジトリパターン（`_async`サフィックス付きメソッド）
- **包括的エラーハンドリング**: 多言語対応の構造化例外処理（`details`パラメータ付き）
- **セキュアな通信**: テナント分離による二重認証（辞書型の戻り値）
- **耐障害性アーキテクチャ**: サーキットブレーカーとリトライ機構
- **標準化API**: 一貫したレスポンス形式とページネーション（`data`フィールド使用）
- **包括的ログ**: コンテキスト付きリクエスト・レスポンス監査
- **設定管理**: 環境ベースの設定と合理的なデフォルト値（印紙税設定含む）

このライブラリは、サービス固有の要件に対する柔軟性を保持しながら、共通の関心事を効果的に抽象化し、POSマイクロサービスエコシステムの優れた基盤となっています。

## 使用例

### 1. リポジトリパターンの使用

```python
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from motor.motor_asyncio import AsyncIOMotorDatabase

class ItemStoreMasterRepository(AbstractRepository[ItemStoreMasterDocument]):
    """店舗別商品マスタのリポジトリ実装例"""
    
    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str, store_code: str):
        # AbstractRepositoryのコンストラクタにコレクション名、ドキュメントクラス、DBインスタンスを渡す
        super().__init__("item_store_master", ItemStoreMasterDocument, db)
        self.tenant_id = tenant_id
        self.store_code = store_code
    
    async def get_item_store_by_code(self, item_code: str) -> ItemStoreMasterDocument:
        """商品コードで店舗別商品情報を取得"""
        filter = {
            "tenant_id": self.tenant_id, 
            "store_code": self.store_code, 
            "item_code": item_code
        }
        # AbstractRepositoryのget_one_asyncメソッドを使用
        return await self.get_one_async(filter)
    
    async def create_item_store_async(self, item_store_doc: ItemStoreMasterDocument) -> ItemStoreMasterDocument:
        """新規店舗別商品を作成"""
        item_store_doc.tenant_id = self.tenant_id
        item_store_doc.store_code = self.store_code
        # AbstractRepositoryのcreate_asyncメソッドを使用
        success = await self.create_async(item_store_doc)
        if success:
            return item_store_doc
        else:
            raise Exception("Failed to create item store")

```

### 2. 認証の使用

```python
from kugel_common.security import get_current_user
from fastapi import Depends

@app.get("/api/v1/protected")
async def protected_endpoint(current_user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {current_user.get('username')}"}
```

### 3. エラーハンドリング

```python
from kugel_common.exceptions import InvalidRequestDataException
import logging

logger = logging.getLogger(__name__)

def validate_item_code(item_code: str):
    if not item_code or len(item_code) < 3:
        # InvalidRequestDataExceptionは3つの引数を受け取る
        raise InvalidRequestDataException(
            "Item code must be at least 3 characters",  # システムメッセージ
            logger=logger,  # ロガー（オプション）
            original_exception=None  # 元の例外（オプション）
        )
        
# または、サービス層での一般的なエラー処理
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

### 4. HTTP通信

```python
from kugel_common.utils.http_client_helper import HttpClientHelper

async def call_other_service():
    # HttpClientHelperはシングルトンパターンで実装されている
    client = HttpClientHelper()
    
    # getメソッドはurlとservice_nameを別々に受け取る
    response = await client.get(
        url="/api/v1/data",
        service_name="cart",  # サービス名を指定してベースURLを解決
        timeout=30.0  # タイムアウト（オプション）
    )
    return response.json()
```

### 5. Dapr統合

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