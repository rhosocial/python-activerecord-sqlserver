# SQL Server Dialect Expressions

## Overview

SQL Server provides its own SQL dialect with T-SQL extensions.

## JSON Functions

### JSON_VALUE

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal, FunctionCall

# Get JSON value
func = FunctionCall(dialect, "JSON_VALUE", Column(dialect, "attributes"), Literal(dialect, "$.brand"))
sql, params = func.to_sql()
# sql: JSON_VALUE(attributes, %s)
# params: ('$.brand',)
```

### FOR JSON

```python
# Return results as JSON
# SELECT * FROM users FOR JSON PATH
```

## Output Clause

SQL Server supports OUTPUT clause for DML operations:

```python
# INSERT with OUTPUT
# INSERT INTO users (name) OUTPUT inserted.id VALUES ('John')

# DELETE with OUTPUT
# DELETE FROM users OUTPUT deleted.* WHERE id = 1
```

## Common Table Expressions (CTE)

```python
# CTE support
# WITH cte AS (SELECT * FROM users) SELECT * FROM cte
```

## See Also

- [Field Types](./field_types.md) — SQL Server data types
- [Indexing](./indexing.md) — Index types

💡 *AI Prompt:* "How does SQL Server's T-SQL differ from standard SQL?"
