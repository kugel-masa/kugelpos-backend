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
class AbstractRepository(ABC, Generic[Tdocument]):
    """型安全なCRUD操作を提供する汎用リポジトリ"""

    def __init__(self, collection_name: str, document_class: Type[Tdocument], db: AsyncIOMotorDatabase)

    # トランザクション管理
    async def start_transaction(self) -> AsyncIOMotorClientSession
    async def commit_transaction(self)
    async def abort_transaction(self)
    def set_session(self, session: AsyncIOMotorClientSession)

    # CRUD操作
    async def create_async(self, document: Tdocument) -> bool
    async def get_one_async(self, filter: dict) -> Tdocument
    async def get_all_async(self, max: int = 0) -> list[Tdocument]
    async def get_list_async(self, filter: dict, max: int = 0) -> list[Tdocument]
    async def get_list_async_with_sort_and_paging(
        self, filter: dict, limit: int = 0, page: int = 1, sort: list[tuple[str, int]] = None
    ) -> list[Tdocument]
    async def get_paginated_list_async(
        self, filter: dict, limit: int = 0, page: int = 1, sort: list[tuple[str, int]] = None
    ) -> PaginatedResult[Tdocument]
    async def replace_one_async(self, filter: dict, document: Tdocument) -> bool
    async def update_one_async(self, filter: dict, new_values: dict, max_retries: int = 3, retry_interval: float = 0.1) -> bool
    async def delete_async(self, search_dict: dict) -> bool

    # 集約操作
    async def execute_pipeline(self, pipeline: list[dict]) -> list[dict]

    # ユーティリティ
    def make_shard_key(self, keys: list[str]) -> str
