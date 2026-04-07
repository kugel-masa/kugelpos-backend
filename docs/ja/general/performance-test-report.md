# パフォーマンステストレポート

## テスト環境

| 項目 | 値 |
|------|-----|
| VM | Lima (シングルホスト) |
| CPU | 6コア |
| メモリ | 16GB |
| OS | Linux 6.8.0-101-generic |
| 認証 | JWT |

### サービス構成 (docker-compose.prod.yaml)

| サービス | ワーカー数 |
|---------|-----------|
| account | 2 |
| terminal | 4 |
| master-data | 4 |
| **cart** | **8** |
| report | 2 |
| journal | 2 |
| stock | 1 |

### テスト条件

- **ユーザー数**: 300
- **テスト時間**: 3分
- **ターミナル数**: 310（マルチターミナルモード）
- **テスト前手順**: 全サービス再起動 → テストデータセットアップ → Redis FLUSHALL

---

## サマリー

| # | 施策 | 効果 | ポイント |
|---|------|------|---------|
| 1 | ベースライン安定性検証（2回実施） | — | req/s は ±0.5% で安定。Avg は ±15〜19% の変動幅があり、これを超えない限り有意差とは言えない |
| 2 | Redis 永続化（RDB）無効化 | **効果なし** | RDB は fork() ベースの非同期書き込みでメインプロセスをブロックしない。3回実施しエラー0件・性能差なし |
| 3 | Cart cache deletion（bill/cancel 時にキャッシュ削除） | **効果なし** | 3分間では効果が見えない。長時間テストではカート蓄積によるRedisメモリ削減効果が顕在化する可能性あり |
| 4 | pub/sub publish 非同期化（`asyncio.create_task()`） | **大幅悪化** | 全エンドポイントで Avg +63〜121%、P95 +119〜300%。バックグラウンドタスクがイベントループを圧迫。シングルVM では逆効果 |
| 5 | Redis activedefrag + THP 無効化 | **効果なし** | 短時間テストでは差が出ない。フラグメンテーション蓄積の予防措置として本番適用を推奨。今回の環境は THP が `madvise` → `never` で影響小 |
| 6 | Create Cart asyncio.gather()（マスタデータ4並列取得） | **効果なし** | Create Cart Avg -2〜+2%、req/s +0.2%。4つの HTTP 呼び出しを並列化したが、ベースライン変動幅内。個々の呼び出しが軽量なため並列化の恩恵が小さい |
| 7 | Cancel Cart setting value asyncio.gather()（5設定値並列取得） | **効果なし〜微改善** | Cancel Cart Avg -15〜-5%、Add Item Avg -9〜-24%、req/s +0.6%。変動幅内だが全指標で改善傾向。設定値取得の並列化は軽量だが一貫した改善を示す |
| 8 | Worker count tuning（master-data 4w→8w） | **効果なし〜微悪化** | Create Cart Avg +1〜+16%、Cancel Cart Avg +8〜+20%、req/s -0.4%。master-data ワーカー増加が CPU 競合を増やし、むしろ悪化傾向。6コア環境では過剰 |

---

## テスト 1: ベースライン安定性の検証

**日付**: 2026-04-07
**目的**: ベースラインの再現性を確認（テスト条件の妥当性検証）
**コード**: main（変更なし）
**Redis**: RDB 有効（デフォルト）

### Run 1

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 159 | 130 | 350 | 610 | 5.00 |
| Add Item | 53 | 29 | 180 | 360 | 81.81 |
| Cancel Cart | 419 | 350 | 830 | 1100 | 3.34 |
| **Aggregated** | **72** | **33** | **290** | **570** | **90.16** |

### Run 2

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 183 | 130 | 460 | 1400 | 5.01 |
| Add Item | 63 | 32 | 210 | 550 | 81.35 |
| Cancel Cart | 466 | 400 | 900 | 1600 | 3.34 |
| **Aggregated** | **85** | **37** | **330** | **730** | **89.69** |

### 安定性の評価

| 指標 | Run 1 | Run 2 | 変動幅 |
|------|-------|-------|--------|
| Create Cart Avg | 159ms | 183ms | ±15% |
| Add Item Avg | 53ms | 63ms | ±19% |
| Cancel Cart Avg | 419ms | 466ms | ±11% |
| Aggregated req/s | 90.16 | 89.69 | ±0.5% |

**req/s は非常に安定**（±0.5%）。平均レスポンスタイムは ±15〜19% の変動があるが、300ユーザーでは許容範囲。

