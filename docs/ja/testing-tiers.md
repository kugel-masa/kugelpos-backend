# テストの3層構造ガイド

このドキュメントは Kugelpos の各サービスにおけるテストの階層分け(unit / integration / e2e)の定義と書き分け基準をまとめたものです。

## 概要

| 層 | 場所 | 外部依存 | 速度目標 | 並列実行 |
|---|---|---|---|---|
| **unit** | `services/<svc>/tests/unit/` | なし(全 mock) | サービス全体 < 10秒 | 完全並列可 |
| **integration** | `services/<svc>/tests/integration/` | 実 MongoDB のみ | サービス全体 < 2分 | サービス間並列可 |
| **e2e** | `services/<svc>/tests/e2e/` または top-level `/e2e/` | full docker-compose stack | 数分 | 直列 |

## 各層の責務

### Unit tests (`tests/unit/`)

「ロジックを単独で検証する」テスト。**何も起動していなくても通る**こと。

**書くもの**:
- repository: `motor` をモックして CRUD ロジック / クエリ生成を検証
- service / business logic: repository 層をモックして state machine、計算、判定ロジックを検証
- API layer: `TestClient` + service 層モックでリクエスト/レスポンスの shape、バリデーション、エラーハンドリングを検証
- circuit breaker のしきい値、各種ユーティリティ関数

**書かないもの**:
- 実 DB アクセス
- 実 HTTP コール(他サービスへの呼び出しを含む)
- 実 Dapr / Redis / RabbitMQ

**Marker**:
```python
import pytest

pytestmark = pytest.mark.unit
```
またはファイル単位で `pytest.ini` の `markers = unit:` で定義したマーカーを使用。

### Integration tests (`tests/integration/`)

「サービス1つの内部結合を実物の DB で検証する」テスト。**MongoDB のみ起動していれば通る**こと。

**書くもの**:
- 実 MongoDB に対する repository の動作(aggregation pipeline 含む)
- API → service → repository → DB の縦串
- インデックス・スキーマ・トランザクション境界の検証

**外部呼び出しの扱い**:
- 他サービス HTTP は `respx` でモック
- Dapr 呼び出しは `DaprClientHelper` を DI で差し替えてモック
- JWT は `kugel_common.security` の関数を使ってテスト内でローカル生成(他サービスの token endpoint を叩かない)

**Marker**:
```python
pytestmark = pytest.mark.integration
```

### E2E tests (`tests/e2e/` または `/e2e/`)

「業務シナリオを横断的に検証する」テスト。**full docker-compose stack が必要**。

**書くもの**:
- 「カート作成 → 商品追加 → 決済 → tranlog 発行 → journal 記録 → report 集計」のような業務フロー
- Dapr pub/sub の実動作
- circuit breaker の実発火検証
- multi-service 認証フロー

**配置**:
- 1 サービス内で完結する e2e は `services/<svc>/tests/e2e/`
- 複数サービスをまたぐ横断シナリオは top-level `/e2e/`

top-level `/e2e/` には現状、以下のクロスサービステストを配置:

| ファイル | 検証内容 |
|---|---|
| `test_health_all_services.py` | 全サービス `/health` の疎通 |
| `test_pos_full_journey.py` | tenant 準備 → 開局 → カート → 決済 → tranlog 発行 → journal/report 集計 |
| `test_void_return_journey.py` | Void/Return 系の符号反転を cart → journal → report で確認 |
| `test_pubsub_idempotency.py` | 同一 `event_id` の再配信で二重集計が起きないこと |
| `test_data_consistency.py` | cart/journal/report 間の合計値整合性 |
| `test_auth_boundary.py` | 越境テナント拒否、期限切れ/署名不正/不正形 JWT |
| `test_concurrency.py` | 並列カート操作と pub/sub の順序 |

`/e2e/` は専用の `Pipfile` (独立 venv) を持ち、`scripts/run_e2e_tests.sh` がサービス毎の e2e の後で自動実行する。

**Marker**:
```python
pytestmark = pytest.mark.e2e
```

## 実行方法

### Unit tests のみ(MongoDB 不要)

```bash
# 全サービス
./scripts/run_unit_tests.sh

# 特定サービス
./scripts/run_unit_tests.sh cart account

# 1サービス内で
cd services/cart
pipenv run pytest -m unit
```

### Integration tests(MongoDB のみ起動)

```bash
# MongoDB を起動
./scripts/start-with-mongodb-replica.sh   # MongoDB のみ

# 実行
./scripts/run_integration_tests.sh
# または
cd services/cart
pipenv run pytest -m integration
```

### E2E tests(全スタック起動)

```bash
# 全サービスを起動
./scripts/start.sh

# 実行
./scripts/run_e2e_tests.sh
```

### `run_all_tests.sh` (legacy 互換 wrapper)

`./scripts/run_all_tests.sh` および `./scripts/run_all_tests_with_progress.sh` は、unit → integration → e2e を順次叩く薄いラッパとして残してある。サービスごとの `run_all_tests.sh` も同様。tier ごとに走らせたい場合は上の3スクリプトを直接使うこと。

## 書き分けの判断フロー

新規テストを書くとき:

1. **DB なしで通るか?**
   - YES → `tests/unit/`
   - NO → 2 へ

2. **他サービス起動なしで通るか?(MongoDB のみで OK か?)**
   - YES → `tests/integration/`
   - NO → 3 へ

3. **複数サービスの相互作用を検証しているか?**
   - YES → top-level `/e2e/`
   - NO(でも該当サービスのフルスタック確認が必要) → `tests/<svc>/tests/e2e/`

## クロスサービス HTTP モックパターン(integration)

他サービスへの outbound HTTP は `respx` でモック:

```python
import respx
import httpx

@pytest.fixture
def mock_account_service(respx_mock):
    respx_mock.post("http://localhost:8000/api/v1/accounts/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "fake-token", "token_type": "bearer"},
        )
    )
    yield respx_mock
```

## ローカル JWT 生成パターン(integration)

`kugel_common` の関数を使い、account サービスを起動せずにテスト用 JWT を生成:

```python
from kugel_common.security import create_access_token
from datetime import timedelta

@pytest.fixture(scope="session")
def admin_token():
    return create_access_token(
        data={"sub": "admin", "tenant_id": "T9999"},
        expires_delta=timedelta(hours=1),
    )
```

`SECRET_KEY` は `.env.test` の固定値を使用(本番とは別)。

## Dapr モックパターン(integration)

`DaprClientHelper` を依存性注入で差し替え:

```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_dapr_client():
    client = AsyncMock()
    client.publish_event = AsyncMock(return_value=None)
    client.save_state = AsyncMock(return_value=None)
    client.get_state = AsyncMock(return_value=None)
    return client
```

## 関連

- 3層化リファクタの議論・移行ログ: GitHub Issue/PR #109, #110
- スラッシュコマンド: `/test-guide` (`.claude/commands/test-guide.md`)
