#!/bin/bash
export PIPENV_IGNORE_VIRTUALENVS=1


test_files=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_report.py"
)

for test_file in "${test_files[@]}"; do
    pipenv run pytest "$test_file"
done
