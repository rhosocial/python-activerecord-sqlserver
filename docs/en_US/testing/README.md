# Testing

This section covers testing for the sqlserver backend.

## Contents

- [Test Configuration](configuration.md): SQL Server-specific test setup
- [Local Testing](local.md): Docker-based local test environment

## Testing Principles

### Sync/Async Parity

All backends with IO operations must prepare **paired sync and async tests** for equivalent scenarios:

```python
# Sync test
def test_create_user():
    user = User(name="Alice").create()
    assert user.id is not None

# Async test — same logic, async API
async def test_async_create_user():
    user = await AsyncUser(name="Alice").create()
    assert user.id is not None
```

If a backend only supports sync or only async, prepare the corresponding tests only.

### Expression Classes — No IO

Expression tests involve no database IO — they only build SQL and validate the generated SQL:

```python
def test_expression_sql():
    expr = Eq(User.name, "Alice")
    assert expr.to_sql(dialect) == "[name] = ?"
    assert expr.params == ["Alice"]
```

No async counterpart is needed for expression tests.

### ActiveRecord Tests — Use Testsuite

ActiveRecord feature tests (model CRUD, relationships, queries) use the **testsuite**:

```
python-activerecord-testsuite/
└── src/rhosocial/activerecord/testsuite/feature/
    ├── basic/      # Level 1 — must pass first
    ├── relation/   # Level 1 — must pass first
    ├── query/      # Level 1 — must pass first
    ├── events/     # Level 2 — extended behaviors
    ├── mixins/     # Level 2
    ├── interface/  # Level 2
    └── examples/   # Level 2
```

Each backend provides **provider implementations** that wire the tests to its specific database. The test logic is shared; only the provider layer changes per backend.

**Running testsuite tests:**

```bash
cd python-activerecord-sqlserver
PYTHONPATH=tests .venv3.14-ubuntu26.04/bin/pytest \
    ../python-activerecord-testsuite/src/rhosocial/activerecord/testsuite/feature/relation/
```

**Provider responsibilities:** See the [Core Testsuite Provider Guide](provider_guide.md).

### Test Categories Summary

| What to Test | Approach | IO? | Async? |
|-------------|----------|-----|--------|
| Expression classes (dialect SQL generation) | Unit tests, no DB | No | No |
| Type adapters (type conversion) | Unit tests, no DB | No | No |
| Named features (connection, expression, procedure, migration) | Backend CLI scripts | Yes | If supported |
| ActiveRecord features (CRUD, relations, queries) | Testsuite + provider | Yes | Yes |
| Backend-specific features (unique types, syntax) | Project-specific tests | Yes | Yes |

### SQL Server Testing Notes

- **Tests MUST run serially** — do NOT use `pytest -n auto` or parallel execution
- SQL Server uses `?` as parameter placeholder (pyodbc convention)
- The `SQLServerUnicodeDialect` renders VARCHAR/CHAR as NVARCHAR/NCHAR for test compatibility with Unicode test data

## Provider Responsibilities

For provider implementation guidelines, see the [Core Testsuite Provider Guide](provider_guide.md).

## General Testing Strategies

For DummyBackend usage and three-tier testing strategy, see the [Core Backend Testing Guide](backend_testing.md).

## See Also

- [Core Backend Testing Guide](backend_testing.md)
- [Core Testsuite Provider Guide](provider_guide.md)
