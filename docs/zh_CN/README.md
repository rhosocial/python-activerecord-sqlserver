# rhosocial-activerecord SQL Server 后端文档

SQL Server 后端是 [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord)
的 Microsoft SQL Server 后端实现。它使用 `pyodbc` 驱动，将 ActiveRecord 模式带入
SQL Server，并适配 SQL Server 以 `<schema>.<object>` 两段式标识符为核心的命名规则。

## 目录 (Table of Contents)

- **[Schema 命名空间](sqlserver_specific_features/schema_namespace.md)**：声明
  `__schema_name__`、DDL 的 `schema_name` 参数、列引用最多两段的规则、别名处理、
  `SCHEMA_NAME()`、`DEFAULT_SCHEMA`，以及分区方案所在 schema 的约束

## 关键结论速览

| 问题 | 结论 |
|---|---|
| `schema_name` 指什么？ | 当前 database 内的某个 schema |
| 限定表渲染为 | `[app].[orders]` |
| 列引用 | 最多两段：`[orders].[id]`，**schema 不会重复出现在列上** |
| 取别名之后 | `[o].[id]`，别名同时取代 schema 与表名 |
| 当前 schema | `SCHEMA_NAME()`，括号不可省略 |
| `CREATE SCHEMA` / `DROP SCHEMA` | 支持 |
| schema DDL 的 `IF [NOT] EXISTS` / `CASCADE` | 不支持 |

## 相关文档

- **[Schema 命名空间（核心库指南）](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)**：
  所有后端共同遵循的、与方言无关的规则

---

> ⚠️ **依赖说明**：本后端依赖核心库 `rhosocial-activerecord`，请与核心库一并安装，
> 不要单独安装本后端。