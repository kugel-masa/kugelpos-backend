#!/bin/bash
# Host-side setup the test runners need but the base image does not provide.
set -euo pipefail

# kugel_common's receipt formatting sets LC_ALL to ja_JP.UTF-8. The service images
# generate it (see each Dockerfile), but unit and integration tests run on the
# host, where an unknown locale fails with "unsupported locale setting".
if ! locale -a 2>/dev/null | grep -qi '^ja_JP\.utf8$'; then
    sudo sed -i 's/^# *ja_JP.UTF-8 UTF-8/ja_JP.UTF-8 UTF-8/' /etc/locale.gen
    grep -q '^ja_JP.UTF-8 UTF-8' /etc/locale.gen || echo 'ja_JP.UTF-8 UTF-8' | sudo tee -a /etc/locale.gen >/dev/null
    sudo locale-gen
fi

# The cross-service e2e suite runs from its own venv, which the per-service
# runners do not install.
if command -v pipenv >/dev/null 2>&1; then
    (cd tests/e2e && PIPENV_IGNORE_VIRTUALENVS=1 pipenv sync --dev)
fi
