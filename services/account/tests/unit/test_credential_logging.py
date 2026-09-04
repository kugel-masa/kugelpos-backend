# Copyright 2026 masa@kugel
"""Registration must not write the stored credential down (issue #136).

`UserAccountInDB` carries `hashed_password`. The plaintext is replaced by
`"*****"` before the document is built, so the credential-sentinel scan does
not see this line - that scan plants a plaintext password and looks for it.
A bcrypt hash is not the plaintext, but it is offline-crackable material and
does not belong in a log either.

What made this one survive the masking work on issue #211: the shape is
`f"...{user_info.model_dump()}"` - a method call, where every sweep looked for
a bare `{name}` on one line. An AST pass over the repo for that shape found
exactly two, and the other one carries no credential.

Reaching the log itself means standing up the registration endpoint and its
database, so the call site is source-checked and the masking it relies on is
exercised directly. The e2e sentinel scan walks the endpoint for real - it
just cannot see this line, because it plants a plaintext password and this
line carries the hash.
"""

from datetime import datetime

from app.api.common.schemas import BaseUserAccountInDB
from kugel_common.utils.log_utils import mask_loggable

HASH = "$2b$12$SENTINELhashSENTINELhashSENTINELhashSENTINELhash"


def _user() -> BaseUserAccountInDB:
    return BaseUserAccountInDB(
        username="admin",
        password="*****",  # what the endpoint stores in its place
        tenant_id="T0001",
        hashed_password=HASH,
        is_superuser=True,
        is_active=True,
        created_at=datetime(2026, 9, 4),
    )


def test_the_stored_hash_is_not_written_to_the_log():
    masked = mask_loggable(_user())

    assert HASH not in str(masked), "the stored password hash is readable in the log"
    # The record stays identifiable, or the line is not worth emitting.
    assert "admin" in str(masked)
    assert "T0001" in str(masked)


def test_the_register_path_does_not_dump_the_document_raw(caplog):
    # The call site rather than the helper: `mask_loggable` being correct does
    # not help if the line still interpolates `user_info.model_dump()`.
    import inspect

    from app.api.v1 import account

    source = inspect.getsource(account)
    assert "user_info->{user_info.model_dump()}" not in source, (
        "the user document is logged raw, hashed_password included"
    )
    assert "mask_loggable(user_info)" in source


def test_masking_leaves_the_document_the_caller_stores_alone():
    # This runs immediately before `insert_one(user_info.model_dump())`.
    user = _user()

    mask_loggable(user)

    assert user.hashed_password == HASH, "the document about to be stored was modified"
