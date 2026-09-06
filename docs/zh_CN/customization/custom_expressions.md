# 自定义表达式

## 概述

SQL Server 后端通过 T-SQL 特定语法扩展了核心表达式类。你可以创建新的表达式类型来为 SQL Server 特有的 SQL 结构添加支持。

## 表达式设计原则

表达式是**声明式**的——它们收集所有参数并将 SQL 生成委托给方言：

```python
class MyExpression(BaseExpression):
    def __init__(self, dialect, **params):
        self.dialect = dialect
        self.params = params

    def to_sql(self, dialect):
        # 委托给方言生成 SQL
        return dialect.format_my_expression(**self.params)
```

## 创建自定义表达式

### 步骤 1：定义表达式类

```python
from rhosocial.activerecord.backend.expression.base import BaseExpression

class SQLServerJSONValueExpression(BaseExpression):
    """用于 JSON_VALUE 函数的 T-SQL 表达式。"""

    def __init__(self, dialect, column, path):
        self.dialect = dialect
        self.column = column
        self.path = path

    def to_sql(self, dialect):
        col_sql, _ = self.column.to_sql()
        return f"JSON_VALUE({col_sql}, ?)", (self.path,)
```

### 步骤 2：注册到方言

```python
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

class CustomSQLServerDialect(SQLServerDialect):
    def format_json_value(self, column, path):
        return f"JSON_VALUE({column}, ?)"
```

### 步骤 3：在代码中使用

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal, FunctionCall

# 优先使用内置的 FunctionCall 辅助类来处理函数
func = FunctionCall(dialect, "JSON_VALUE", Column(dialect, "attributes"), Literal(dialect, "$.brand"))
sql, params = func.to_sql()
# sql: JSON_VALUE([attributes], ?)
# params: ('$.brand',)
```

## 运算符 Mixin

使用运算符 mixin 进行常见的比较和算术操作：

```python
from rhosocial.activerecord.backend.expression.operators import ComparisonMixin, ArithmeticMixin

class MyExpression(ComparisonMixin, ArithmeticMixin, BaseExpression):
    pass

# 现在支持 ==, !=, <, >, +, -, *, / 等
expr = MyExpression(dialect, Column(dialect, "amount")) > 100
sql, params = expr.to_sql()
# sql: [amount] > ?
# params: (100,)
```

## 序列化

表达式支持序列化/反序列化，用于缓存和日志记录：

```python
# 序列化
data = expr.serialize()

# 反序列化
expr = BaseExpression.deserialize(data)
```

## 另请参阅

- [核心表达式系统](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/expression) — 表达式基类和运算符
- [SQL Server 方言](../backend_specific_features/dialect.md) — T-SQL 特定 SQL 函数

💡 *AI 提示词：* "如何为表达式库中没有的 T-SQL 函数创建自定义表达式？"
