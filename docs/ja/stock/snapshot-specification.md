# Stock Service スナップショット作成仕様書

## 概要

スナップショット機能は、特定時点での店舗の全在庫状態を記録する機能です。これにより、在庫の履歴追跡、監査、レポート作成、在庫推移分析が可能になります。

## スナップショットの目的

### 1. 監査証跡
- 特定日時の正確な在庫状態の記録
- 内部監査や外部監査への対応
- コンプライアンス要件の充足

### 2. レポーティング
- 日次・週次・月次の在庫レポート
- 在庫推移の分析
- 在庫回転率の計算

### 3. 在庫照合
- 実地棚卸との照合
- システム在庫と実在庫の差異分析
- 在庫ロスの特定

### 4. データ復旧
- 障害時の在庫状態の復元参考情報
- 過去の特定時点の在庫確認

## データ構造

### StockSnapshotDocument

スナップショットのメインドキュメント構造：

```python
{
    "tenant_id": "tenant001",        # テナントID
    "store_code": "store001",        # 店舗コード
    "total_items": 150,              # 商品種類数
    "total_quantity": 5250.0,        # 在庫数量合計
    "stocks": [                      # 商品別在庫詳細
        {
            "item_code": "ITEM001",
            "quantity": 148.0,
            "minimum_quantity": 25.0
        },
        # ... 他の商品
    ],
    "created_by": "system",          # 作成者
    "created_at": "2024-01-01T00:00:00Z",  # 作成日時
    "updated_at": "2024-01-01T00:00:00Z"   # 更新日時
}
```

### StockSnapshotItem

各商品の在庫情報を格納する埋め込みドキュメント：

| フィールド | 型 | 説明 |
|-----------|---|------|
| item_code | string | 商品コード |
| quantity | float | スナップショット時点の在庫数量 |
| minimum_quantity | float | 最小在庫閾値 |

## スナップショット作成プロセス

### 1. 作成フロー

```
[APIリクエスト受信]
    ↓
[認証・権限確認]
    ↓
[全在庫データ取得] ← 最大10,000件の制限
    ↓
[スナップショットデータ構築]
    │
    ├─ 商品ごとの在庫情報を収集
    ├─ 合計商品数をカウント
    └─ 在庫数量の合計を計算
    ↓
[MongoDBへ保存]
    ↓
[レスポンス返却]
```

### 2. 実装詳細

```python
# SnapshotService.create_snapshot_async()の処理フロー

1. 店舗の全在庫を取得
   - tenant_idとstore_codeで絞り込み
   - 最大10,000件まで取得（ハードコード制限）

2. スナップショットアイテムの生成
   - 各在庫レコードをStockSnapshotItemに変換
   - 在庫数量の合計を計算

3. スナップショットドキュメントの作成
   - 全商品数、合計数量、商品詳細を設定
   - 作成者情報とタイムスタンプを付与

4. データベースへの保存
   - MongoDBのstock_snapshotsコレクションに保存
   - インデックスによる高速化
```

## パフォーマンス特性

### 現在の実装

| 項目 | 仕様 |
|-----|------|
| 最大取得件数 | 10,000商品 |
| 処理方式 | 同期的一括処理 |
| メモリ使用量 | 商品数に比例して増加 |
| トランザクション | 単一トランザクション |
| 並列処理 | なし |

### パフォーマンス考慮事項

1. **メモリ使用量**
   - 10,000商品で約5-10MBのメモリを使用
   - 大規模店舗では注意が必要

2. **実行時間**
   - 商品数に比例して増加
   - 1,000商品: 約0.5-1秒
   - 10,000商品: 約5-10秒

3. **データベース負荷**
   - 全在庫の一括読み込みによる一時的な負荷
   - インデックスによる最適化済み

## API仕様

### スナップショット作成

**エンドポイント:** `POST /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

**リクエスト:**
```json
{
    "createdBy": "user001"  // オプション（デフォルト: "system"）
}
```

**レスポンス:**
```json
{
    "success": true,
    "code": 201,
    "message": "スナップショットの作成に成功しました",
    "data": {
        "id": "507f1f77bcf86cd799439014",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "totalItems": 150,
        "totalQuantity": 5250.0,
        "stocks": [...],
        "createdBy": "user001",
        "createdAt": "2024-01-01T00:00:00Z"
    }
}
```

### スナップショット一覧取得

**エンドポイント:** `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

**クエリパラメータ:**
- `skip`: スキップ件数（デフォルト: 0）
- `limit`: 取得件数（デフォルト: 20、最大: 100）

### スナップショット詳細取得

**エンドポイント:** `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

## 保持ポリシーとクリーンアップ

### 保持期間

| 設定項目 | デフォルト値 | 説明 |
|---------|------------|------|
| retention_days | 90日 | スナップショットの保持期間 |

### クリーンアップ処理

```python
# 90日以前のスナップショットを削除
await snapshot_service.cleanup_old_snapshots_async(
    tenant_id="tenant001",
    store_code="store001",
    retention_days=90
)
```

**重要事項:**
- 自動クリーンアップは未実装
- 手動での定期的なクリーンアップが必要
- 店舗単位でのクリーンアップのみ対応

## 使用シナリオ

### 1. 日次棚卸し

```bash
# 毎日午前0時にスナップショットを作成
curl -X POST "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot" \
  -H "Authorization: Bearer {token}" \
  -d '{"createdBy": "daily_batch"}'
