# backend tests

SQLServerBackend process-level behavior: real-database backend tests, offline mixin validation (deadlock priority, SET LANGUAGE / DATEFORMAT, identity queries), async error-class handling, connection configuration and connection resilience (ping reconnect, network interruption, shared backends).

## Key files

- `test_backend.py` — backend integration (sync/async)
- `test_backend_mixin_validation.py` — mixin validation branches (offline)
- `test_config.py` — connection configuration
- `test_connection_resilience.py` — reconnect and interruption scenarios
- `test_backend_error_handling_async.py` — async error classes (sync twin pending, Tier-2)