```

#### 主要機能

- **型安全性**: Python Genericsによる型安全なCRUD操作（Tdocumentは型パラメータ）
- **トランザクション**: マルチドキュメントトランザクション対応（start/commit/abort）
- **ページネーション**: 組み込みページネーション機能（get_paginated_list_async）
- **リトライ機能**: WriteConflict（MongoDB コード112）の自動リトライ（update_one_async）
- **集約パイプライン**: execute_pipelineによる集約クエリ実行
- **セッション共有**: 複数リポジトリでセッションを共有してクロスコレクショントランザクション対応

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
async def get_terminal_info(
    terminal_id: str = Path(...),
    api_key: str = Security(api_key_header)
) -> TerminalInfoDocument:
    """端末APIキーによる認証（Pathパラメータ版）"""

    # 端末ID形式: {tenant_id}-{store_code}-{terminal_no}
    # APIキー検証
    # サービス間端末情報取得
    # 戻り値はTerminalInfoDocument型

async def get_terminal_info_with_api_key(
    terminal_id: str = Query(...),
    api_key: str = Security(api_key_header)
) -> TerminalInfoDocument:
    """端末APIキーによる認証（Queryパラメータ版）"""
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

#### 資格情報のマスク (issue #211)

ボディは 2 つの出力先に届く。`request_log` コレクションと、フィルタを一切
挟まない DEBUG 行を通じた `app.log` である。しかも FastAPI が検証する
**前**に記録されるため、422 で拒否されたリクエストも同じように全文が残る。
`POST /register` が受け取る `password` は平文で、ハッシュ化されるのはその
後であり、スタッフマスタの `pin` はリクエストにもレスポンスにも平文で載る。
マスクがなければ、どちらも監査コレクションに残ることになる。

`mask_sensitive_data`（`utils/log_utils.py`）はボディをパースする箇所で
適用する。ここ 1 箇所で両方の出力先を覆える。文書やヘッダ一式をログに出す
他の呼び出し側にも個別に適用する。`security.py`（端末文書は自身の `api_key`
と、配下スタッフの平文 `pin` を持つ）、`http_client_helper.py`、および
ヘッダを自前で組み立ててクライアントに渡す前にログへ出す web リポジトリ
（`staff_master_web_repository.py`、report の `terminal_info_web_repository.py`
と `category_master_web_repository.py`）である。共通クライアントだけを
マスクしても後者は覆えない。規則は 3 つ。

1. **秘密フィールド名** — `pin`、`password`、`token`、`secret`、`cardNo`、
   `pan`、`authorization`、`dapr-api-token` など — は大文字小文字と区切り
   文字を無視して照合するため、`pin_code`・`pinCode`・`PIN_CODE` は同一の
   名前として扱う。ボディは lowerCamelCase、スキーマは snake_case なので、
   両方の綴りが実際に現れる。
2. **`apiKey` は両端を残す**（`abcd...5678`）。`mask_dict_api_key` が既に
   確立した、調査用の形式に合わせる。
3. **資格情報コンテナ**（`credentials` / `credential`）配下は、キー名に
   関わらずすべての値をマスクする。任意の文字列キーを受け付けるスキーマ
   では `cardN0` のような綴りで秘密を運べてしまい、名前による規則では
   捕まえられないため。

キーは常に残し、値だけを置き換えるので、何が送られてきたかはログに残る。
`None` は `None` のまま保つ。「PIN が送られなかった」と「PIN が送られた」の
区別は、どちらの値も明かさずに保てる。同じマスクを検証エラーの詳細にも
適用する。そうしないと、拒否した値が ERROR ログと 422 レスポンスの双方に
そのまま反射される。

`mask_loggable` は、パース済み JSON ではない値 — 全フィールドを表示する
pydantic 文書など — に対して同じマスクを行う。文書やレスポンスモデルを
丸ごとログ行や例外メッセージに載せる箇所ではこちらを使う。例外を投げない。
リクエストの結果に口を出してはいけない経路で動くためである。

その経路のひとつはログより遠くまで届く。`CannotCreateException` は渡された
文書をメッセージに埋め込み、例外ハンドラは `str(exc)` を 400 レスポンスの
`data` として呼び出し元に返す。つまりスタッフの作成に失敗すると平文の `pin`
が、端末の作成に失敗すると発行したばかりの `api_key` が、そのまま相手に
戻ってしまう。マスクは各 `raise` ではなく例外クラス側に置いた。呼び出し箇所
は全サービスで20を超えるためである。

ログ行のマスクは最後の手段であって、最初の手段ではない。そもそも値に含める
必要がないものは発生源で落とす。開閉局ログは端末文書を丸ごと埋め込み、3 つの
サービスが保存し互いに配信し合うため、terminal サービスは埋め込むコピーの
`api_key` と スタッフの `pin` を伏せる（`_terminal_info_for_log`）。最初から
入らなければ、読む側のどこからも漏れない。

以上はコードを読むだけでは確認できない。`tests/e2e/test_credential_sentinels.py`
は、他の何とも間違えようのない資格情報を仕込み、店舗が使うのと同じ順に
システムを一巡させ（最後に見つかった漏洩はいずれも失敗経路にあったため、
失敗経路も意図的に踏む）、全コンテナのログと全コレクションを読み返して
それらを探す。値がどう書かれたかについて何も仮定しないことが要点である。
このテストが最初に見つけた漏洩は、複数行にまたがる呼び出しの中の属性参照
という、あらゆるテキスト検索が見落とす形をしていた。

マスクは秘匿の問題、後述の上限はサイズの問題であり、別々の問いに答える
別々の関数である。1 つのフィールドがその両方を必要とすることもある。

#### ログボディの上限 (issue #155)

ボディはリクエストログファイルとテナント別 `request_log` コレクションの
2 箇所に保存されるため、上限のないボディは二重にコストを払うことになる。
リクエスト・レスポンスの双方について、保存前に以下のサニタイズを行う。

1. **フィールド除去**: `REQUEST_LOG_STRIP_FIELDS` に指定されたフィールドを
   マーカー（`{"_stripped": "<field>", ...}`）に置き換える。マーカーには
   除去した値の短いスカラーメンバーだけを残すため、署名鍵 ID・スキーマ
   バージョン・発行時刻は検索可能なまま、本体だけが落ちる。既定値は署名済み
   カートスナップショット（`signedSnapshot` / `signed_snapshot`）を対象とする。
   これはカート更新のたびに参照マスタを含むカート文書全体を運ぶうえ、
   サーバーが発行したものそのものなので再構成可能であり、リストアの監査証跡は
   `log_cart_restore` にある。
2. **サイズ上限**: 除去後もなお `REQUEST_LOG_MAX_BODY_BYTES` を超えるボディは
   `{"_truncated": true, "_encoded_bytes": N, "_preview": "..."}` に置き換える（プレビューは上限値までに切り詰める）。

いずれもログに残る内容だけに作用し、クライアントには常に完全なボディが返る。
サニタイズは例外を投げない。処理できないボディは `{"_sanitize_failed": true}`
として保存され、リクエスト自体は失敗しない。

| 環境変数 | 既定値 | 用途 |
|---|---|---|
| `REQUEST_LOG_STRIP_FIELDS` | `signedSnapshot,signed_snapshot` | マーカーに置き換えるボディフィールド（カンマ区切り）。除去を無効化するには空白1文字を設定する。**空文字は無視され**既定値が適用される（`Settings` は `env_ignore_empty=True`） |
| `REQUEST_LOG_MAX_BODY_BYTES` | `32768` | ログに残すボディのサイズ上限。`0` で上限無効 |

なお gzip (#147) はこの量を抑えない。ログにはパース済みの非圧縮ボディが
保存されるため、転送時の圧縮は届かない。

## 8. ビジネスロジック支援

### トランザクション種別 (`enums.py`)

```python
class TransactionType(Enum):
    """トランザクション種別"""

    # 販売操作（整数値）
    NormalSales: int = 101           # 通常販売
    NormalSalesCancel: int = -101    # 通常販売取消（精算前）
    ReturnSales: int = 102           # 返品
    VoidSales: int = 201             # 販売取消
    VoidReturn: int = 202            # 返品取消

    # 端末操作
    Open: int = 301                  # 開店
    Close: int = 302                 # 閉店

    # 現金操作
    CashIn: int = 401                # 現金入金
    CashOut: int = 402               # 現金出金

    # レポート
    FlashReport: int = 501           # 中間報告
    DailyReport: int = 502           # 日次報告
