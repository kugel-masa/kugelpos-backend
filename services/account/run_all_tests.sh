#!/bin/bash
export PIPENV_IGNORE_VIRTUALENVS=1

for test_file in \
    tests/test_clean_data.py \
    tests/test_setup_data.py \
    tests/test_health.py \
    tests/test_operations.py
do
    pipenv run pytest $test_file -s -v
done
