# Quickstart: 移行の確かめ方

**Feature**: 301-pymongo-async-migration

## 1. Motor が残っていない

```bash
grep -rn -i "motor" --include=*.py services | grep -v "/\.venv/"          # 0 件（コメント中の説明も直す）
grep -n -i "motor" services/*/Pipfile services/*/Pipfile.lock services/commons/pyproject.toml   # 0 件
```

## 2. 依存とロック（R-9）

```bash
for s in account cart journal master-data report stock terminal; do
  (cd services/$s && pipenv verify) || echo "verify failed: $s"
done

# 空の環境で、ロックだけから入るか
for s in account cart journal master-data report stock terminal; do
  (cd services/$s && export WORKON_HOME=$(mktemp -d) PIPENV_VENV_IN_PROJECT=0 &&
   pipenv install --deploy && pipenv run pip check &&
   pipenv run python -c "from pymongo import AsyncMongoClient" &&
   ! pipenv run python -c "import motor" 2>/dev/null) || echo "deploy check failed: $s"
done

./scripts/build.sh                                  # 全イメージを作り直す
```

## 3. テスト

```bash
./scripts/run_unit_tests.sh
./scripts/start.sh
./scripts/run_integration_tests.sh                  # commons を含む（R-11）

# await の付け忘れを失敗にする（R-10）
for s in commons account cart journal master-data report stock terminal; do
  (cd services/$s && pipenv run pytest -W error::RuntimeWarning tests/unit) || echo "unit RW failed: $s"
done
# integration も同様（cart は unit と integration を別のプロセスで走らせる: #153）

./scripts/run_e2e_tests.sh                          # cart は DUAL（既定）: 96 passed
```

cart を REQUIRED で（/test-guide）:

```bash
echo 'CART_REQUEST_SNAPSHOT_MODE=REQUIRED' >> services/cart/.env
./scripts/stop.sh && ./scripts/start.sh             # 再起動しないとモードは変わらない
docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE   # REQUIRED であること
cd services/cart && pipenv run pytest tests/e2e -m "not dual_only"   # 48 passed, 48 deselected
# 終わったら .env の行を消して再起動する
```

## 4. 書き方が変わる箇所

- commons の integration に、集計・セッション（commit / abort / `async with`）・接続の終了（同じループ、二重、別のループ）・件数 0・ループごとの接続のテストがあり、通る
- `grep -rn -E "\.(aggregate|list_indexes|close|start_transaction)\(" services/*/app services/*/tests services/commons/src services/commons/tests` の結果がすべて `await` 付き（PyMongo の対象に限る）
- 統合テストの出力に「別のループから閉じようとした」警告が無い

## 5. 停止のログ（R-10）

```bash
./scripts/stop.sh
# 停止の直前に各サービスのログを保存して確かめる
for s in account terminal master-data cart report journal stock; do
  docker logs services-$s-1 2>&1 | grep -i -E "unclosed|RuntimeError|DatabaseException|never awaited"
done                                                # 何も出ない
```

## 6. 性能

移行前の main と移行後のブランチで、標準の性能テスト（`/perf-test`）を同じ条件で走らせ、主要な指標を表で比べる。10% を超える劣化には、説明か対処を付ける。

## 7. 手順書

`docs/{en,ja}/general/pymongo-async-migration.md` に、対応表、書き方が変わる箇所と見つけ方（R-8 の検索項目をすべて含む）、順番、確かめ方、依存の更新の仕方がある。下流のツリーの名前は無い。
