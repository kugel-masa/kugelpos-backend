# Research: 端末サインインでの従業員 PIN の照合

**Feature**: 323-staff-pin-verification | **Date**: 2026-11-23

コードを読んで確かめた事実と、それに基づく決定を記録する。

---

## R-1 サービス間の資格情報

**事実**
- `kugel_common.utils.service_auth.create_service_token(tenant_id, service_name)` が、`is_service_account: True`・`tenant_id`・`service` を持つ 5 分間の JWT を発行する。cart・journal・report がすでに使っている
- `kugel_common.security.get_service_account_info` は FastAPI の依存で、トークンを検証し、`is_service_account` が無ければ 403 を返す。`oauth2_scheme` は `auto_error=False` なので、`Authorization` ヘッダが無い（API キーだけの）ときはトークンが `None` のまま `verify_token` に渡り、その検証失敗で 401 になる
- `get_service_account_info` は claim の `service` を見ない。サービスアカウントのトークンなら、どのサービスのものでも通る
- 端末の JWT（`token_type: terminal`）・利用者の JWT・スーパーユーザーは `is_service_account` を持たないので 403 になる
- cart・journal・report・stock がすでにサービスアカウントのトークンを使っている
- `verify_tenant_id(tenant_id, claim_tenant_id, logger)` がパスと claim のテナントの一致を検査する

**決定**: 照合のエンドポイントは `get_service_account_info` に依存し、`verify_tenant_id` でテナントを検査する。terminal は `create_service_token(tenant_id, "terminal")` で呼ぶ。呼び出し元のサービスは限定しない（ログに claim の `service` を残す）。

**代替案**: 端末の JWT / API キーで呼ぶ（今の `get_staff_by_id_async` と同じ）→ 却下。照合が端末の資格情報で直接呼べると、照合そのものが総当たりの入り口になる（spec FR-006）。

---

## R-2 内部用エンドポイントの置き場所

**事実**
- master-data には内部用（`/internal`）のルーターがまだ無い。ルーターは `app/main.py` で `prefix="/api/v1"` を付けて登録している
- API 命名規約（`.claude/rules/api-naming-convention.md`）は、アクションは `POST`、複合語はハイフン区切り

**決定**: 新しいルーター `app/api/v1/internal.py`（`prefix="/internal"`）を作り、`POST /api/v1/internal/tenants/{tenant_id}/staff/{staff_id}/verify` を置く。`main.py` で他と同じく `/api/v1` の下に登録する。

**代替案**
- 公開の staff ルーターに置く → 却下。公開 API と内部 API の区別が付かず、将来ゲートウェイで内部用だけを塞ぐことができない
- `verify-pin` → 却下。PIN を登録していない従業員でも成功する（PIN だけの照合ではなく、従業員の認証）ので `verify` とする

---

## R-3 従業員の削除と状態

**事実**
- master-data の `StaffMasterDocument` は `is_deleted` を持たない（`status` はあるが使われていない）。`delete_staff_async` は `delete_async` による物理削除
- `get_staff_by_id_async` は該当が無ければ `None` を返す

**決定**: 「従業員なし」は `None` の 1 通り。論理削除は考慮しない（spec を合わせて修正済み）。`status` による判定は入れない（今どこでも使っていないため、意味を新しく決めることになる）。

---

## R-4 端末側のエラーコード

**事実**
- terminal の `SignInOutException` は `406004`（`SIGN_IN_OUT_ERROR`、「担当者の登録状況を確認してください」）・HTTP 401
- 今、存在しない従業員でのサインインはすでにこの例外（406004 / 401）になる

**決定**: 失敗 3 種類はすべて既存の `SignInOutException`（406004 / 401）にする。存在しない従業員の応答は今と同じで、PIN の 2 種類がそれに揃う。新しいコードは採番しない。

**代替案**: 新しいコード（例: 406006）→ 却下。存在しない従業員の応答が変わり、互換が崩れる。3 種類を同じ応答にする（spec FR-015）にも既存のコードで足りる。

---

## R-5 依存先の障害

