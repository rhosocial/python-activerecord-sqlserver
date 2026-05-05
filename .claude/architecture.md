# Architecture Guide - python-activerecord-sqlserver

> SQL Server backend implementation for rhosocial-activerecord

## Project Overview

| Item | Value |
|------|-------|
| **Database** | Microsoft SQL Server |
| **Python Driver** | pyodbc |
| **Python Version** | 3.8+ |

## Directory Structure

```
python-activerecord-sqlserver/
├── src/rhosocial/activerecord/backend/impl/sqlserver/
│   ├── __init__.py           # Backend initialization
│   ├── __main__.py           # CLI entry point
│   ├── backend.py            # Sync backend implementation
│   ├── async_backend.py      # Async backend implementation
│   ├── config.py             # Configuration
│   ├── dialect.py            # SQL Server dialect
│   ├── protocols.py          # Protocol definitions
│   ├── transaction.py        # Transaction management
│   ├── adapters.py           # Type adapters
│   ├── mixins.py             # SQL Server-specific mixins
│   ├── types.py              # SQL Server-specific types
│   ├── cli/                  # CLI commands
│   │   ├── connection.py
│   │   ├── info.py
│   │   ├── introspect.py
│   │   ├── named_connection.py
│   │   ├── named_procedure.py
│   │   ├── named_query.py
│   │   ├── output.py
│   │   ├── query.py
│   │   └── status.py
│   ├── expression/           # SQL Server-specific expressions
│   │   └── locking.py        # Locking expressions (FOR UPDATE)
│   ├── functions/            # SQL Server-specific functions
│   ├── introspection/         # Schema introspection
│   └── show/                 # SHOW statements
├── tests/
│   └── rhosocial/activerecord_sqlserver_test/
└── pyproject.toml
```

## SQL Server-Specific Features

- **TABLESAMPLE**: Table sampling for large datasets
- **PIVOT/UNPOT**: Pivot and unpivot queries
- **OUTPUT clause**: Returning modified data
- **HierarchyId**: Hierarchical data support
- **JSON support**: JSON functions and indexes

## Expression-Dialect System

Like all backends, SQL Server uses the Expression-Dialect separation:
- Expression classes define query structure
- Dialect classes handle SQL generation

SQL Server-specific expressions in `expression/` directory.

## Reference

- [Core architecture](../python-activerecord/.claude/architecture.md)
- [Backend development guide](../python-activerecord/.claude/backend_development.md)