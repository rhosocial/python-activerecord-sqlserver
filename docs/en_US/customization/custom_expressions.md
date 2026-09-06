# Custom Expressions

## Overview

The SQL Server backend extends core expression classes with T-SQL-specific SQL syntax. You can create new expression types to add support for SQL Server-unique SQL constructs.

## Expression Design Principles

Expressions are **declarative** — they collect all parameters and delegate SQL generation to the dialect:

```python
class MyExpression(BaseExpression):
    def __init__(self, dialect, **params):
        self.dialect = dialect
        self.params = params

    def to_sql(self, dialect):
        # Delegate to dialect for SQL generation
        return dialect.format_my_expression(**self.params)
```

## Creating Custom Expressions

### Step 1: Define the Expression Class

```python
from rhosocial.activerecord.backend.expression.base import BaseExpression

class SQLServerJSONValueExpression(BaseExpression):
    """T-SQL expression for the JSON_VALUE function."""

    def __init__(self, dialect, column, path):
        self.dialect = dialect
        self.column = column
        self.path = path

    def to_sql(self, dialect):
        col_sql, _ = self.column.to_sql()
        return f"JSON_VALUE({col_sql}, ?)", (self.path,)
```

### Step 2: Register with the Dialect

```python
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

class CustomSQLServerDialect(SQLServerDialect):
    def format_json_value(self, column, path):
        return f"JSON_VALUE({column}, ?)"
```

### Step 3: Use in Code

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal, FunctionCall

# Prefer the built-in FunctionCall helper for functions
func = FunctionCall(dialect, "JSON_VALUE", Column(dialect, "attributes"), Literal(dialect, "$.brand"))
sql, params = func.to_sql()
# sql: JSON_VALUE([attributes], ?)
# params: ('$.brand',)
```

## Operator Mixins

Use operator mixins for common comparison and arithmetic operations:

```python
from rhosocial.activerecord.backend.expression.operators import ComparisonMixin, ArithmeticMixin

class MyExpression(ComparisonMixin, ArithmeticMixin, BaseExpression):
    pass

# Now supports ==, !=, <, >, +, -, *, /, etc.
expr = MyExpression(dialect, Column(dialect, "amount")) > 100
sql, params = expr.to_sql()
# sql: [amount] > ?
# params: (100,)
```

## Serialization

Expressions support serialization/deserialization for caching and logging:

```python
# Serialize
data = expr.serialize()

# Deserialize
expr = BaseExpression.deserialize(data)
```

## See Also

- [Core Expression System](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/expression) — expression base classes and operators
- [SQL Server Dialect](../backend_specific_features/dialect.md) — T-SQL-specific SQL functions

💡 *AI Prompt:* "How do I create a custom expression for a T-SQL function not in the expression library?"
