#!/bin/bash
# Host-side setup the build and the test runners need but the base image and a
# fresh clone do not provide.
set -euo pipefail

SERVICES=(account terminal master-data cart journal report stock)

# kugel_common's receipt formatting sets LC_ALL to ja_JP.UTF-8. The service images
# generate it (see each Dockerfile), but unit and integration tests run on the
# host, where an unknown locale fails with "unsupported locale setting".
if ! locale -a 2>/dev/null | grep -qi '^ja_JP\.utf8$'; then
    sudo sed -i 's/^# *ja_JP.UTF-8 UTF-8/ja_JP.UTF-8 UTF-8/' /etc/locale.gen
    grep -q '^ja_JP.UTF-8 UTF-8' /etc/locale.gen || echo 'ja_JP.UTF-8 UTF-8' | sudo tee -a /etc/locale.gen >/dev/null
    sudo locale-gen
fi

# Every service Pipfile and Dockerfile takes kugel_common from
# services/<service>/commons/dist, which is git-ignored, so a fresh clone has
# no wheel: neither the venvs nor the images can be built until it exists.
if ! command -v hatch >/dev/null 2>&1; then
    pipx install hatch
fi
./scripts/run_build_common.sh
./scripts/run_copy_common.sh

# Each venv is synced from its Pipfile.lock, which never rewrites the lock. The
# test runners call `pipenv run` and fail on a missing venv with
# ModuleNotFoundError rather than a hint to install one.
export PIPENV_IGNORE_VIRTUALENVS=1
for dir in services/commons "${SERVICES[@]/#/services/}" tests/e2e; do
    echo "pipenv sync --dev: $dir"
    (cd "$dir" && pipenv sync --dev)
done
