# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from kugel_common.config.settings_app import AppSettings
from kugel_common.enums import RoundMethod
from kugel_common.config.settings_auth import AuthSettings
from kugel_common.config.settings_datetime import DatetimeSettings
from kugel_common.config.settings_tax import TaxSettings
from kugel_common.config.settings_stamp_duty import StampDutySettings
from kugel_common.config.settings_web import WebServiceSettings
from kugel_common.config.settings_http import HttpRequestSettings
from kugel_common.config.settings_database import DBCollectionCommonSettings, DBSettings
from app.config.settings_database import DBCollectionSettings
from app.config.settings_cart import CartSettings


class Settings(
    AppSettings,
    DatetimeSettings,
    TaxSettings,
    StampDutySettings,
    AuthSettings,
    WebServiceSettings,
    DBSettings,
    DBCollectionCommonSettings,
    DBCollectionSettings,
    CartSettings,
    HttpRequestSettings,
):
    # Override required fields with defaults
    MONGODB_URI: str = Field(default="mongodb://localhost:27017/?replicaSet=rs0")
    DB_NAME_PREFIX: str = Field(default="db_cart")

    # The client-carried design puts the whole cart document on every mutating
    # request (issue #156), so cart's largest legitimate body is the one that
    # sizes the ceiling. Measured against the running stack, a 999-line
    # transaction with distinct SKUs sends 894 KB - 85% of the 1 MB default,
    # and the first request refused is at 1,221 lines. Compressing does not
    # help: the ceiling is enforced against the decompressed size, so the same
    # transaction is refused at the same line count while travelling as 22 KB.
    # 4 MB leaves room for the item-master copies, longer names, image URLs and
    # discounts that a real basket carries (issue #195).
    MAX_REQUEST_BODY_BYTES: int = Field(default=4 * 1024 * 1024)

    @field_validator("ROUND_METHOD_FOR_DISCOUNT")
    @classmethod
    def _round_method_for_discount_is_known(cls, value: str) -> str:
        """Refuse a discount rounding method the discount logic cannot act on.

        The discount paths match this value exactly against RoundMethod. Any
        other value - `round` in lower case is enough - used to match nothing and
        fall through to the un-rounded amount, so discounts carried sub-yen
        fractions into line totals, the tax base and the tranlog with nothing in
        the logs. RoundMethod has no member meaning "do not round", so that was
        never what the setting asked for.

        Validated here rather than in commons' AppSettings: cart is the only
        service that reads it, so a mistyped value stops cart, not every service.
        """
        allowed = [method.value for method in RoundMethod]
        if value not in allowed:
            raise ValueError(
                f"ROUND_METHOD_FOR_DISCOUNT must be one of {allowed} (case-sensitive), got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _honour_deprecated_body_limit_name(self):
        """Let a deployment that set REQUEST_DECOMPRESS_MAX_BYTES keep working.

        The old name governed the same ceiling before it covered uncompressed
        bodies too (issue #195). Renaming it outright would silently drop an
        operator's override back to the default, so an explicit old-name value
        still wins; unset, it follows MAX_REQUEST_BODY_BYTES.
        """
        if self.REQUEST_DECOMPRESS_MAX_BYTES is None:
            self.REQUEST_DECOMPRESS_MAX_BYTES = self.MAX_REQUEST_BODY_BYTES
        else:
            # Checked here rather than left to HttpRequestSettings' validator:
            # assigning to a field does not re-validate it (validate_assignment
            # is off), so the old name would otherwise be the one way to get a
            # ceiling of 0 past the guard and refuse every request with a body.
            if self.REQUEST_DECOMPRESS_MAX_BYTES <= 0:
                raise ValueError(
                    "REQUEST_DECOMPRESS_MAX_BYTES must be a positive number of bytes, "
                    f"got {self.REQUEST_DECOMPRESS_MAX_BYTES}. There is no value that "
                    "disables the ceiling; raise it instead."
                )
            self.MAX_REQUEST_BODY_BYTES = self.REQUEST_DECOMPRESS_MAX_BYTES
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,  # Ignore empty values from .env file
        extra="allow",  # ← ignore ではなく allow を指定
    )


settings = Settings()
