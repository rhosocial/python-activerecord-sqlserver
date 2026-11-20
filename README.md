<!-- README.md -->
# rhosocial-activerecord-sqlserver ($\rho_{\mathbf{AR}\text{-sqlserver}}$)

[![PyPI version](https://badge.fury.io/py/rhosocial-activerecord-sqlserver.svg)](https://badge.fury.io/py/rhosocial-activerecord-sqlserver)
[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-sqlserver.svg)](https://pypi.org/project/rhosocial-activerecord-sqlserver/)
[![Tests](https://github.com/rhosocial/python-activerecord-sqlserver/actions/workflows/test.yml/badge.svg)](https://github.com/rhosocial/python-activerecord-sqlserver/actions)
[![Coverage Status](https://codecov.io/gh/rhosocial/python-activerecord-sqlserver/branch/main/graph/badge.svg)](https://app.codecov.io/gh/rhosocial/python-activerecord-sqlserver/tree/main)
[![Supported SQL Server versions](https://img.shields.io/badge/SQLServer-2017%7C2019%7C2022%7C2025-blue?logo=microsoftsqlserver)](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-sqlserver.svg)](https://github.com/rhosocial/python-activerecord-sqlserver/blob/main/LICENSE)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>SQL Server Backend for rhosocial-activerecord</h3>
    <p><b>OUTPUT clause · Temporal tables · SQL Graph · Sync &amp; async</b></p>
</div>

This is the Microsoft SQL Server backend for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It cannot be used standalone.

**Keywords:** sql-server, mssql, odbc, pyodbc, orm, activerecord, pydantic, python, async, type-safe

## Why This Project?

SQL Server is a mainstay of enterprise data platforms, yet working with it usually means hand-writing T-SQL or adopting an ORM that hides the database. This backend brings the same small, intuitive ActiveRecord API — a class is a table, an instance is a row — to SQL Server, with full type safety and native sync–async parity.

It speaks SQL Server on its own terms. DML that returns affected rows uses the `OUTPUT` clause, temporal queries use `FOR SYSTEM_TIME`, and capabilities such as SQL Graph, memory-optimized tables and columnstore appear only on the server versions that support them. You keep one consistent API and still see the exact T-SQL through `.to_sql()` before anything runs.

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-sqlserver
```

Requires Python 3.9+, `pyodbc>=5.3.0`, an installed ODBC Driver 17+ and a reachable SQL Server instance.

### End-to-End Example

```python
"""Save as demo.py and run with: python demo.py"""
from typing import Annotated, ClassVar

from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.expression.types import VarCharType
from rhosocial.activerecord.field import DefaultTimestampMixin, IntegerPKMixin
from rhosocial.activerecord.model import ActiveRecord


class User(IntegerPKMixin, DefaultTimestampMixin, ActiveRecord):
    name: Annotated[str, UseSqlType(VarCharType(length=100))]
    email: Annotated[str, UseSqlType(VarCharType(length=255))]
    age: int = 0

    c: ClassVar[FieldProxy] = FieldProxy()  # enables User.c.<field> expressions

    @classmethod
    def table_name(cls) -> str:
        return "users"


# Configure the backend and create the table from the model declaration
User.configure(
    SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="myapp",
        username="sa",
        password="YourStrong!Passw0rd",
        driver="ODBC Driver 17 for SQL Server",
    ),
    SQLServerBackend,
)
User.create_table()

# Create
alice = User(name="Alice", email="alice@example.com", age=30)
alice.save()
print(alice.id)  # database-assigned integer primary key

# Query with type-safe expressions
adults = User.query().where(User.c.age >= 18).all()
print([user.name for user in adults])

# Inspect the generated SQL without executing it
sql, params = User.query().where(User.c.age >= 18).to_sql()
print(sql, params)  # SELECT ... FROM [users] WHERE [users].[age] >= ?   (18,)
```

> **Async parity:** use `AsyncActiveRecord` with `AsyncSQLServerBackend` — same method names, same patterns, just add `await`.

## Project Architecture

Models and field proxies are declared once against the core `ActiveRecord` API; this backend binds them to SQL Server's dialect and the `pyodbc` driver. Query structure and T-SQL generation are decoupled: nothing is rendered until an explicit `.to_sql()` call, so you can preview and verify every statement before it runs. The sync (`SQLServerBackend`) and async (`AsyncSQLServerBackend`) implementations are native and share the same method names.

For the full picture, start with the [core library documentation](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md).

**SQL Server highlights.** `OUTPUT` for returning affected rows, `FOR SYSTEM_TIME` for temporal tables, SQL Graph, memory-optimized and columnstore tables, and version-gated features. See [Database introspection](docs/introspection.md) and [Table partitioning](docs/partition.md) for the SQL Server-specific details.

## Backend Support & Progress

This package supports SQL Server **2017, 2019, 2022 and 2025**. Capabilities are gated by the detected server version, so a feature appears only where the server supports it (for example SQL Graph from 2017 and `columnstore_order` from 2022). Connectivity uses `pyodbc` with an installed ODBC Driver 17+.

It ships as a separate package from the core `rhosocial-activerecord` library; add it to any project using that library and configure models with `SQLServerBackend`. The core library and its documentation describe ActiveRecord itself.

> **⚠️ Development Stage:** This project is under active development. APIs may change, and some features are not yet production-ready.

## Contributing, License, Links

### Contributing

We welcome contributions! Please see [CONTRIBUTING.md](https://github.com/rhosocial/python-activerecord/blob/main/CONTRIBUTING.md) for guidelines.

### License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

### Documentation

* **[Core library documentation](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md)** — the full documentation table of contents
* **[Database introspection](docs/introspection.md)** — what this backend answers, where each answer comes from, and the version floors that decide whether it can be asked
* **[Table partitioning](docs/partition.md)** — SQL Server's function/scheme model, DDL expressions and the maintenance helper
* **[Backend architecture notes](.claude/architecture.md)** and **[testing notes](.claude/testing.md)** — backend-specific design and test setup

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-sqlserver">GitHub</a> · <a href="https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md">Documentation</a> · <a href="https://pypi.org/project/rhosocial-activerecord-sqlserver/">PyPI</a></p>
</div>
