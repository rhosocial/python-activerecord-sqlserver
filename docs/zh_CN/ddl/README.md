# DDL 操作

## 概述

本节介绍 SQL Server 后端的 DDL（数据定义语言）操作。DDL 定义数据库架构——表、索引、视图和其他对象。

**重要**：rhosocial-activerecord 中的所有 DDL 都是**基于表达式**的。你在 Python 中定义架构，框架生成 SQL，然后通过后端执行。下面的示例使用 `ActiveRecord` 以保持简洁，但 `AsyncActiveRecord` 的工作方式完全相同——DDL 生成是纯计算，不涉及 I/O。

DDL 章节分为两部分：

1. **后端 DDL 能力** — SQL Server 后端支持的完整 DDL 操作集，通过后端特定表达式类表示。
2. **ActiveRecord DDL 派生** — 框架可以从模型类声明自动生成的内容。

---

# 第一部分：后端 DDL 能力

SQL Server 后端支持以下 DDL 操作：

## 支持的操作

| 操作 | SQL Server 支持 | 表达式类 |
|------|----------------|---------|
| CREATE TABLE | ✅ | `CreateTableExpression` |
| ALTER TABLE | ✅ | `AlterTableExpression` |
| DROP TABLE | ✅ | `DropTableExpression` |
| CREATE INDEX | ✅ | `CreateIndexExpression` |
| DROP INDEX | ✅ | `DropIndexExpression` |
| CREATE VIEW | ✅ | `CreateViewExpression` |
| DROP VIEW | ✅ | `DropViewExpression` |
| TRUNCATE | ✅ | `TruncateExpression` |
| CREATE SCHEMA | ✅ | `CreateSchemaExpression` |
| CREATE SEQUENCE | ✅ | `CreateSequenceExpression` |
| CREATE PROCEDURE | ✅ | `SQLServerCreateProcedureExpression` |
| CREATE FUNCTION | ✅ | `SQLServerCreateFunctionExpression` |
| CREATE TRIGGER | ✅ | `SQLServerCreateTriggerExpression` |
| CREATE FULLTEXT CATALOG | ✅ | `SQLServerCreateFullTextCatalogExpression` |
| CREATE FULLTEXT INDEX | ✅ | `SQLServerCreateFullTextIndexExpression` |

## SQL Server 特定表选项

SQL Server 支持几个其他后端不可用的表选项：

- `WITH (MEMORY_OPTIMIZED=ON)` 用于内存 OLTP
- `ON partition_scheme` 用于分区表
- `TEXTIMAGE_ON` 用于大对象存储

## CREATE INDEX

### 索引类型

| 后端 | 支持的索引类型 |
|------|---------------|
| SQLite | 仅 B-tree |
| MySQL | BTREE、HASH |
| PostgreSQL | BTREE、HASH、GIN、GiST、SP-GiST、BRIN |
| SQL Server | CLUSTERED、NONCLUSTERED、COLUMNSTORE、FULLTEXT、SPATIAL |

### 并发索引创建

| 后端 | CONCURRENTLY 支持 |
|------|------------------|
| SQLite | 否 |
| MySQL | 否 |
| PostgreSQL | 是 |
| SQL Server | 是（ONLINE 选项） |

### 全文索引

| 后端 | 全文索引语法 |
|------|-------------|
| SQLite | FTS5 虚拟表 |
| MySQL | `FULLTEXT INDEX`（InnoDB，MySQL 5.6+） |
| PostgreSQL | GIN 索引 on `tsvector` 列 |
| SQL Server | `CREATE FULLTEXT INDEX`（独立目录） |

## 序列

| 后端 | 序列 | AUTO_INCREMENT 机制 |
|------|------|-------------------|
| SQLite | 否 | `INTEGER PRIMARY KEY` 上的 `AUTOINCREMENT` |
| MySQL | 否 | `AUTO_INCREMENT` 列属性 |
| PostgreSQL | 是（`SERIAL`、`IDENTITY`） | `SERIAL` 或 `GENERATED ... AS IDENTITY` |
| SQL Server | 是（`CREATE SEQUENCE`） | `IDENTITY(1,1)` 或 `SEQUENCE` + `NEXT VALUE FOR` |

## 分区

| 后端 | 分区 | 策略 |
|------|------|------|
| SQLite | **否** | — |
| MySQL | 是（5.1+） | RANGE、LIST、HASH、KEY、COLUMNS、子分区 |
| PostgreSQL | 是（PG 10+） | RANGE、LIST、HASH |
| SQL Server | 是（2008+） | RANGE、LIST、HASH（通过分区方案/函数） |

> **注意**：分区 DDL 未集成到模型声明层中。你必须直接使用后端特定表达式类。详见[分区](../backend_specific_features/partition.md)。

## SQL Server 特定表达式类

| 表达式 | 用途 |
|--------|------|
| `SQLServerCreateProcedureExpression` | 使用 T-SQL 语法的 CREATE PROCEDURE |
| `SQLServerCreateFunctionExpression` | 使用 T-SQL 语法的 CREATE FUNCTION |
| `SQLServerCreateTriggerExpression` | 使用 INSERTED/DELETED 表的 CREATE TRIGGER |
| `SQLServerCreateFullTextCatalogExpression` | CREATE FULLTEXT CATALOG |
| `SQLServerCreateFullTextIndexExpression` | CREATE FULLTEXT INDEX |
| `SQLServerColumnstoreIndexExpression` | 列存储索引 DDL |
| `SQLServerDropRoutineExpression` | DROP PROCEDURE/FUNCTION |
| `SQLServerDropTriggerExpression` | DROP TRIGGER |

---

# 第二部分：ActiveRecord DDL 派生

`ModelSchemaGenerator` 从 ActiveRecord 模型声明派生 DDL。你在模型类上定义字段、表名、索引和约束——框架生成 SQL。

## 可以从模型派生的内容

| 功能 | 模型集成 | 使用方式 |
|------|---------|---------|
| 表创建 | 是 | `ModelSchemaGenerator.generate_create_table()` |
| 列定义 | 是 | 在模型类上声明字段 |
| 索引 | 是 | `indexes()` 类方法 |
| 约束 | 是 | `UseConstraint` 注解 |
| 架构 | 是 | `schema()` 类方法 |
| 分区 | **否** | 仅后端特定表达式类 |
| 序列 | **否** | 仅后端特定表达式类 |
| 触发器 | **否** | 仅后端特定表达式类 |
| 存储过程 | **否** | 仅后端特定表达式类 |

## 创建表

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from typing import ClassVar

class User(ActiveRecord):
    id: int | None = None
    username: str
    email: str
    age: int
    is_active: bool = True
    metadata: dict = {}

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

SQL Server 生成的 SQL：

```sql
CREATE TABLE IF NOT EXISTS [users] (
    [id] INT NOT NULL IDENTITY(1,1),
    [username] NVARCHAR(255) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [age] INT NOT NULL,
    [is_active] BIT NOT NULL DEFAULT 1,
    [metadata] NVARCHAR(MAX),
    PRIMARY KEY ([id])
)
```

与其他后端的区别：
- **SQL Server**：使用 `IDENTITY(1,1)` 自增，`NVARCHAR` 存储字符串，`BIT` 存储布尔值，`NVARCHAR(MAX)` 存储 JSON
- **MySQL**：使用 `AUTO_INCREMENT`，`VARCHAR`，`BOOLEAN`，`JSON`
- **PostgreSQL**：使用 `SERIAL`，`VARCHAR`，`BOOLEAN`，`JSONB`

💡 *AI 提示词：* "SQL Server 和 PostgreSQL 的 DDL 生成有什么区别？"
