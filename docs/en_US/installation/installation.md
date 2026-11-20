# Installation

## Package

```bash
pip install rhosocial-activerecord-sqlserver
```

The package installs into the `rhosocial.activerecord.backend.impl.sqlserver`
namespace. It depends on `pyodbc >= 5.3.0` and a compatible release of the core
`rhosocial-activerecord` library. When developing against a local checkout of a
sibling package, install it by explicit local path rather than relying on a
published version from an index, so that the editable source tree is the one
actually imported.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python | 3.9 or newer |
| SQL Server | 2017, 2019, 2022 or 2025 |
| ODBC driver | Microsoft ODBC Driver 17 or 18 for SQL Server, installed on the client |
| `pyodbc` | `>= 5.3.0`, installed as a dependency |

The ODBC driver is a **system** component, not a Python package: `pyodbc` only
loads it by name. Verify that the driver is present before debugging Python
code — an incorrect or missing driver name is the most common connection
failure. On the connection config the default is `ODBC Driver 17 for SQL
Server`; override `driver` if you installed Driver 18. See
[Connection configuration](configuration.md).

### Async support

The sync backend uses `pyodbc`. For `AsyncSQLServerBackend`, install the async
extra, which pulls in `aioodbc`:

```bash
pip install "rhosocial-activerecord-sqlserver[async]"
```

## Verify the install

A syntax-and-import check needs no database:

```bash
python -c "from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend; print(SQLServerBackend)"
python -c "from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig; print(SQLServerConnectionConfig)"
```

To confirm the driver name your machine can actually load:

```python
import pyodbc
print(pyodbc.drivers())  # look for "ODBC Driver 17/18 for SQL Server"
```

## Next steps

- [Connection configuration](configuration.md) — authentication, encryption, timeouts, pooling
- [Quick start](../getting_started/quick_start.md) — a declarative model end to end