```

### 2. 月次在庫レポート

```bash
# 月初のスナップショットを取得
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot?limit=31" \
  -H "Authorization: Bearer {token}"
```

### 3. 在庫照合

実地棚卸との照合時：
1. 棚卸開始時にスナップショット作成
2. 実地棚卸実施
3. スナップショットと実地数量を比較
4. 差異がある場合は在庫調整

## 制限事項と注意点

### 現在の制限

1. **商品数制限**
   - 最大10,000商品まで
   - これを超える店舗では一部商品が含まれない

2. **自動化未対応**
   - スケジュール実行機能なし
   - 手動またはバッチからのAPI呼び出しが必要

3. **増分スナップショット未対応**
   - 常に全在庫をキャプチャ
   - 差分のみの記録は不可

4. **圧縮機能なし**
   - データは非圧縮で保存
   - 大規模店舗ではストレージ使用量に注意

5. **リアルタイム性**
   - スナップショット作成中の在庫変更は反映されない
   - 完全な一貫性は保証されない

### 推奨事項

1. **作成タイミング**
   - 営業時間外または取引の少ない時間帯
   - 日次: 午前0時〜3時
   - 週次: 日曜日の深夜

2. **保持期間**
   - 日次スナップショット: 30日
   - 週次スナップショット: 90日
   - 月次スナップショット: 1年

3. **監視**
   - スナップショットのサイズ監視
   - 作成時間の監視
   - 失敗時のアラート設定

## エラー処理

### エラーケース

| エラー | 原因 | 対処 |
|-------|------|------|
| メモリ不足 | 商品数が多すぎる | バッチ処理の実装 |
| タイムアウト | 処理時間が長い | タイムアウト値の調整 |
| 権限エラー | 認証・認可の失敗 | 権限の確認 |
| データベースエラー | MongoDB接続問題 | 接続設定の確認 |

### エラーレスポンス例

```json
{
    "success": false,
    "code": 500,
    "message": "スナップショットの作成に失敗しました",
    "data": null,
    "operation": "create_snapshot"
}
```

## 将来の拡張計画

### 1. 自動スケジューリング
- Cronジョブ統合
- 設定可能なスケジュール
- 複数スケジュールのサポート

### 2. 増分スナップショット
- 前回からの差分のみ記録
- ストレージ使用量の削減
- 高速化

### 3. 圧縮とアーカイブ
- 古いスナップショットの圧縮
- 外部ストレージへのアーカイブ
- 自動復元機能

### 4. 分析機能
- スナップショット間の差分分析
- 在庫推移グラフ
- 異常検知アラート

### 5. パフォーマンス改善
- ストリーミング処理
- 並列処理
- 商品数制限の撤廃

## ベストプラクティス

### 1. 定期実行の実装例

```python
# 外部スケジューラー（例：Apache Airflow）から呼び出し
import asyncio
from datetime import datetime

async def create_daily_snapshot(tenant_id: str, store_code: str):
    """日次スナップショットを作成"""
    created_by = f"daily_batch_{datetime.now().strftime('%Y%m%d')}"
    
    try:
        response = await stock_api.create_snapshot(
            tenant_id=tenant_id,
            store_code=store_code,
            created_by=created_by
        )
        logger.info(f"スナップショット作成成功: {response.data.id}")
    except Exception as e:
        logger.error(f"スナップショット作成失敗: {str(e)}")
        # アラート送信
```

### 2. 保持期間管理の実装例

```python
async def manage_snapshot_retention():
    """スナップショットの保持期間を管理"""
    configs = [
        {"pattern": "daily_batch_*", "retention_days": 30},
        {"pattern": "weekly_batch_*", "retention_days": 90},
        {"pattern": "monthly_batch_*", "retention_days": 365},
    ]
    
    for config in configs:
        # パターンに一致するスナップショットをクリーンアップ
        deleted_count = await cleanup_snapshots_by_pattern(
            pattern=config["pattern"],
            retention_days=config["retention_days"]
        )
        logger.info(f"削除されたスナップショット: {deleted_count}件")
```

### 3. 監視とアラート

```python
# スナップショット作成の監視
async def monitor_snapshot_creation():
    """スナップショット作成を監視"""
    # 最新のスナップショットを確認
    latest_snapshot = await get_latest_snapshot(tenant_id, store_code)
    
    if not latest_snapshot:
        send_alert("スナップショットが見つかりません")
        return
    
    # 24時間以上古い場合はアラート
    age_hours = (datetime.utcnow() - latest_snapshot.created_at).total_seconds() / 3600
    if age_hours > 24:
        send_alert(f"最新のスナップショットが{age_hours:.1f}時間前です")
```

スナップショット機能は、在庫管理における重要な監査・分析ツールとして、適切な運用により大きな価値を提供します。