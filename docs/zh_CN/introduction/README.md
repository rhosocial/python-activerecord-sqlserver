# 简介

## SQL Server 后端概述

`rhosocial-activerecord-sqlserver` 是 rhosocial-activerecord 核心库的 Microsoft SQL Server 数据库后端实现。它提供了完整的 ActiveRecord 模式支持，专门针对 SQL Server 特性进行了优化，包括 T-SQL 语法、OUTPUT 子句、时态表和企业级功能。

## 同步与异步

SQL Server 后端同时提供同步与异步两套 API，两者在功能上完全对等。本文档后续章节将以同步方式举例说明，异步 API 的使用方式与同步版本一致，只需将方法调用替换为对应的异步版本即可。

### 命名约定

框架在所有后端之间使用一致的命名约定：

| 组件 | 同步 | 异步 |
|------|------|------|
| 后端类 | `SQLServerBackend` | `AsyncSQLServerBackend` |
| 事务管理器 | `SQLServerTransactionManager` | `AsyncSQLServerTransactionManager` |
| 连接配置 | `SQLServerConnectionConfig` | `SQLServerConnectionConfig`（共享） |
| 方言 | `SQLServerDialect` | `SQLServerDialect`（共享） |

连接配置和方言在同步和异步之间共享——它们是纯数据对象，不是活动连接。

### 模型层

模型层提供两个基类，方法名相同但调用约定不同：

| 操作 | `ActiveRecord`（同步） | `AsyncActiveRecord`（异步） |
|------|----------------------|----------------------------|
| 查找单个 | `find_one()` | `async find_one()` |
| 查找全部 | `find_all()` | `async find_all()` |
| 保存 | `save()` | `async save()` |
| 删除 | `delete()` | `async delete()` |
| 查询构建器 | `.query()` → `ActiveQuery` | `.query()` → `AsyncActiveQuery` |

方法名**完全相同**——没有 `a` 前缀约定。区别在于类级别，而非方法级别。

### 配置

```python
# 同步
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

class User(ActiveRecord):
    ...

User.configure(SQLServerConnectionConfig(...), SQLServerBackend)
user = User.find_one(1)

# 异步
from rhosocial.activerecord.model import AsyncActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

class User(AsyncActiveRecord):
    ...

User.configure(SQLServerConnectionConfig(...), AsyncSQLServerBackend)
user = await User.find_one(1)
```

### 异步驱动要求

SQL Server 使用 `pyodbc` 进行同步访问，使用 `aioodbc` 进行异步访问：

| 后端 | 同步驱动 | 异步驱动 | 说明 |
|------|---------|---------|------|
| SQL Server | `pyodbc` | `aioodbc` | pyodbc 的独立异步包装器 |

**重要**：异步组件是懒加载的，以避免在仅使用同步 API 时需要 `aioodbc`。如果导入 `AsyncSQLServerBackend` 而未安装 `aioodbc`，将在导入时收到 `ImportError`。

安装异步支持：

```bash
pip install rhosocial-activerecord-sqlserver[async]
# 或
pip install aioodbc
```

## 快速链接

- **[与核心库的关系](./relationship.md)**：了解 sqlserver 后端如何与核心库协同工作
- **[支持版本](./supported_versions.md)**：查看支持的 SQL Server、Python 和依赖版本

## 已知限制和特殊行为

每个数据库都有自己不同于 SQL 标准的行为。本节记录了可能令你惊讶的 SQL Server 特定特殊行为。

| 特殊行为 | 描述 |
|---------|------|
| @@IDENTITY vs SCOPE_IDENTITY() | 后端使用 SCOPE_IDENTITY() 以避免触发器生成值的问题 |
| OUTPUT 子句 | SQL Server 使用 OUTPUT 而非 RETURNING 来获取 DML 结果 |
| OFFSET FETCH 需要 2012+ | 2012 之前的版本需要 ROW_NUMBER() 进行分页 |
| SET NOCOUNT ON | 启用时，cursor.rowcount 可能返回 -1 |
| NVARCHAR vs VARCHAR | NVARCHAR 存储 Unicode；VARCHAR 不存储。方言默认使用 NVARCHAR 以兼容测试 |
| GO 批分隔符 | SQL Server 脚本使用 GO 作为批分隔符，而非分号 |
| TOP 代替 LIMIT | SQL Server 使用 TOP N 语法代替 LIMIT N |
| MERGE 用于 UPSERT | SQL Server 使用 MERGE 进行 upsert 操作，而非 ON CONFLICT |
| 无 TRUNCATE CASCADE | TRUNCATE 不支持 CASCADE 选项 |
| 无部分索引 | SQL Server 不支持索引上的 WHERE 子句部分索引 |

💡 *AI 提示词：* "什么是 ActiveRecord 模式？与 DataMapper 模式有什么区别？"
