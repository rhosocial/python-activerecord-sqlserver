# rhosocial-activerecord SQL Server Backend Documentation

> 🤖 **AI Learning Assistant**: Key concepts in this documentation are marked
> with 💡 AI Prompt. When you encounter concepts you don't understand, you can
> ask the AI assistant directly.

> **Example:** "Why does this backend gate SQL Graph on the server version, and
> how do I preview the T-SQL before it runs?"

> 📖 **Scope**: These pages describe **this backend only** — where SQL Server
> differs, what it supports, and how it is configured and tested. The
> ActiveRecord model, field and query-building contract belongs to the
> [core library documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US)
> and is not repeated here.

## Table of Contents

1. **[Introduction](introduction/README.md)**
    * **[Backend overview](introduction/README.md)**: what this backend is, how it is layered, and when to use it
    * **[Relationship with the core library](introduction/README.md#relationship-with-the-core-library)**: what the backend adds and what stays in core
    * **[Supported versions](introduction/README.md#supported-versions)**: SQL Server 2017 / 2019 / 2022 / 2025; Python 3.9+

2. **[Installation & Configuration](installation/installation.md)**
    * **[Installation](installation/installation.md)**: `pip` install, `pyodbc` and the ODBC driver
    * **[Connection configuration](installation/configuration.md)**: host, port, database, authentication, driver
    * **[Encryption & certificates](installation/configuration.md#encryption--tls)**: `encrypt`, `trust_server_certificate`, client certificates
    * **[Timeouts & connection pool](installation/configuration.md#timeouts--connection-pool)**: connection/query timeouts and ODBC pooling

3. **[Getting Started](getting_started/quick_start.md)**
    * **[Quick start](getting_started/quick_start.md)**: a declarative model end to end
    * **[Runnable examples](../examples/README.md)**: connection, DDL and introspection scripts

4. **[Modeling](modeling/field_types.md)**
    * **[SQL Server field types](modeling/field_types.md)**: `NVARCHAR`, `NCHAR`, `NVARCHAR(MAX)`, `VARBINARY`, `XML`, `UNIQUEIDENTIFIER`, `BIT`, `TINYINT` and more

5. **[DDL Operations](ddl/create_table.md)**
    * **[Creating tables](ddl/create_table.md)**: models to tables, IDENTITY, constraints and indexes
    * **[Partitioning](ddl/partition.md)**: functions, schemes, `SPLIT`/`MERGE`/`SWITCH` and the maintenance helper
    * **[Advanced objects](ddl/advanced_objects.md)**: temporal tables, SQL Graph, columnstore, memory-optimized tables and sequences

6. **[Migrations](migration/README.md)**
    * **[Migrations on SQL Server](migration/README.md)**: backend configuration, transactional DDL, version gating and CLI wiring (the system itself is in the core docs)
    * **[Migration examples](../examples/migration/README.md)**: function-style and class-style examples using this backend

7. **[Querying](querying/output_and_merge.md)**
    * **[OUTPUT and RETURNING](querying/output_and_merge.md)**: returning affected rows from DML
    * **[MERGE and pagination](querying/output_and_merge.md#merge-and-pagination)**: upsert, `OFFSET ... FETCH`, hints

8. **[Transaction Support](transactions/README.md)**
    * **[Isolation levels](transactions/README.md#isolation-levels)**: including `SNAPSHOT`
    * **[Savepoints](transactions/README.md#savepoints)**: nested transactions via `SAVE TRANSACTION`
    * **[Deadlocks & retries](transactions/README.md#deadlocks-and-retries)**: error mapping and retry guidance

9. **[Introspection](introspection/README.md)**
    * **[Database introspection](introspection/README.md)**: catalogue sources, capability answers, operational and data families, CLI types

10. **[Capabilities](capabilities/README.md)**
    * **[Capability gates](capabilities/README.md)**: how `supports_*` switches and version floors work
    * **[Version floor reference](capabilities/README.md#version-floor-reference)**: which feature appears on which server

11. **[Command Line](cli/README.md)**
    * **[CLI usage](cli/README.md)**: `info`, `query`, `status` and `introspect`

12. **[Testing](testing/README.md)**
    * **[Test configuration](testing/README.md)**: PYTHONPATH, provider registration, local SQL Server via Docker
    * **[Local scope](testing/README.md#local-test-scope)**: targeted checks only; full matrix on CI

> 📖 **Core Library Documentation**: To learn about the complete ActiveRecord
> framework, refer to [rhosocial-activerecord documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US).
