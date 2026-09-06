# SQL Server 方言表达式

## 概述

SQL Server 提供了自己的 SQL 方言，包含 T-SQL 扩展。

## JSON 函数

### JSON_VALUE

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal, FunctionCall

# 获取 JSON 值
func = FunctionCall(dialect, "JSON_VALUE", Column(dialect, "attributes"), Literal(dialect, "$.brand"))
sql, params = func.to_sql()
# sql: JSON_VALUE(attributes, %s)
# params: ('$.brand',)
```

### FOR JSON

```python
# 将结果作为 JSON 返回
# SELECT * FROM users FOR JSON PATH
```

## OUTPUT 子句

SQL Server 支持 DML 操作的 OUTPUT 子句：

```python
# INSERT with OUTPUT
# INSERT INTO users (name) OUTPUT inserted.id VALUES ('John')

# DELETE with OUTPUT
# DELETE FROM users OUTPUT deleted.* WHERE id = 1
```

## 公用表表达式 (CTE)

```python
# CTE 支持
# WITH cte AS (SELECT * FROM users) SELECT * FROM cte
```

## 另请参阅

- [字段类型](./field_types.md) — SQL Server 数据类型
- [索引](./indexing.md) — 索引类型

💡 *AI 提示：* "SQL Server 的 T-SQL 与标准 SQL 有何不同？"
