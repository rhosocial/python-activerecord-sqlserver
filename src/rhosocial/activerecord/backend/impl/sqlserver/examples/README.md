# SQL Server Backend Examples

This directory contains example code demonstrating how to use the rhosocial-activerecord expressions with the SQL Server backend.

## Directory Structure

```
examples/
├── README.md               # This file
├── connection/             # Connection examples
│   ├── __init__.py
│   └── quickstart.py       # Quick start guide - connect, query, result handling
├── ddl/                    # Data Definition Language examples
│   ├── __init__.py
│   ├── create_table.py     # Create table with columns and constraints
│   └── create_index.py     # Create index on existing table
├── insert/                 # INSERT operation examples
│   ├── __init__.py
│   ├── with_output.py      # Insert with OUTPUT clause (SQL Server's RETURNING)
│   └── batch.py            # Batch insert multiple rows
├── query/                  # Query (SELECT) examples
│   ├── __init__.py
│   ├── basic.py            # Basic SELECT with WHERE, ORDER BY, OFFSET FETCH
│   └── join.py             # JOIN multiple tables (including CROSS APPLY)
├── transaction/            # Transaction control examples
│   ├── __init__.py
│   └── basic.py            # Basic transaction with context manager
└── types/                  # Type-related examples
    ├── __init__.py
    └── json_basic.py       # JSON operations (SQL Server 2016+)
```

## Example File Format

Each example file follows this structure:

```python
"""
[Title and description of what this example demonstrates.]
"""

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
# Database connection setup code
# Don't copy this when learning the pattern

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
# Core code demonstrating the expression usage
# Copy this part when applying to your project

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
# Execute the expression against the backend
# This can be included or omitted depending on needs

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
# Cleanup code
# Don't copy this when learning the pattern
```

## Key Principles

1. **Self-contained**: Each example file can be executed independently
2. **Clear sections**: Setup/Teardown are clearly marked as reference only
3. **Pure business logic**: The core expression usage is clean and copyable
4. **No external dependencies**: All setup is within the file itself
5. **Expression-based**: All SQL is generated via expressions, no raw SQL

## SQL Server Specific Features

- **OUTPUT clause**: SQL Server uses OUTPUT instead of RETURNING
- **OFFSET FETCH**: Pagination syntax (SQL Server 2012+)
- **IDENTITY**: Auto-increment columns
- **CROSS APPLY/OUTER APPLY**: Alternative to LATERAL JOIN
- **MERGE**: Native upsert support
- **SNAPSHOT isolation**: MVCC-like isolation level

## Environment Variables

Examples use these environment variables with defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLSERVER_HOST` | `localhost` | Server hostname |
| `SQLSERVER_PORT` | `1433` | Server port |
| `SQLSERVER_DATABASE` | `test_db` | Database name |
| `SQLSERVER_USERNAME` | `sa` | Username |
| `SQLSERVER_PASSWORD` | `""` | Password |
| `SQLSERVER_DRIVER` | `ODBC Driver 17 for SQL Server` | ODBC driver |
| `SQLSERVER_ENCRYPT` | `false` | Encrypt connection |
| `SQLSERVER_TRUST_SERVER_CERTIFICATE` | `true` | Trust server certificate |

## Running Examples

```bash
# Set environment variables (optional)
export SQLSERVER_HOST=localhost
export SQLSERVER_PORT=1433
export SQLSERVER_DATABASE=test_db
export SQLSERVER_USERNAME=sa
export SQLSERVER_PASSWORD=YourPassword

# Run a specific example
python -m rhosocial.activerecord.backend.impl.sqlserver.examples.ddl.create_table
```

## For LLM Context

When using these examples as reference:
- Focus on the **SECTION: Business Logic** portion
- The Setup and Teardown sections are boilerplate for execution only
- Copy the business logic pattern to your own project
- All SQL is expression-based, following the Expression-Dialect architecture
