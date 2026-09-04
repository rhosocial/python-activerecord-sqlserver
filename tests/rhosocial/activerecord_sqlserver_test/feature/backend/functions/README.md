# functions tests

SQL Server function coverage: supports_functions() factories, JSON function protocol with version detection (2016+) and real-database JSON function integration, plus the niladic CURRENT_TIMESTAMP form (no NOW()/CURRENT_DATE).

## Key files

- `test_dialect_function_support.py` — SQLFunctionSupport protocol conformance
- `test_functions.py` — function factories
- `test_json_functions.py` — JSON function protocol
- `test_json_functions_backend.py` — JSON functions on a live server
- `test_niladic_functions.py` — niladic forms
