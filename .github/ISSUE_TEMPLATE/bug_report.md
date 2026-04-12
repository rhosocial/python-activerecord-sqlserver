---
name: Bug Report
about: Report a bug in rhosocial ActiveRecord SQL Server Backend
title: '[SQLSERVER-BUG] '
labels: 'bug, sqlserver'
assignees: ''
---

## Before Submitting

Please ensure this bug is specific to the SQL Server backend implementation. If the issue occurs across all backends (involving ActiveRecord/ActiveQuery functionality), please submit the issue at https://github.com/rhosocial/python-activerecord/issues instead.

## Description

A clear and concise description of the bug in the SQL Server backend.

## Environment

- **rhosocial ActiveRecord SQL Server Version**: [e.g. 1.0.0.dev1]
- **rhosocial ActiveRecord Core Version**: [e.g. 1.0.0.dev13]
- **Python Version**: [e.g. 3.13]
- **SQL Server Version**: [e.g. 2019, 2022, Azure SQL]
- **pyodbc Driver Version**: [e.g. 5.0.0]
- **OS**: [e.g. Linux, macOS, Windows]

## Steps to Reproduce

1.
2.
3.

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

What actually happened instead of the expected behavior.

## Database Query

If applicable, provide the generated SQL query that causes the issue:

```sql
-- Your problematic SQL query here
```

## Model Definition

If the issue is related to a specific model, please share your model definition:

```python
# Example model definition
class User(ActiveRecord):
    __table_name__ = 'users'

    id: Optional[int] = None
    name: str
    email: EmailStr
```

## SQL Server-Specific Configuration

Any SQL Server-specific configuration that might be relevant:

```python
config = SQLServerConnectionConfig(
    host='localhost',
    port=1433,
    database='test',
    username='user',
    password='password',
    driver='ODBC Driver 18 for SQL Server',
    # Add your specific options here
)
```

## Error Details

If you're getting an error, include the full error message and stack trace:

```
Paste the full error message here
```

## Additional Context

Any other context about the problem here.
