# Quickstart — 実装〜検証の動線

**Feature**: Cart Master-Data 共通キャッシュ基盤
**Branch**: `072-master-data-cache`

本ドキュメントは実装着手から E2E 検証までの最短経路を示す。詳細設計は [data-model.md](./data-model.md)、未解決事項の決着は [research.md](./research.md)、I/F は [contracts/](./contracts/) を参照。

---

## 0. 前提

- 既に `072-master-data-cache` ブランチに切替済み（`git status` で確認）
- リポジトリルートで作業（`/home/masa/proj/kugelpos-public/`）
- Docker / Docker Compose / Pipenv が利用可能

---

## 1. フェーズ 1: 共通キャッシュ基盤（commons）

### 1.1 ファイル作成

```text
services/commons/src/kugel_common/utils/cache/__init__.py
services/commons/src/kugel_common/utils/cache/cache_backend.py
services/commons/src/kugel_common/utils/cache/in_memory_cache_backend.py
services/commons/src/kugel_common/utils/cache/dapr_state_cache_backend.py
```

各クラスのインターフェースは `specs/072-master-data-cache/contracts/cache_backend.py` 準拠。

### 1.2 単体テスト

```text
services/commons/tests/unit/utils/cache/test_in_memory_cache_backend.py
services/commons/tests/unit/utils/cache/test_dapr_state_cache_backend.py
```

カバレッジ項目:
- get / set / delete のラウンドトリップ
- TTL 失効
- increment の単発・並行・バックエンド失敗
- バックエンド失敗時の例外不伝播（None / False を返すこと）

### 1.3 実行

```bash
cd services/commons
pipenv run pytest tests/unit/utils/cache/ -v
```

---

## 2. フェーズ 1 (続): 共通基底クラス（cart）

### 2.1 ファイル作成

```text
services/cart/app/models/repositories/abstract_master_data_repository.py
```

I/F は `specs/072-master-data-cache/contracts/abstract_master_data_repository.py` 準拠。

### 2.2 設定追加

`services/cart/app/config/settings_cart.py` に [data-model.md §9](./data-model.md) の表どおりに新設定キーを追加。旧 `USE_ITEM_CACHE` / `ITEM_CACHE_TTL_SECONDS` は撤去（cart 内部のみで参照されているので破壊的変更ではない）。

### 2.3 Dapr コンポーネント追加

```text
services/dapr/components/masterstore.yaml
```

内容は [data-model.md §10](./data-model.md)。K8s / Azure 用テンプレも同様に追加。

### 2.4 lifespan で backend を生成

`services/cart/app/main.py` の FastAPI lifespan handler を改修:

```python
async def lifespan(app: FastAPI):
    # ... 既存処理 ...
    app.state.master_cache_backend = DaprStateCacheBackend(
        store_name=cart_settings.MASTER_DATA_CACHE_STATE_STORE
    )
    yield
    await app.state.master_cache_backend.close()
```

### 2.5 単体テスト

```text
services/cart/tests/unit/repositories/test_abstract_master_data_repository.py
```

`InMemoryCacheBackend` を注入してテスト:
- HIT / MISS の基本動作
- NotFoundException 時にキャッシュ書込みされないこと（FR-013 / SC-009）
- バックエンド get 失敗時に直接フェッチへ落ちること（FR-007 / SC-003）
- store_code_override の優先順位（R-009）
- 世代カウンタ +1 で旧エントリが論理的に消えること（FR-006 / SC-005）
- entry_kind 違いでキー衝突しないこと（FR-010）

### 2.6 実行

```bash
cd services/cart
pipenv run pytest tests/unit/repositories/test_abstract_master_data_repository.py -v
```

---

## 3. フェーズ 2: ItemMasterWeb / ItemMasterGrpc 移行

最も恩恵が大きく、Web/Grpc 両系統で SC-007（経路間キャッシュ共有）を検証できるため最初に移行する。

### 3.1 改修

```text
services/cart/app/models/repositories/item_master_web_repository.py
services/cart/app/models/repositories/item_master_grpc_repository.py
services/cart/app/models/repositories/item_master_repository_factory.py
```

- 旧 `_item_cache` / `USE_ITEM_CACHE` 参照を削除
- `AbstractMasterDataRepository[ItemMasterDocument]` を継承
- `_fetch_one(item_code)` のみ実装（既存の HTTP/gRPC 呼び出しコードを移植）
- factory は `cache_backend` を受け取り両クラスに渡す

