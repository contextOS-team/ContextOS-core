# Deferred Items - Phase 07.2

## Pre-existing Test Failures (Out of Scope)

1. **test_integration.py::test_health_with_real_db** - `AttributeError: 'function' object has no attribute 'cache_clear'` - The `get_settings` function was monkey-patched during a prior fixture, losing its `lru_cache` wrapper. Pre-existing before 07.2.

2. **test_linear_sync.py::TestGraphQLClient::test_graphql_client_sends_auth_header** - Test asserts `"lin_api_test_token"` but production code now sends `"Bearer lin_api_test_token"` after 07.2-01 fix. The test assertion needs updating to match the corrected Bearer prefix behavior. Likely should be addressed in 07.2-03 or a follow-up.
