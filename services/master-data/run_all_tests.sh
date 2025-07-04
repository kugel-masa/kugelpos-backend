#!/bin/bash
export PIPENV_IGNORE_VIRTUALENVS=1


tests=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_operations.py"
)

for test in "${tests[@]}"; do
    pipenv run pytest "$test"
done
