# 性能问题

## 概述

本节介绍 SQL Server 的性能问题及优化方法。

## 慢查询分析

### 使用 SQL Server Profiler / 扩展事件

SQL Server 使用扩展事件（而不是 MySQL 的慢查询日志）进行查询监控：

```sql
-- 创建扩展事件会话以捕获慢查询
CREATE EVENT SESSION slow_queries ON SERVER
ADD EVENT sqlserver.sql_statement_completed
WHERE duration > 1000000  -- 1 秒（微秒）
ADD TARGET package0.ring_buffer;
```

### 使用 EXPLAIN 分析查询

后端提供 `ExplainExpression` 类来生成执行计划语句。**不要执行原始 EXPLAIN SQL** —— 请使用表达式系统：

```python
from rhosocial.activerecord.backend.expression.statements.explain import (
    ExplainExpression,
    ExplainOptions,
    ExplainFormat,
)

# 构建查询表达式
query = User.query().where(User.c.name == "Tom").select(User.c.id, User.c.name)

# 基本 EXPLAIN
explain = ExplainExpression(dialect, statement=query)
sql, params = explain.to_sql()
# sql: SET SHOWPLAN_ALL ON ...

# 带 JSON 格式的 EXPLAIN（JSON 执行计划）
explain_json = ExplainExpression(
    dialect,
    statement=query,
    options=ExplainOptions(format=ExplainFormat.JSON),
)
```

## 常见性能问题

### 1. 缺少索引

SQL Server 默认在主键上创建**聚集**索引，并可创建**非聚集**索引：

```sql
-- 添加非聚集索引
CREATE NONCLUSTERED INDEX idx_name ON [users] ([name]);
```

使用后端的索引支持——参见[索引](../backend_specific_features/indexing.md)。

### 2. SELECT *

```python
# 避免 SELECT *，只查询所需列
users = User.query().select(User.c.id, User.c.name).all()
```

### 3. N+1 查询问题

使用 `with_()` 预加载关联数据以避免 N+1 查询：

```python
# 预加载关联的 posts
users = User.query().with_('posts').all()

# 加载嵌套关联
users = User.query().with_('posts.comments').all()

# 使用查询修饰符加载
users = User.query().with_(('posts', lambda q: q.top(5))).all()
```

### 4. NVARCHAR 与 VARCHAR

使用错误的字符串类型会导致隐式转换和索引失效：

| 关注点 | 建议 |
|---------|----------------|
| Unicode 文本 | 使用 `NVARCHAR`（方言默认使用 NVARCHAR） |
| 非 Unicode、仅 ASCII | `VARCHAR` 没问题且更紧凑 |
| 隐式转换 | 避免比较 NVARCHAR 和 VARCHAR 列——会强制扫描 |

### 5. 参数嗅探

SQL Server 根据第一个参数值缓存查询计划。对于值变化很大的参数，使用 `OPTION (RECOMPILE)` 或查询提示。

## 连接超时

```python
config = SQLServerConnectionConfig(
    timeout=30,
    query_timeout=60,
)
```

## 另请参阅

- [索引](../backend_specific_features/indexing.md) — 聚集/非聚集索引
- [EXPLAIN](../backend_specific_features/explain.md) — 执行计划分析

💡 *AI 提示词：* "如何优化 SQL Server 查询性能？"
