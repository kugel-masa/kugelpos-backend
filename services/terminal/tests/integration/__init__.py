# Copyright 2026 masa@kugel
#
# Integration test placeholder for terminal service.
#
# Tests here will run against a real MongoDB but mock outbound HTTP calls
# (account, master-data, cart, report, journal, stock) via respx, and use
# httpx ASGITransport to drive terminal's FastAPI app in-process.
#
# As of this commit no tests live here yet — terminal's existing live
# tests stay under tests/e2e/. Tests will be promoted from e2e to
# integration as the in-process + respx pattern is rolled out per-flow.