**事実**
- `HttpClientHelper` は 4xx を受けると即座に `HttpClientError(status_code=..., response=<httpx.Response>)` を投げる（再試行しない）。接続・タイムアウトの失敗は再試行の後に `HttpClientError(response=str(e))`（`status_code=None`）を投げる
- 今の `StaffMasterWebRepository` は、404 を `NotFoundException`、それ以外を `RepositoryException`（既定 404）にしている。サインインでは `NotFoundException` だけを捕まえているので、master-data の障害は `RepositoryException` として 404 で返っている
- terminal には `ExternalServiceException`（`407201` / 502）がある

**決定**
- commons の新しい照合メソッドは、応答本文の `userError.code`（エラー応答は移行期間中 `user_error` も持つが非推奨。`userError` を読み、無ければ `user_error` を見る）が `405701` / `405702` / `405703` のときだけ `StaffAuthenticationException`（理由を持つ）を投げる。それ以外（5xx、接続失敗、コードの無い 4xx、想定外の本文）は `RepositoryException` のまま投げる
- terminal は `StaffAuthenticationException` を `SignInOutException`（406004 / 401）に、`RepositoryException` と `ServiceUrlNotConfiguredError`（master-data の URL が設定されていない）を `ExternalServiceException`（407201 / 502）に写す
- 接続失敗・タイムアウトは `HttpClientHelper` が再試行してから失敗する（既定 3 回 × 30 秒）。既存の挙動のまま

**代替案**: HTTP ステータスで判定する → 却下。404 は「従業員なし」と「ルートが無い（master-data が古い）」を区別できない。業務コードだけを信じる。

---

## R-6 PIN の比較

**事実**: 平文で保存されている（#136 で据え置き）。PIN は文字列。

**決定**
- `secrets.compare_digest(stored.encode("utf-8"), given.encode("utf-8"))`。`str` のままだと ASCII 以外で `TypeError` になるため、bytes に揃える
- 比較は `StaffMasterService.verify_staff_async` の中の 1 か所だけ。ハッシュ化するときは、この比較と登録・更新の保存を差し替える

---

## R-7 応答とログに PIN を出さない

**事実**
- #211・#316・#318 により、要求本文のログ・リポジトリのログ・例外のメッセージは `mask_loggable` / `describe_exception` を通る。`pin` は秘密のキーとして伏せられる
- `HttpClientHelper` は 4xx の応答本文を WARNING（404）/ ERROR（それ以外）でログに出す。照合の失敗の応答本文には PIN が無い（`details` を持たない）ので漏れはない。ただし PIN 誤り（401）のたびに ERROR が出る（既存の挙動。下げるには commons の HTTP クライアント全体に関わるので、本フィーチャーでは変えない）
- **terminal のサインインのルートは、要求の Pydantic オブジェクトをそのまま DEBUG ログに出している**（`terminal/app/api/v1/terminal.py` の `logger.debug(f"...terminal_signin: {terminal_signin}")`）。`pin` を足すと `pin='1234'` がそのまま出る。要求本文のログ（ミドルウェア）と `HttpClientHelper` の送信ログは `pin` を伏せる

**決定**
- 照合の応答のスキーマは PIN の項目を持たない（除外ではなく、型に無い）
- 失敗は `details` を持たない。メッセージにも PIN を入れない
- 要求本文のスキーマの `pin` は既存の伏せ処理（キー名 `pin`）に掛かる。テストで確かめる
- terminal のサインインの DEBUG ログは `mask_loggable(terminal_signin)` にする。DEBUG を有効にしたテストで、一意で長い PIN がどのログにも出ないことを確かめる
- master-data の照合の失敗の例外は WARNING で記録する（認証の失敗は障害ではない）
- terminal の `SignInOutException` のメッセージは、理由を含めず 3 種類で同じにする（`Staff authentication failed: staff_id->{id}`）。応答の最上位の `message` にこれが出るため。理由は別のログ行（WARNING）に出す

---

## R-8 PIN を登録していない従業員に PIN が送られたら