---

## テスト 2: Redis 永続化なし (永続化無効) のベースライン

**日付**: 2026-04-07
**目的**: Redis RDB を無効化した場合のパフォーマンス影響を確認
**コード**: main（変更なし）

### Redis 設定

```
command: ["redis-server", "--save", "", "--appendonly", "no"]
```

### Run 1

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 236 | 150 | 720 | 1200 | 5.01 |
| Add Item | 77 | 37 | 290 | 530 | 80.88 |
| Cancel Cart | 606 | 500 | 1300 | 2100 | 3.34 |
| **Aggregated** | **105** | **44** | **430** | **830** | **89.22** |

### Run 2

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 184 | 130 | 500 | 900 | 5.01 |
| Add Item | 62 | 33 | 220 | 400 | 81.52 |
| Cancel Cart | 472 | 390 | 1100 | 1400 | 3.34 |
| **Aggregated** | **84** | **39** | **320** | **600** | **89.87** |

### 永続化有効 vs 永続化無効の比較 (Run 2 同士)

| Endpoint | 永続化有効 | 永続化無効 | 差分 |
|----------|--------|--------|------|
| Create Cart Avg | 183ms | 184ms | +0.5% |
| Add Item Avg | 63ms | 62ms | -1.6% |
| Cancel Cart Avg | 466ms | 472ms | +1.3% |
| req/s | 89.69 | 89.87 | +0.2% |

### Run 3（再テスト: 標準手順で再実施）

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 188 | 130 | 480 | 1300 | 5.00 |
| Add Item | 64 | 30 | 240 | 520 | 81.37 |
| Cancel Cart | 473 | 380 | 1000 | 1800 | 3.34 |
| **Aggregated** | **86** | **35** | **340** | **670** | **89.71** |

### 結論

**RDB の有無による差はなし。3回のテストすべてでエラー0件。**

- Redis の RDB 永続化は `fork()` ベースの非同期書き込み。メインプロセスはブロックされない
- 3分間のテストでは 永続化トリガーが数回程度で影響が微小

---

## テスト 3: Cache Deletion (bill/cancel 時のカートキャッシュ削除)

**日付**: 2026-04-07
**目的**: bill/cancel 後に Redis キャッシュを保存→削除に変更した場合の効果を検証
**コード**: `feature/89-async-parallelization` ブランチの cache deletion のみ
**Redis**: RDB 有効（デフォルト）

### 変更内容

`services/cart/app/services/cart_service.py` の2箇所:
- **cancel_transaction_async**: `__cache_cart_async(Cancelled)` → `__remove_cached_cart_async()`
- **bill_async**: `__cache_cart_async(Completed)` → `__remove_cached_cart_async()`

完了済みカートを Redis に保存せず削除することで、Redis メモリ使用量を削減し、テールレイテンシの改善を期待。

### After (Cache Deletion 適用)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 194 | 140 | 520 | 900 | 5.00 |
| Add Item | 64 | 32 | 230 | 480 | 81.33 |
| Cancel Cart | 483 | 400 | 1000 | 1400 | 3.34 |
| **Aggregated** | **86** | **38** | **340** | **680** | **89.67** |

### Before/After 比較

| Endpoint | Baseline Run 1 | Baseline Run 2 | Cache Deletion | 評価 |
|----------|---------------|---------------|---------------|------|
| Create Cart Avg | 159ms | 183ms | 194ms | 変動幅内 |
| Add Item Avg | 53ms | 63ms | 64ms | 変動幅内 |
| Cancel Cart Avg | 419ms | 466ms | 483ms | 変動幅内 |
| req/s | 90.16 | 89.69 | 89.67 | 変動幅内 |

| Endpoint | Baseline P99 範囲 | Cache Deletion P99 | 評価 |
|----------|------------------|-------------------|------|
| Create Cart | 610〜1400ms | 900ms | 変動幅内 |
| Add Item | 360〜550ms | 480ms | 変動幅内 |
| Cancel Cart | 1100〜1600ms | 1400ms | 変動幅内 |

### 結論

**3分間のテストでは効果なし。**

3分間ではカート蓄積量が少なく、deletion の効果が出にくい。長時間テストではカート蓄積による Redis メモリ削減効果が顕在化する可能性がある。

---

## テスト 4: Cancel/Bill pub/sub publish 非同期化

