"""``app.exceptions`` imports on its own.

Its ``__init__`` re-exported ``ItemNotFoundException`` from
``kugel_common.exceptions``, which commons has never defined (it is a cart-local
exception). ``import app.exceptions``, and importing any module inside the
package, raised ImportError. Nothing in the app imported the package, so the
service still started; the only test that did patched the missing name into
commons first. The first app module to use a master-data exception would have
stopped the service from starting.

Runs in a fresh interpreter so no other test can have patched commons or cached
the package first.
"""

import os
import subprocess
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _import_in_fresh_interpreter(module: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "ALLOW_INSECURE_DEV_SECRETS": "true"}
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=SERVICE_ROOT,
        env=env,
        capture_output=True,
        check=False,  # the tests assert on returncode and show stderr
        text=True,
        timeout=60,
    )


def test_package_imports():
    result = _import_in_fresh_interpreter("app.exceptions")
    assert result.returncode == 0, result.stderr


def test_submodule_imports():
    result = _import_in_fresh_interpreter("app.exceptions.master_data_exceptions")
    assert result.returncode == 0, result.stderr


def test_every_reexported_name_resolves():
    import app.exceptions as package

    missing = [name for name in dir(package) if not name.startswith("_") and getattr(package, name, None) is None]
    assert missing == []
