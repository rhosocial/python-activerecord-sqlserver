# Backend Overview

`rhosocial-activerecord-sqlserver` is the Microsoft SQL Server backend for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It
binds the framework's ActiveRecord models and query builder to SQL Server's
dialect and to the `pyodbc` driver. It cannot be used standalone — it is an
add-on to the core library.

The backend speaks SQL Server on its own terms instead of flattening it to a
lowest-common-denominator SQL: DML that returns affected rows uses `OUTPUT`,
temporal queries use `FOR SYSTEM_TIME`, schema objects are named with
`[...]-quoted identifiers, and server-specific features (SQL Graph,
memory-optimized tables, columnstore, partitioning) appear only on the versions
that support them. You keep a single API and can still preview the exact T-SQL
through `.to_sql()` before anything runs.

> 💡 *AI prompt: "What does it mean that this backend renders native T-SQL rather than portable SQL? How can I see the statement before it is executed?"*

## Design principles

1. **Backend implementation** — extends the core Expression–Dialect–Backend
   layering with SQL Server-specific dialect, expressions, types, adapters and
   mixins. Query structure is built as expression nodes; the dialect renders
   them to T-SQL only when `.to_sql()` is called.
2. **Driver** — uses `pyodbc` for connectivity. Async support is provided by
   `aioodbc` through `AsyncSQLServerBackend`, with the same method names as the
   sync backend (add `await`).
3. **Namespace package** — installs under
   `rhosocial.activerecord.backend.impl.sqlserver` as part of the core library's
   PEP 420 namespace.
4. **Capability negotiation** — a broad set of `supports_*` switches, many of
   them version-gated against the connected server, decide whether a feature
   can be rendered. See [Capability gates](../capabilities/README.md).

## Relationship with the core library

The core library owns the ActiveRecord abstraction: declaring a `Model`, its
fields and mixins, defining relations, building queries and expressions, and
the introspection/partition *contracts*. This backend owns the SQL Server side
of those contracts:

| Concern | Core library | This backend |
|---------|--------------|--------------|
| Model declaration, fields, mixins, relations | ✅ | — (reused as-is) |
| Query builder and expression nodes | ✅ | SQL Server expression subclasses and dialect rendering |
| Native type mapping | core type classes | `SQLServer*Type` variants (e.g. `SQLServerNVarCharType`) and adapters |
| Connection configuration | `ConnectionConfig` base | `SQLServerConnectionConfig` (ODBC string, auth, encryption) |
| CRUD / DDL / DML execution | backend protocol | `SQLServerBackend` / `AsyncSQLServerBackend` |
| Introspection contract and result types | ✅ | catalogue queries against `sys.*` / `INFORMATION_SCHEMA`, capability answers |
| Partitioning contract, plan and retention protocol | ✅ | `SQLServerPartitionPlan`, `SQLServerPartitionMaintenance`, partition expressions |
| Transactions | `TransactionManager` | `SQLServerTransactionManager` (SNAPSHOT, savepoints) |

A declarative model is written once against core's `ActiveRecord` API and then
bound to this backend. See [Quick start](../getting_started/quick_start.md) and
the [runnable examples](../../examples/README.md).

## Supported versions

| Item | Value |
|------|-------|
| SQL Server | **2017, 2019, 2022, 2025** (tested in CI) |
| Python | **3.9+** (see `pyproject.toml`) |
| Driver | `pyodbc >= 5.3.0`; ODBC Driver **17+** (18 recommended) |
| Core library | `rhosocial-activerecord >= 1.0.0.dev30, < 2.0.0` |

Version detection happens at connect time. `backend.introspect_and_adapt()`
refreshes the detected version so version-gated probes answer for the server
actually reached, rather than for a construction-time assumption. The backend's
internal floor constants reach back to 2005 for a few legacy capabilities, but
the releases this repository tests against are 2017–2025, all of which are past
the relevant gates. The capability chapter lists the floors that matter in
practice.

> ⚠️ **Development stage**: this package is under active development. APIs may
> change and some features are not yet production-ready.

## Where to go next

- [Installation and configuration](../installation/installation.md)
- [Quick start with a declarative model](../getting_started/quick_start.md)
- [SQL Server-specific field types](../modeling/field_types.md)
- [Database introspection](../introspection/README.md)
