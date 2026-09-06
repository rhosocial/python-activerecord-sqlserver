# Test Configuration

## Overview

This section describes how to configure the testing environment for the SQL Server backend.

For general testing strategies (DummyBackend, SQLite integration testing), see the [Core Backend Testing Guide](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/testing/backend_testing.md).

## End-to-End Testing with SQL Server Backend

For complete SQL Server behavior testing, use the SQL Server backend:

```python
import os
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig


class User(ActiveRecord):
    name: str
    email: str

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'


# Read configuration from environment variables
config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', 1433)),
    database=os.environ.get('SQLSERVER_DATABASE', 'test'),
    username=os.environ.get('SQLSERVER_USER', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', ''),
    trust_server_certificate=True,  # Development only
)
User.configure(config, SQLServerBackend)
```

## Test Fixtures

```python
import pytest
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig


@pytest.fixture
def sqlserver_config():
    return SQLServerConnectionConfig(
        host='localhost',
        port=1433,
        database='test',
        username='sa',
        password='Password123!',
        trust_server_certificate=True,
    )


@pytest.fixture
def sqlserver_backend(sqlserver_config):
    backend = SQLServerBackend(connection_config=sqlserver_config)
    backend.connect()
    yield backend
    backend.disconnect()


def test_connection(sqlserver_backend):
    version = sqlserver_backend.get_server_version()
    assert version is not None
```

## Scenario-Based Configuration

The SQL Server test suite uses YAML scenario files that map to running SQL Server instances:

```yaml
# tests/config/sqlserver_scenarios.yaml
scenarios:
  sqlserver_2019:
    host: localhost
    port: 11433
    username: sa
    password: Password123!
    trust_server_certificate: true

  sqlserver_2022:
    host: localhost
    port: 11434
    username: sa
    password: Password123!
    trust_server_certificate: true

  sqlserver_2025:
    host: localhost
    port: 11435
    username: sa
    password: Password123!
    trust_server_certificate: true
```

Set `SQLSERVER_SCENARIOS_CONFIG_PATH` to point at the scenario file, or it defaults to `tests/config/sqlserver_scenarios.yaml`.

## Testing Notes

- **Tests MUST run serially** — do NOT use `pytest -n auto` or parallel execution
- SQL Server uses `?` as the parameter placeholder (pyodbc convention)
- The `SQLServerUnicodeDialect` renders VARCHAR/CHAR as NVARCHAR/NCHAR for test compatibility with Unicode test data

💡 *AI Prompt:* "What is the difference between unit tests, integration tests, and end-to-end tests?"