**決定**: 無視して成功（spec の Clarifications）。比較は行わない。空文字の PIN が登録されている場合は「未登録」と同じ（`not staff.pin`）。空白だけの PIN は PIN として扱う（前後の空白は取り除かない）。

---

## R-9 既存の `get_staff_by_id_async` の扱い

**事実**: terminal で `StaffMasterWebRepository.get_staff_by_id_async` を使っているのはサインインだけ（`terminal_service.py:322`）。

**決定**: サインインは照合メソッドへ移す。`get_staff_by_id_async` は commons に残す（公開されたクラスのメソッドで、他の利用者がいうるため）。ただし「PIN を確かめずにサインインさせる経路を作らない」（spec FR-014）を、サインインのテストで固定する。

---

## R-10 既存の従業員のダミーの PIN

**事実**
- master-data の従業員の登録・更新の要求（`BaseStaffCreateRequest` / `BaseStaffUpdateRequest`）で `pin` は必須の `str`。PIN を使っていないテナントでも、API で登録した従業員にはダミーの PIN が入っていることが多い
- このリポジトリの e2e の準備データも、S001 を `"pin": "1234"` で登録している（master-data・report の `test_setup_data.py`）。約 25 か所のテストが従業員コードだけでサインインしている

**決定**
- 判定は「従業員マスタの PIN が空かどうか」のまま（spec の Clarifications）
- 登録・更新の `pin` を `Optional[str] = None` にする。登録では省略・空文字は「PIN なし」。更新では、省略すると今の PIN を変えず（`model_fields_set` に `pin` が無ければ更新の内容から外す）、`null`・空文字のときだけ消す。名前だけを直す更新で PIN が黙って消え、その従業員が PIN なしでサインインできるようになるのを防ぐ（実装時に判明）
- e2e の準備データでは S001 を PIN なしにし、既存のサインインのテストはそのまま使う。PIN の照合の e2e は、PIN 付きの従業員を別に登録して確かめる
- リリースノートで「PIN なしでサインインさせたい従業員は PIN を空にする」と告知する

**代替案**: テナントの設定や従業員ごとの印で照合を有効にする → 却下（spec の Clarifications）。判定の材料を増やさない

---

## R-11 内部の呼び出し先の URL

**事実**: 既存の `StaffMasterWebRepository.get_staff_by_id_async` は `f"/tenants/{self.tenant_id}/staff/{id}"` で、従業員コードを符号化せずにパスへ埋め込んでいる。

**決定**: 照合の呼び出しでは、従業員コード（とテナント）を `urllib.parse.quote(..., safe="")` で符号化してから埋め込む。`/` や `..` を含む従業員コードでも、呼び出し先のパスは変わらない（照合では「存在しない従業員」になる）。

---

## R-12 照合の成功の応答の項目

**事実**: commons の `StaffMasterDocument`（端末の `staff` に記録する型）は `tenant_id`・`store_code`・`id`・`name`・`pin`・`is_deleted` を持ち、`roles` を持たない。今、端末が使うのは `id` と `name` だけ。

**決定**: 照合の成功の応答は `id` と `name` だけにする。terminal は応答から `StaffMasterDocument(tenant_id=..., id=..., name=...)` を作って記録する（`pin` は持たない）。

---

## R-13 すでにサインインしている端末

**事実**: `/auth/token` は保存された端末の `staff` から claim を作り、照合し直さない（`terminal/app/api/v1/auth.py`）。

**決定**: 遡らない（spec の Edge Cases）。PIN の設定・変更・従業員の削除は、次のサインインから効く。

---

## R-14 列挙の限界

**事実**
- 照合の判定は、従業員の有無・PIN の有無で処理の経路が違う。比較を行うのは PIN を登録した従業員の枝だけ
- master-data の従業員の取得（単一・一覧）は端末の資格情報で呼べる

**決定**: 定数時間の比較が防ぐのは、PIN の一致の度合いの漏えいだけ。従業員の存在と名前は、処理時間や取得 API から調べられる（spec の Assumptions に明記）。ダミーの比較などで経路を揃えることはしない（取得 API で同じことが分かるため、効果が無い）。
