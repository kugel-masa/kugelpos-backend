#!/bin/bash
export PIPENV_IGNORE_VIRTUALENVS=1


for test_file in \
    tests/test_clean_data.py \
    tests/test_setup_data.py \
    tests/test_health.py \
    tests/test_cart.py \
    tests/test_void_return.py \
    tests/test_transaction_status_repository.py \
    tests/test_tran_service_status.py \
    tests/test_payment_cashless_error.py
do
    pipenv run pytest $test_file
done
