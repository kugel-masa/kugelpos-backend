# Implementation Plan: 処理できなかったイベントを見えるようにし、直したあとに流し直せるようにする

**Branch**: `230-dead-letter-handling` | **Date**: 2026-11-25（2026-11-27 改訂: 受け手の中で諦める形） | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/230-dead-letter-handling/spec.md`

## Summary

report・journal・stock が受け直しても処理できないイベントを、受け手自身が諦めて記録し、1 回だけ通知し、API で一覧・照会・流し直し・破棄できるようにする。受け直しのたびの重大エラーの通知はやめる。

- **どこでデッドレターにするか**: 受け手の処理が失敗するたびに `dead_letter` の回数を足し、一続きの失敗が 17 回に達したら、同じ更新で「未対応」にして CloudEvent を保存し、RabbitMQ には SUCCESS を返す。17 回は Dapr の受け直しの上限（19 回）より 2 回手前（R-1）
- **最後の受け皿**: 記録が書けないとき（MongoDB の障害）とテナントのわからないイベントは、起きたその場で知らせ（プロセスの中の 5 分の窓、R-5c）、今までどおり受け直しを使い切って `dlq-*` に移る。期限は付けない。戻す手順は shovel で受け手の購読のキューへ（R-12、R-13）
- **Dapr の版に依存しない**: 新しいコンポーネント・購読・ルートは無い。Azure Container Apps の Dapr 1.16.4 でも同じに動く（R-1）
- **持ち主**: 受け手のサービスがそれぞれ持つ。共通の部分は `kugel_common.dead_letter`（R-2）
- **本体と購読の分け方**: 購読の処理の本体は処理の結果（処理できた／処理済み／捨てた／失敗）だけを返す。失敗の記録と Dapr への応答は購読の薄いルートが決める（R-3）
- **流し直し**: 受け手のサービスの中で、本体を直接・同期で呼ぶ。ほかの受け手には届かない。まとめては受け付けて裏で流す（R-3、R-7）
- **同時の操作**: 記録の `_id` はイベント ID。失敗の記録と諦める判断は 1 回の `find_one_and_update`（変更前を返す、外から来た値は `$literal`）。流し直しは `replay_claim_id` で引き受け、結果もその ID を条件に書く（R-4、R-7）
- **通知**: 「未対応」になったときに送る。送れたら `notified_at`。送り損ねは掃除が送り直す（まれに 2 回）。5 分の窓で 9 件まで 1 件ずつ、10 件目でまとめる（R-5、R-5a）
- **定期の掃除**: 5 分ごとに、受け直しが終わったのに「失敗中」のまま残った記録（数え損ね）を「未対応」に上げ、送り損ねた通知を送り直す（R-14）
- **中身と秘密**: 照会の `message` はマスクして返す。`last_error` はマスクして切る。Slack には例外の型だけ（R-15）
- **権限**: 人の利用者の JWT だけ。端末・サービスアカウントの JWT は 403（R-9）

## Technical Context

**Language/Version**: Python 3.12+（ほかのサービスと同じ）
**Primary Dependencies**: FastAPI、Pydantic v2、PyMongo async API、Dapr（pub/sub、RabbitMQ。設定は変えない）、`kugel_common`（`AbstractRepository`、`slack_notifier`、`verify_token`、`verify_tenant_id`。新しく `get_user_with_token`）。新しい外部の依存は無い
**Storage**: report・journal・stock のテナントごとの DB に `dead_letter` と `dead_letter_alert` を新設（data-model.md）
**Testing**: pytest。unit（状態の表のすべてのマス、諦める判断、本体の結果と購読の応答、通知の窓、掃除、マスク、ルーター、権限、受け直しの予算）、integration（実際の MongoDB で、パイプラインの更新・`$` を含む中身・同時の失敗で「未対応になった」が 1 回・条件付きの更新・引き受け直しと遅れた結果・掃除・TTL の索引・流し直し）、e2e（スタックで、必ず失敗するイベントが記録され、流し直せる。記録が書けないときは `dlq-*` に移る）
**Target Platform**: Linux のコンテナ（docker-compose、Azure Container Apps。Azure への配備は別に扱う）
**Project Type**: 既存のマイクロサービス（web service）
**Performance Goals**: 受け手が諦めてから 1 分以内に記録と通知（SC-001。同じ処理の中で行う）
**Constraints**: 諦める回数は Dapr の受け直しの上限より 2 回以上少ない（予算のテストで確かめる）。中身をログ・通知に出さない（#211）。成功の経路に書き込みを足さない。流し直し 1 件は 30 秒まで、まとめては 100 件まで（裏で処理）。記録と Slack の送信は 5 秒まで
**Scale/Scope**: 記録が「未対応」になるのは失敗し続けたイベントだけで、ふだんは 0 件。受け手の不具合では一度に多数（通知の窓でまとめる）。失敗中の記録は、失敗のたびに 1 回の更新

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 判定 |
|---|---|
| 0. 言語規則（成果物は日本語、コード・コメント・ログは英語） | 満たす |
| ほかの原則 | 憲章に未記入（テンプレートのまま）。CLAUDE.md の規約（リポジトリの形、async、型ヒント、テストの 3 層、エラーコードの範囲）に従う |

Phase 1 のあとも違反なし。

## Project Structure

### Documentation (this feature)

```text
specs/230-dead-letter-handling/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dead-letter-api.md
│   └── dead-letter-recording.md
└── tasks.md
```

### Source Code (repository root)

```text
services/
├── commons/src/kugel_common/dead_letter/        # 新規
│   ├── __init__.py
│   ├── document.py          # DeadLetterDocument、状態の定数、要約、諦める回数（DEAD_LETTER_GIVE_UP_AFTER_FAILURES）
│   ├── repository.py        # 失敗の記録（諦める判断を含む）、条件付きの引き受け・確定・破棄、一覧、索引
│   ├── outcome.py           # HandlerOutcome（PROCESSED / ALREADY_PROCESSED / DROPPED / FAILED）
│   ├── failure.py           # record_failure（記録 → 判断 → 通知。GAVE_UP / ALREADY_RECORDED / KEEP_RETRYING）
│   ├── alerts.py            # 通知の本文と窓（dead_letter_alert）
│   ├── unrecordable.py      # notify_unrecordable（記録できないときの知らせ、プロセスの中の 5 分の窓）
│   ├── sweep.py             # 定期の掃除（取り残された失敗中、送り損ねた通知）
│   ├── replay.py            # 流し直し（引き受け → 処理（30 秒まで）→ claim を条件に結果）
│   └── router.py            # API を作る関数（サービスごとのエラーコードと処理の本体を受け取る）
├── commons/src/kugel_common/security.py         # get_user_with_token（端末・サービスアカウントの JWT は 403）
├── commons/tests/unit/test_dead_letter_*.py
├── report/app/
│   ├── main.py                     # ルーター、定期の掃除の起動
│   ├── api/v1/tran.py              # handle_log を本体と購読のルートに分ける、ルートで record_failure、テナントが無い分岐で知らせる
│   ├── services/log_service.py     # Slack を外す（3 か所）
│   ├── database/database_setup.py  # 索引
│   └── exceptions/report_error_codes.py ほか   # 413009
├── journal/app/                    # report と同じ（411007）
├── stock/app/                      # handle_transaction_log の本体の切り出し、record_failure、ルーター、索引、414404
├── */tests/{unit,integration}/test_dead_letter_*.py
├── report/tests/unit/test_pubsub_redelivery_budget.py   # 諦める回数が maxRetries + 1 より 2 回以上少ない
tests/e2e/test_dead_letter_journey.py            # サービス横断
docs/{en,ja}/general/error_code_spec.md、dapr_components.md、各サービスの api-specification.md、運用の手順（dlq-* の見つけ方と戻し方）
```

**Structure Decision**: 共通の部分は commons に置き、3 サービスは配線（処理の本体の切り出し、失敗の分岐での `record_failure`、ルーターの取り付け、エラーコード）だけにする。Dapr のコンポーネントと RabbitMQ の設定は変えない。commons を変えるので、3 サービスの Pipfile.lock の commons を更新する（既存の手順どおり `./scripts/build.sh commons`）。

## Phase の流れ

1. **commons**: `dead_letter` パッケージ（文書・本体の結果・リポジトリ・失敗の記録・通知・記録できないときの知らせ・掃除・流し直し・ルーター）、`get_user_with_token`、ユニットテスト（状態の表のすべてのマス、諦める判断、窓）
2. **受け手の処理の分割**: 3 サービスの購読の処理を、処理の結果だけを返す本体と、購読の薄いルートに分ける。ルートが `FAILED` で `record_failure` を呼び、返り値で SUCCESS / RETRY を返す。report・journal の Slack を外す
3. **配線**: ルーター、掃除の起動、索引、エラーコード、受け直しの予算のテスト
4. **統合テスト**: 実際の MongoDB で、失敗中 → 未対応（17 回目）、同時の失敗で「未対応になった」が 1 回、未対応のあとの失敗はすぐ SUCCESS、記録が書けないと RETRY、流し直しの失敗で記録が消えない、同時の流し直し、引き受け直しと遅れた結果、通知の失敗で `notified_at` が空、破棄、TTL の索引、窓の同時の更新
5. **e2e**: 諦める回数と受け直しを小さくした設定を上書きで入れ（`tests/e2e` 用の compose の上書きと resiliency）、テストから入れて戻せる故障（精算実績の文書を壊して戻す）で、必ず失敗するイベントが記録され、流し直すと処理される。閉設ログ（#343）の場面、2 つの受け手が失敗する場面。MongoDB を止めると知らせが 1 回届き、`dlq-*` に移り、R-13 の手順で戻すと記録される
6. **文書**: エラーコード、Dapr の文書（受け手が諦めて記録すること、`dlq-*` は最後の受け皿）、API の文書、運用の手順（`dlq-*` の見つけ方と戻し方）。Azure への配備は別に扱う

## Complexity Tracking

| 増えるもの | 要る理由 | 簡単な代わりを退けた理由 |
|---|---|---|
| 「失敗中」の記録（成功すると TTL で消える） | 失敗の理由と回数は受け手の中にしか無い（R-4）。諦める判断にも回数が要る | 回数を持たないと、いつ諦めるかを決められない（Dapr は回数を渡さない） |
| 諦める回数と Dapr の上限の結びつき | 上限に先に届くと `dlq-*` に落ちる（R-1） | 予算のテストで、設定が離れたら落ちるようにする |
| 定期の掃除（各サービス、5 分ごと） | 数え損ねたイベントと送り損ねた通知を、人の目に頼らずに拾う（R-14） | 成功の経路で `failing` を消すと、成功の経路に読み書きが増える |
| 流し直しの `replay_claim_id` | 引き受けの期限を過ぎたあとの遅れた結果を断る（R-7） | 期限だけでは、2 人が同じ記録の結果を後から上書きできる |