### 3.2 DI 改修

`services/cart/app/dependencies/` 配下の DI 関数で、Item リポジトリ生成時に `request.app.state.master_cache_backend` を渡す。

### 3.3 既存テスト更新

`services/cart/tests/unit/repositories/test_item_master_*.py` を新シグネチャに合わせる。fetch のモック化（`monkeypatch.setattr` で `_fetch_one` を差し替え）。

### 3.4 結合テスト

```text
services/cart/tests/integration/repositories/test_item_master_with_dapr.py
```

実 Redis + Dapr サイドカー起動状態で:
- HIT / MISS / TTL 失効が観測可能
- Web で書いたエントリを Grpc が読める（SC-007）
- 世代カウンタが Redis 上で +1 されている

```bash
./scripts/start.sh                   # 全サービス起動
cd services/cart
pipenv run pytest tests/integration/repositories/test_item_master_with_dapr.py -v
```

---

## 4. フェーズ 3: 残りリポジトリ移行

Payment / Promotion / Settings / Tax を順次移行。順番は任意だが、Promotion（メソッド引数 store_code）と Settings（テナント/店舗二重性）は R-001 / R-002 の決定事項を厳密に踏襲すること。

各リポジトリの単体テストを新シグネチャに合わせ、`pipenv run pytest tests/unit/repositories/` が全件通ることを確認。

---

## 5. フェーズ 4: 旧設定の撤去と仕上げ

- `services/cart/app/config/settings_cart.py` の旧 `USE_ITEM_CACHE` / `ITEM_CACHE_TTL_SECONDS` 撤去
- 既存ドキュメント（`docs/ja/...`）への記述があれば更新
- `pipenv run ruff check app/` / `ruff format app/` を変更ファイルに対して実行

---

## 6. E2E 検証

```bash
./scripts/run_e2e_tests.sh
```

確認ポイント:
- 既存の購買シナリオがすべて通ること（リグレッションなし）
- カート操作で同一商品を 2 回引いた場合、master-data サービスへのリクエストログが 1 回のみ（カートサービスのアクセスログまたは master-data 側のアクセスログを確認）

---

## 7. 手動検証

### 7.1 キーの実際の格納形式を確認

```bash
docker compose exec redis redis-cli -n 3
> KEYS mdcache:*
> GET mdcache:T001:S001:item_master:gen0:one:ITEM_A
```

### 7.2 個別無効化

```python
# IPython など対話シェルで cart の DI コンテナを使うか、
# 一時的な管理エンドポイント / pytest fixture で:
await item_repo.invalidate("ITEM_A")
# その直後にもう一度引くと master-data がアクセスされる（ログで確認）
```

### 7.3 namespace 一括無効化

```python
await item_repo.invalidate_all()
# 世代カウンタが +1 されていることを Redis CLI で確認
docker compose exec redis redis-cli -n 3 GET mdcache:T001:S001:item_master:generation
```

### 7.4 バックエンド障害時の継続稼働

```bash
# Redis を一時停止
docker compose stop redis
# カート操作を実行 → 通常通り完了することを確認（応答は遅くなる）
docker compose start redis
# カート操作を再実行 → 通常速度に戻ることを確認
```

---

## 8. リリース前チェックリスト

- [ ] `pipenv run pytest -m unit` 全件 PASS（cart / commons）
- [ ] `pipenv run pytest -m integration` 全件 PASS（実 Redis 起動状態）
- [ ] `./scripts/run_e2e_tests.sh` 全件 PASS
- [ ] `pipenv run ruff check` 変更ファイルすべて PASS
- [ ] 旧設定キー (`USE_ITEM_CACHE` 等) のコード内参照が 0 件（`grep -r "USE_ITEM_CACHE" services/cart`）
- [ ] `docs/` 配下に該当する記述があれば更新
- [ ] Issue #125 にチェックボックスがあれば消化済み

---

## 参考

- [Issue #125](https://github.com/kugel-masa/issues/125) — 元の改善提案
- [spec.md](./spec.md) — 機能仕様
- [research.md](./research.md) — 設計決定事項
- [data-model.md](./data-model.md) — クラス / キー / 設定の詳細
- [contracts/](./contracts/) — 公式インターフェース
