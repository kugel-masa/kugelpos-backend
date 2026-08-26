# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
HTTP request handling limits shared by every service (issue #195).

The body ceiling is enforced outermost, ahead of authentication, so it cannot
be a per-route decision — which makes it the one number that has to fit the
largest legitimate request a service ever receives. It therefore has to be
settable per service rather than compiled in:

- cart carries the whole cart document on every mutating request in the
  client-carried design (#156). Measured against the running stack, a 999-line
  transaction with distinct SKUs sends 894 KB, and the first request refused
  is at 1,221 lines.
- report and journal serve the Dapr pub/sub tranlog subscribers from this same
  app. A refused event is retried and then dead-lettered, so a ceiling set too
  low loses the sale silently rather than failing it visibly. The same 999-line
  transaction publishes a 552 KB tranlog.
- master-data takes a whole collection in one body on two endpoints: the item
  book's categories -> tabs -> buttons tree (1 MB refused it at 5,950 buttons),
  and a setting's per-store/terminal values (3,000 stores x 5 terminals is
  750 KB).

Compression is not a way around it: the ceiling is enforced against the
decompressed size, so a gzipped body refused at 1,221 lines is refused at the
same line count when it travels as 22 KB on the wire.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class HttpRequestSettings(BaseSettings):
    """
    Request-handling limits every service carries.

    Attributes:
        MAX_REQUEST_BODY_BYTES: The largest request body this service will
            hold. Enforced as the body is delivered, ahead of authentication;
            larger is refused with 413. Services whose legitimate traffic is
            bigger than the default override it (see the module docstring).
    """

    MAX_REQUEST_BODY_BYTES: int = Field(
        default=1024 * 1024,
        description="Maximum request body size in bytes, compressed or not; larger is refused with 413.",
    )

    @field_validator("MAX_REQUEST_BODY_BYTES")
    @classmethod
    def _must_be_positive(cls, value: int) -> int:
        """Refuse to start on a ceiling that would reject everything.

        Zero or a negative number is not "no limit" — it is the opposite. The
        ceiling is enforced outermost, so at 0 every request carrying a body is
        answered 413 while bodyless health checks still pass: the service looks
        alive and serves nothing. A negative value refuses even the bodyless
        request, taking the service down completely. Both are one plausible
        typo away for an operator trying to disable the limit, so the failure
        belongs at startup rather than on the first sale.

        Declared as a validator rather than ``Field(gt=0)`` because a subclass
        that overrides the field with a bare ``Field(default=...)`` — which
        cart, master-data, report and journal all do — replaces the FieldInfo
        and would drop the constraint. Validators are collected by field name
        across the hierarchy, so this one survives the override.
        """
        if value <= 0:
            raise ValueError(
                f"MAX_REQUEST_BODY_BYTES must be a positive number of bytes, got {value}. "
                "There is no value that disables the ceiling; raise it instead."
            )
        return value
