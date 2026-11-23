# Contract: terminal サインイン（変更）

**Feature**: 323-staff-pin-verification

## エンドポイント（既存）

```
POST /api/v1/terminals/{terminal_id}/sign-in
```

認証は今と同じ（端末の JWT または API キー）。

## 要求

```json
{ "staffId": "S001", "pin": "1234" }
```

| 項目 | 必須 | 変更 |
|---|---|---|
| staffId | はい | なし |
| pin | いいえ | **新規**。省略した要求（`{"staffId": "S001"}`）は今と同じく受け付ける |

## 処理

1. 端末が無い → 今と同じ（`TerminalNotFoundException`）
2. すでにサインインしている → 今と同じ（`TerminalAlreadySignedInException`）。照合は呼ばない
3. commons の `StaffMasterWebRepository.verify_staff_async(staff_id, pin)` で照合する（サービスアカウントのトークンで呼ぶ。従業員コードは符号化してパスに埋め込む）
4. 成功 → 照合の応答（`id`・`name`。PIN を持たない）から端末の `staff` を作って記録し、サインインした端末情報を返す
5. 失敗 → 端末の状態を変えずに断る

## 失敗の応答

| 起きたこと | 応答 | ログ（WARNING / ERROR） |
|---|---|---|
| 照合が 405701 / 405702 / 405703 | 401 / `406004`（3 つとも同じメッセージ） | テナント・端末・従業員コード・理由（`staff_not_found` / `pin_required` / `pin_mismatch`） |
| master-data に届かない・5xx・想定外の応答 | 502 / `407201` | テナント・端末・従業員コードと「判定できなかった」こと |

- 401 / `406004` は、今の「存在しない従業員」の応答と同じ。PIN の 2 種類がこれに揃う
- 応答の最上位の `message` も 3 種類で同じ（`Staff authentication failed: staff_id->{id}`）。理由は応答に出さず、ログにだけ出す
- PIN の値は、応答にもログにも出さない。サインインの要求を記録する DEBUG ログも `pin` を伏せる

## 変わらないもの

- サインアウト、すでにサインインしている端末の扱い
- 端末情報の応答（従業員の PIN は含まない）
- すでにサインインしている端末は、その後に PIN が設定・変更されても遡って断られない

## 挙動の変化

PIN が入っている従業員は、PIN なし・誤った PIN では 401 / `406004` で断られる。これまでは従業員コードだけで通った。これまで登録・更新で PIN が必須だったため、ダミーの PIN が入っている従業員も多い。PIN なしでサインインさせたい従業員は、更新で `pin` に空文字または `null` を送って PIN を消す（リリースノートで告知）。
