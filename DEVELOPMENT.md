# gRPC実装 開発ガイド

## 作業環境

**ブランチ**: `feature/21-grpc-item-master-communication`
**Worktree**: `/home/masa/proj/kugelpos-stpos/worktrees/021-grpc-implementation`
**関連Issue**: #21 - 本番環境でのgRPC適用: cart-master-data間通信の最適化

## 開始方法

```bash
# 作業ディレクトリに移動
cd /home/masa/proj/kugelpos-stpos/worktrees/021-grpc-implementation

# ブランチ確認
git branch --show-current
# → feature/21-grpc-item-master-communication

# 実装プラン確認
cat grpc_implementation_plan.md
```

## 実装ステップ

詳細は `grpc_implementation_plan.md` を参照してください。

### クイックスタート

1. **環境準備**
   ```bash
   cd services/commons
   # __about__.py のバージョンを 0.1.29 に更新
   ```

2. **Protocol Buffers定義作成**
   ```bash
   mkdir -p services/protos
   # item_service.proto を作成
   ```

3. **実装プランに従って作業を進める**
   - Phase 1: 環境準備
   - Phase 2: Protocol Buffers定義
   - Phase 3: gRPCサーバー実装 (master-data)
   - Phase 4: gRPCクライアント実装 (cart)
   - Phase 5: テスト・検証
   - Phase 6: ドキュメント作成

## 目標

- 平均応答時間: 340ms → 177ms (48.7%短縮)
- Master-data通信: 130-150ms → 2-5ms (30倍高速化)
- リソース効率: ワーカー数 20 → 16 (20%削減)

## 参考資料

- **実装プラン**: `grpc_implementation_plan.md`
- **GitHub Issue**: https://github.com/kugel-masa/kugelpos-stpos/issues/21
- **元実装**: `feature/20-cart-performance-testing` ブランチ (コミット 4f6643c)

## 進捗確認

実装の進捗は `grpc_implementation_plan.md` のチェックリストで管理してください。
