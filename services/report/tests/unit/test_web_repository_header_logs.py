# Copyright 2026 masa@kugel
"""The report service's own header logging (issue #211).

`HttpClientHelper` masks the headers it is handed, but these repositories
build the headers themselves and log them before handing them over - so
masking the shared client left the credential in `app.log` on this side. The
values are the terminal's api_key, the caller's bearer token, and the
service-to-service token, each of which IS the credential rather than a
reference to one.
"""

import inspect

from app.models.repositories import category_master_web_repository, terminal_info_web_repository


def test_the_terminal_repository_does_not_print_its_credential():
    source = inspect.getsource(terminal_info_web_repository)
    assert "headers: {headers}" not in source, "the X-API-KEY / bearer header is logged verbatim"
    assert "mask_sensitive_data(headers)" in source


def test_the_terminal_repository_does_not_print_the_response_whole():
    # The answer carries the terminal's api_key and its staff's plaintext pin,
    # so masking only the outgoing header left the credential in the log a few
    # lines later. Both the list and the single-terminal read.
    source = inspect.getsource(terminal_info_web_repository)
    assert 'logger.debug(f"response: {response_data}")' not in source, (
        "the terminal response is logged raw, api_key and staff pin included"
    )
    assert source.count("mask_sensitive_data(response_data)") == 2


def test_the_category_repository_does_not_print_its_service_token():
    source = inspect.getsource(category_master_web_repository)
    assert "Request headers: {headers}" not in source, "the service token is logged verbatim"
    assert "mask_sensitive_data(headers)" in source
