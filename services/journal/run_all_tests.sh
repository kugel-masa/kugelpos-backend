#!/bin/bash
export PIPENV_IGNORE_VIRTUALENVS=1


test_files=(
    "tests/test_clean_data.py" #HACK: Commented out to avoid running this test
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_journal.py"
)

for test_file in "${test_files[@]}"; do
    pipenv run pytest "$test_file"
done