**日付**: 2026-04-07
**目的**: `create_tranlog_async` 内の pub/sub publish を `asyncio.create_task()` で非同期化した場合の効果を検証
**コード**: main + `tran_service.py` の1箇所のみ変更（Issue #89 提案3）
**Redis**: RDB 有効（デフォルト）

### 変更内容

`services/cart/app/services/tran_service.py` の `create_tranlog_async` 内:
```python
# Before
await self._publish_tranlog_async(event_message)

# After
asyncio.create_task(self._publish_tranlog_async(event_message))
```

DBトランザクション（tranlog + delivery_status）コミット後の pub/sub 配信を fire-and-forget 化。
失敗時は delivery_status で追跡され、cron ジョブが5分ごとにリトライする設計。

### After (pub/sub 非同期化)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 345 | 150 | 1400 | 2300 | 5.00 |
| Add Item | 103 | 37 | 460 | 820 | 79.81 |
| Cancel Cart | 924 | 620 | 2800 | 4000 | 3.34 |
| **Aggregated** | **148** | **45** | **610** | **1400** | **88.15** |

### Before/After 比較

| Endpoint | Baseline Avg (Run1/Run2) | pub/sub async | 変化 | 評価 |
|----------|------------------------|--------------|------|------|
| Create Cart | 159 / 183ms | 345ms | +88〜117% | **大幅悪化** |
| Add Item | 53 / 63ms | 103ms | +63〜94% | **大幅悪化** |
| Cancel Cart | 419 / 466ms | 924ms | +98〜121% | **大幅悪化** |
| req/s | 90.16 / 89.69 | 88.15 | -2% | 微減 |

| Endpoint | Baseline P95 (Run1/Run2) | pub/sub async P95 | 変化 |
|----------|------------------------|-------------------|------|
| Create Cart | 350 / 460ms | 1400ms | +204〜300% |
| Add Item | 180 / 210ms | 460ms | +119〜156% |
| Cancel Cart | 830 / 900ms | 2800ms | +211〜237% |

### 結論

**ベースラインの変動幅を大きく超えて全エンドポイントで悪化。**

`asyncio.create_task()` によるバックグラウンド pub/sub が、同一イベントループ内の他リクエスト処理を圧迫している。特に P95 が2〜4倍に悪化しており、テールレイテンシへの影響が顕著。シングルVM環境では pub/sub の非同期化は逆効果。

---

## テスト 5: Redis activedefrag + THP 無効化

**日付**: 2026-04-07
**目的**: Redis のメモリフラグメンテーション対策の効果を検証
**コード**: main（変更なし）
**Redis**: RDB 有効 + `activedefrag yes`
**OS**: THP（Transparent Huge Pages）を `never` に設定

### 変更内容