```

### 税計算・端数処理

```python
class TaxType(Enum):
    """税種別"""
    External: str = "External"  # 外税（価格に加算）
    Internal: str = "Internal"  # 内税（価格に含む）
    Exempt: str = "Exempt"      # 非課税

class RoundMethod(Enum):
    """端数処理方法"""
    Round = "Round"  # 四捨五入
    Floor = "Floor"  # 切り捨て
    Ceil = "Ceil"    # 切り上げ
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
    """レシートデータクラス - 生成されたテキストを保持"""

    receipt_text: str = ""   # レシート印刷用テキスト
    journal_text: str = ""   # 電子ジャーナル用テキスト
```

**注:** `ReceiptData`は生成されたテキストのみを保持するシンプルな構造です。`receipt_text`は **device-agnostic な印字データ（`print_document`スキーマ）を `json.dumps` した JSON 文字列**を保持します（旧来の XML 文字列から移行）。フィールド名・型（`str`）は不変で、中身のフォーマットのみ XML→JSON に変わりました。`journal_text`は従来どおりプレーンテキストの電子ジャーナルです（feature #139）。

### 印字データJSONモデル (`print_document_model.py`)

レシートの構造化データには、OPOS・特定プリンタ機種に依存しない意味要素ベースの **JSON モデル**を使用します（旧 `pydantic-xml` の `PrintData`/`BaseXmlModel`/`Table` は撤去）。`AbstractReceiptData.make_receipt_data()` がこのモデルを構築し、`json.dumps` した文字列を `ReceiptData.receipt_text` に格納します。

```python
class PrintDocument(BaseModel):
    """印字文書のルート。to_dict() で camelCase JSON 化"""
    schema_version: str = "1.0"
    metadata: Metadata           # documentType/tenantId/storeCode/terminalNo/
                                 # transactionNo/receiptNo/businessDate/
                                 # generatedAt/locale/charsPerLine
    elements: list[Element]      # 順序付き印字要素列

# 要素（type で判別するユニオン）: いずれも PrintElement を継承
#   text       … 単一テキスト行（value/align/style）
#   columns    … 複数カラム行（left/mid(startCol)/right・カラム単位 style）
#   ruledLine  … 区切り罫線（char）
#   feed       … 行送り（lines）
#   cut        … レシートカット（full/partial）
#   barcode    … バーコード（symbology/data/height/hri/align）
#   qrcode     … QRコード（data/errorCorrection/moduleSize/align）
#   image      … 画像（source: base64/url）
#   logo       … 事前登録ロゴ（logoId）

class Style(BaseModel):
    """文字修飾: bold/underline/reverse/scaleWidth/scaleHeight(倍角 1-8)/font"""

class PrintElement(BaseModel):
    """全要素の基底。内部ルーティング属性 channel(R/J/RJ, 既定 RJ) を持つ。
    channel は JSON 出力からは除外(exclude=True)される内部属性。"""
    channel: Literal["R", "J", "RJ"] = Field("RJ", exclude=True)
```

**R/J/RJ チャネル（ステーション）**: 各要素は内部 `channel` を持ち、`make_receipt_data()` が振り分けます。R/RJ → `receipt_text`（レシート）、J/RJ → `journal_text`（電子ジャーナル）。`channel` は JSON 出力には現れません。`line_split`/`line_center`/`line_left`/`line_right`/`line_boarder` の各ヘルパに `channel` 引数（既定 `RJ`）で指定できます。詳細は `specs/139-receipt-print-schema/contracts/print-document.schema.md`。

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
        filter_dict = {
            "tenant_id": self.tenant_id,
            "store_code": self.store_code,
            "item_code": item_code
        }
        # AbstractRepositoryのget_one_asyncメソッドを使用
        return await self.get_one_async(filter_dict)

    async def get_items_by_category(self, category_code: str, page: int = 1, limit: int = 100) -> list:
        """カテゴリコードで店舗別商品リストを取得（ページネーション付き）"""
        filter_dict = {
            "tenant_id": self.tenant_id,
            "store_code": self.store_code,
            "category_code": category_code
        }
        # ページネーション付きリスト取得
        return await self.get_paginated_list_async(filter_dict, limit=limit, page=page)

    async def create_item_store_async(self, item_store_doc: ItemStoreMasterDocument) -> bool:
        """新規店舗別商品を作成"""
        item_store_doc.tenant_id = self.tenant_id
        item_store_doc.store_code = self.store_code
        # AbstractRepositoryのcreate_asyncメソッドを使用（成功時Trueを返す）
        return await self.create_async(item_store_doc)

    async def update_price_async(self, item_code: str, new_price: float) -> bool:
        """店舗別価格を更新"""
        filter_dict = {
            "tenant_id": self.tenant_id,
            "store_code": self.store_code,
            "item_code": item_code
        }
        # update_one_asyncは部分更新に使用（WriteConflictの自動リトライ付き）
        return await self.update_one_async(filter_dict, {"store_price": new_price})
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