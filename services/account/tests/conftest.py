# Copyright 2025 masa@kugel
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
Top-level conftest for account service tests.

Provides only environment-variable plumbing shared by integration and e2e
tiers. The HTTP client and DB cleanup fixtures now live in the per-tier
subdirectory conftests (tests/integration/, tests/unit/).

Unit tests override `set_env_vars` to a no-op in tests/unit/conftest.py.
"""
import logging
import logging.config
import os


# Module-level env bootstrap: must run BEFORE any test file imports the
# service app so app.config.settings sees the correct DB_NAME_PREFIX /
# SECRET_KEY etc. on first load. pytest auto-discovery of tests/unit/
# would otherwise cache settings defaults before set_env_vars fires,
# leading to integration-tier flakes.
from dotenv import load_dotenv as _load_dotenv

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_load_dotenv(os.path.join(_ROOT_DIR, '.env.test'), override=True)
os.environ.setdefault("DB_NAME_PREFIX", "db_account")
os.environ.setdefault("STORE_CODE", "5678")
os.environ.setdefault("TERMINAL_ID", f"{os.environ.get('TENANT_ID', 'T9999')}-5678-9")
import pytest
from dotenv import load_dotenv

logging.config.fileConfig("app/logging.conf")


@pytest.fixture(scope="session")
def set_env_vars():
    """Load .env.test and configure environment for integration/e2e tests."""
    from kugel_common.database import database as db_helper

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    load_dotenv(dotenv_path=dotenv_path, override=True)

    is_local = os.getenv("LOCAL_TEST") == "True"
    remote_server = os.getenv("REMOTE_URL")
    tenant_id = os.getenv("TENANT_ID")

    print("")
    print("---------------------------")
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"dotenv_path: {dotenv_path}")
    print(f"LOCAL_TEST: {is_local}")
    print(f"REMOTE_URL: {remote_server}")
    print(f"TENANT_ID: {tenant_id}")
    print("---------------------------")

    if is_local:
        os.environ["BASE_URL_ACCOUNT"] = "http://localhost:8000"
    else:
        os.environ["BASE_URL_ACCOUNT"] = f"https://account.{remote_server}"

    print(f"BASE_URL_ACCOUNT: {os.environ.get('BASE_URL_ACCOUNT')}")

    os.environ["DB_NAME_PREFIX"] = "db_account"
    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")

    yield

    del os.environ["BASE_URL_ACCOUNT"]
    del os.environ["DB_NAME_PREFIX"]