```bash
# Redis activedefrag 有効化
docker exec redis redis-cli CONFIG SET activedefrag yes

# THP 無効化 (madvise → never)
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

#### activedefrag

Redis がアイドル時にメモリフラグメンテーションを自動修復する機能。デフォルトは無効。有効にすると `mem_fragmentation_ratio` が高くなった際に自動的にメモリ再配置を行う。

#### THP (Transparent Huge Pages) とは

Linux のメモリ管理機能で、通常の 4KB ページの代わりに 2MB の大ページを自動的に使う仕組み。大きなメモリを連続的に使うアプリケーションでは TLB キャッシュヒット率が上がり高速化するが、**Redis では逆効果**になる。

Redis は小さなメモリ領域（カートドキュメント1個 ≒ 16KB）を頻繁に確保・解放する。THP 有効時は以下の問題が生じる:

- Redis が 16KB 書き換え → OS は **2MB ページ全体**を COW コピー（4KB なら 4ページで済む）
- RDB fork 時に COW の単位が 2MB になり、メモリ使用量が急増
- 4KB の変更に対して 2MB のコピーが発生 = **約500倍のオーバーヘッド**

| 設定値 | 動作 | Redis との相性 |
|--------|------|---------------|
| `always` | 常に大ページを使用 | **悪い** |
| `madvise` | アプリが明示的に要求した場合のみ（Redis は要求しない） | 影響小 |
| `never` | 大ページを使わない | **Redis 推奨** |

今回の環境は `madvise` → `never` への変更のため影響は小さい。`always` からの変更であれば大きな差が出る可能性がある。

### After (activedefrag + THP 無効化)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 215 | 140 | 580 | 1700 | 5.01 |
| Add Item | 72 | 35 | 240 | 620 | 81.14 |
| Cancel Cart | 555 | 430 | 1300 | 3100 | 3.34 |
| **Aggregated** | **98** | **42** | **380** | **870** | **89.49** |

### Before/After 比較

| Endpoint | Baseline Avg (Run1/Run2) | activedefrag+THP | 評価 |
|----------|------------------------|-----------------|------|
| Create Cart | 159 / 183ms | 215ms | 変動幅内〜やや高め |
| Add Item | 53 / 63ms | 72ms | 変動幅内 |
| Cancel Cart | 419 / 466ms | 555ms | 変動幅内〜やや高め |
| req/s | 90.16 / 89.69 | 89.49 | 変動幅内 |

### 結論

**3分間のテストではベースラインとほぼ同等（変動幅内）。**

activedefrag と THP 無効化はデータ蓄積・フラグメンテーションが進む長時間運用で効果が顕在化する施策であり、短時間テストでは差が出にくい。本施策は**予防的措置**として有効。本番環境への適用を推奨する。

---

## テスト 6: Create Cart asyncio.gather()（マスタデータ並列取得）

**日付**: 2026-04-07
**目的**: `create_cart_async` 内の4つの逐次マスタデータ取得を `asyncio.gather()` で並列化した場合の効果を検証
**コード**: main + `cart_service.py` の `create_cart_async` のみ変更
**Redis**: RDB 有効（デフォルト）

### 変更内容

`services/cart/app/services/cart_service.py` の `create_cart_async`:
- `store_info_repo.get_store_info_async()`
- `settings_master_repo.get_all_settings_async()`
- `tax_master_repo.load_all_taxes()`
- `promotion_master_repo.get_active_promotions_by_store_async()`

上記4つの逐次 await を `asyncio.gather()` で並列実行に変更。

### After (asyncio.gather 適用)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 156 | 130 | 350 | 620 | 5.01 |
| Add Item | 52 | 28 | 170 | 380 | 82.00 |
| Cancel Cart | 424 | 380 | 780 | 1100 | 3.34 |
| **Aggregated** | **71** | **32** | **290** | **540** | **90.34** |

### Before/After 比較

| Endpoint | Baseline Avg (Run1/Run2) | gather 適用 | 変化 | 評価 |
|----------|------------------------|------------|------|------|
| Create Cart | 159 / 183ms | 156ms | -2〜-15% | 変動幅内 |
| Add Item | 53 / 63ms | 52ms | -2〜-17% | 変動幅内 |
| Cancel Cart | 419 / 466ms | 424ms | +1〜-9% | 変動幅内 |
| req/s | 90.16 / 89.69 | 90.34 | +0.2〜+0.7% | 変動幅内 |

### 結論

**ベースライン変動幅内で有意差なし。**

4つのマスタデータ取得はいずれも Dapr 経由の HTTP 呼び出しだが、個々の応答時間が短い（数ms〜数十ms）ため、並列化による短縮効果が小さい。Create Cart 自体が全体の req/s に占める割合が低く（5 req/s）、ボトルネックになっていない。ただしコードの可読性と拡張性の観点から、並列化は悪くない設計改善である。

---

## テスト 7: Cancel Cart setting value asyncio.gather()（設定値並列取得）

**日付**: 2026-04-07
**目的**: `create_tranlog_async` 内の5つの逐次設定値取得を `asyncio.gather()` で並列化した場合の効果を検証
**コード**: main + `tran_service.py` の `create_tranlog_async` のみ変更
**Redis**: RDB 有効（デフォルト）

### 変更内容

`services/cart/app/services/tran_service.py` の `create_tranlog_async`:
- `RECEIPT_NO_START_VALUE`
- `RECEIPT_NO_END_VALUE`
- `INVOICE_REGISTRATION_NUMBER`
- `RECEIPT_HEADERS`
- `RECEIPT_FOOTERS`

上記5つの `_get_setting_value_async()` を関数冒頭で `asyncio.gather()` により一括取得に変更。

### After (asyncio.gather 適用)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 157 | 130 | 380 | 630 | 5.01 |
| Add Item | 48 | 27 | 160 | 330 | 81.88 |
| Cancel Cart | 396 | 350 | 740 | 1100 | 3.34 |
| **Aggregated** | **67** | **30** | **270** | **480** | **90.22** |

### Before/After 比較

| Endpoint | Baseline Avg (Run1/Run2) | gather 適用 | 変化 | 評価 |
|----------|------------------------|------------|------|------|
| Create Cart | 159 / 183ms | 157ms | -1〜-14% | 変動幅内 |
| Add Item | 53 / 63ms | 48ms | -9〜-24% | 変動幅内（改善傾向） |
| Cancel Cart | 419 / 466ms | 396ms | -5〜-15% | 変動幅内（改善傾向） |
| req/s | 90.16 / 89.69 | 90.22 | +0.1〜+0.6% | 変動幅内 |

| Endpoint | Baseline P95 (Run1/Run2) | gather P95 | 変化 |
|----------|------------------------|-----------|------|
| Create Cart | 350 / 460ms | 380ms | 変動幅内 |
| Add Item | 180 / 210ms | 160ms | -11〜-24% |
| Cancel Cart | 830 / 900ms | 740ms | -11〜-18% |

### 結論

**ベースライン変動幅内だが、全指標で一貫した改善傾向。**

Cancel Cart（Avg -5〜-15%）と Add Item（Avg -9〜-24%）で改善が見られる。5つの設定値取得が逐次から並列になることで、tranlog 作成のレイテンシが削減されている。ただし1回のテストでは変動幅を考慮すると「有意」とまでは言えない。コード品質の観点からも採用を推奨する。

---

## テスト 8: Worker count tuning（master-data 4w→8w）

**日付**: 2026-04-07
**目的**: master-data サービスのワーカー数を4→8に増やした場合の効果を検証
**コード**: main（変更なし）
**Redis**: RDB 有効（デフォルト）

### 変更内容

`services/docker-compose.prod.yaml`:
- master-data: `UVICORN_WORKERS: 4` → `UVICORN_WORKERS: 8`
- cart は 8w のまま（変更なし）

### サービス構成

| サービス | ワーカー数 |
|---------|-----------|
| account | 2 |
| terminal | 4 |
| **master-data** | **8**（4→8に変更） |
| cart | 8 |
| report | 2 |
| journal | 2 |
| stock | 1 |

### After (master-data 8w)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 185 | 130 | 470 | 1000 | 5.00 |
| Add Item | 58 | 30 | 210 | 420 | 81.44 |
| Cancel Cart | 503 | 410 | 1200 | 1800 | 3.34 |
| **Aggregated** | **82** | **35** | **330** | **630** | **89.78** |

### Before/After 比較

| Endpoint | Baseline Avg (Run1/Run2) | 8w 適用 | 変化 | 評価 |
|----------|------------------------|--------|------|------|
| Create Cart | 159 / 183ms | 185ms | +1〜+16% | 変動幅内 |
| Add Item | 53 / 63ms | 58ms | -8〜+9% | 変動幅内 |
| Cancel Cart | 419 / 466ms | 503ms | +8〜+20% | 変動幅内〜やや悪化 |
| req/s | 90.16 / 89.69 | 89.78 | -0.4〜+0.1% | 変動幅内 |

| Endpoint | Baseline P95 (Run1/Run2) | 8w P95 | 変化 |
|----------|------------------------|--------|------|
| Create Cart | 350 / 460ms | 470ms | 変動幅内 |
| Add Item | 180 / 210ms | 210ms | 変動幅内 |
| Cancel Cart | 830 / 900ms | 1200ms | +33〜+45% |

### 結論

**ベースラインと同等〜やや悪化。Cancel Cart の P95 が +33〜45% 悪化。**

6コア環境で master-data を 8 ワーカーに増やすと、cart（8w）+ master-data（8w）= 16 ワーカーとなり、物理コア数を大幅に超過する。コンテキストスイッチのオーバーヘッドが増加し、特に Cancel Cart のようにマスタデータ参照が多いエンドポイントで P95 の悪化が顕著。6コア環境では master-data は 4w が適切。

---

## テスト手順メモ

### 標準テスト手順 (条件を揃えるため)

1. 全サービス停止: `docker compose -f docker-compose.prod.yaml down`
2. 全サービス起動: `docker compose -f docker-compose.prod.yaml up -d`
3. ヘルスチェック確認（全7サービスが healthy）
4. テストデータセットアップ: `bash run_perf_test.sh setup 310`
5. Redis FLUSHALL: `docker exec redis redis-cli FLUSHALL`
6. テスト実行: `bash run_perf_test.sh custom 300 3m`

### 注意事項

- MongoDB のボリュームを削除した場合はレプリカセット初期化が必要
  ```bash
  docker exec mongodb mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
  ```
- Dapr sidecar はタイミングによっては再起動が必要
- 500ユーザーはこのローカル環境ではリソース限界に近く、テスト間の変動が大きい。300ユーザーを推奨
