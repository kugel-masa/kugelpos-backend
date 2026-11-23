# Data Model: 端末サインインでの従業員 PIN の照合

**Feature**: 323-staff-pin-verification | **Date**: 2026-11-23

保存する文書の形は変えない。新しく足すのは要求・応答のスキーマ、照合の結果、例外だけ。

---

## 1. 保存する文書（変更なし）

### master-data `master_staff`（`StaffMasterDocument`）

| 項目 | 型 | 備考 |
|---|---|---|
| tenant_id | str | |
| id | str | 従業員コード |
| name | str? | |
| pin | str? | 平文（#136 で据え置き）。`None` または空文字は「未登録」 |
| status | str? | 使っていない。照合では見ない |
| roles | list | |

削除は物理削除。

### terminal `info_terminal`（`TerminalInfoDocument.staff`）

サインインした従業員。`pin` は持たせない（#296 のまま）。照合の応答から作るので、もともと PIN を持たない。

---

## 2. 照合の判定（master-data `StaffMasterService.verify_staff_async`）

```text
staff = repository.get_staff_by_id_async(staff_id)

staff is None                       → StaffVerifyStaffNotFoundException  (405701)
not staff.pin                       → 成功（送られた PIN は無視）
not pin                             → StaffVerifyPinRequiredException    (405702)
not compare_digest(staff.pin, pin)  → StaffVerifyPinMismatchException    (405703)
それ以外                              → 成功
```

成功の枝は「未登録」と「一致」の 2 つだけ。比較はここだけで行う（spec FR-009）。

---

## 3. スキーマ

### master-data 要求 `StaffVerifyRequest`

| 項目（JSON） | 型 | 必須 | 備考 |
|---|---|---|---|
| pin | str? | いいえ | 省略・`null`・空文字はいずれも「PIN なし」 |

### master-data 応答 `StaffVerifyResponse`（`ApiResponse.data`）

| 項目（JSON） | 型 | 備考 |
|---|---|---|
| id | str | 従業員コード |
| name | str? | |

`pin` の項目は型に無い。`roles`・`tenant_id`・`status` も返さない（端末が記録する `StaffMasterDocument` は `roles` を持たず、使うのは `id` と `name` だけ。R-12）。

### master-data 要求 `BaseStaffCreateRequest` / `BaseStaffUpdateRequest`（変更）

| 項目（JSON） | 型 | 必須 | 変更 |
|---|---|---|---|
| pin | str? | いいえ | **必須から任意へ**。登録: 省略・`null`・空文字は「PIN なし」。更新: 省略は今の PIN を変えない、`null`・空文字は PIN を消す（R-10） |

### terminal 要求 `TerminalSignInRequest`

| 項目（JSON） | 型 | 必須 | 備考 |
|---|---|---|---|
| staffId | str | はい | 既存 |
| pin | str? | いいえ | **新規**。省略した要求は今と同じ形で受け付ける |

---

## 4. 例外とエラーコード

### master-data（新規・`405701`〜`405703`、日本語・英語のメッセージ）

| 例外 | コード | HTTP | 意味 |
|---|---|---|---|
| StaffVerifyStaffNotFoundException | 405701 | 404 | 従業員が存在しない |
| StaffVerifyPinRequiredException | 405702 | 401 | PIN を登録した従業員に PIN が無い・空 |
| StaffVerifyPinMismatchException | 405703 | 401 | PIN が一致しない |

いずれも `details` を持たず、メッセージに PIN を入れない。WARNING で記録する（認証の失敗は障害ではない）。

### commons（新規）

| 例外 / 列挙 | 備考 |
|---|---|
| `StaffAuthenticationFailure`（列挙） | `staff_not_found` / `pin_required` / `pin_mismatch`。405701 / 405702 / 405703 に 1 対 1 |
| `StaffAuthenticationException` | `reason: StaffAuthenticationFailure` を持つ。照合が業務上の失敗を返したときだけ投げる |

その他の失敗は既存の `RepositoryException`。

### terminal（既存を使う）

| 起きたこと | 例外 | コード / HTTP |
|---|---|---|
| `StaffAuthenticationException`（理由を問わず） | SignInOutException | 406004 / 401。メッセージは `Staff authentication failed: staff_id->{id}`（理由を含めない） |
| `RepositoryException`・`ServiceUrlNotConfiguredError`（照合を判定できない） | ExternalServiceException | 407201 / 502 |
