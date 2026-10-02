# rhosocial-activerecord SQL Server Backend Documentation

The SQL Server backend is the Microsoft SQL Server backend implementation for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It uses the
`pyodbc` driver and brings the ActiveRecord pattern to SQL Server, whose identifier
naming follows the two-part `<schema>.<object>` rule.

## Table of Contents

- **[Schema Namespaces](sqlserver_specific_features/schema_namespace.md)**: declaring
  `__schema_name__`, the DDL `schema_name` parameter, the two-part column reference rule,
  aliasing, `SCHEMA_NAME()`, `DEFAULT_SCHEMA`, and partition scheme placement

## Key facts at a glance

| Question | Answer |
|---|---|
| What does `schema_name` mean? | A schema within the current database |
| Qualified table renders as | `[app].[orders]` |
| Column references | At most two parts: `[orders].[id]` — the schema is **not** repeated on the column |
| After an alias | `[o].[id]` — the alias replaces both the schema and the table |
| Current schema | `SCHEMA_NAME()` (the parentheses are required) |
| `CREATE SCHEMA` / `DROP SCHEMA` | Supported |
| `IF [NOT] EXISTS` / `CASCADE` on schema DDL | Not supported |

## Related documentation

- **[Schema Namespaces (core guide)](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)**:
  the dialect-independent rules that every backend shares

---

> ⚠️ **Dependency note**: this backend depends on the core library
> `rhosocial-activerecord`. Install it together with the core library rather than
> independently.