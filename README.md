# rhosocial-activerecord-sqlserver ($\rho_{\mathbf{AR}\text{-sqlserver}}$)

[![PyPI version](https://badge.fury.io/py/rhosocial-activerecord-sqlserver.svg)](https://badge.fury.io/py/rhosocial-activerecord-sqlserver)
[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-sqlserver.svg)](https://pypi.org/project/rhosocial-activerecord-sqlserver/)
[![Tests](https://github.com/rhosocial/python-activerecord-sqlserver/actions/workflows/test.yml/badge.svg)](https://github.com/rhosocial/python-activerecord-sqlserver/actions)
[![Coverage Status](https://codecov.io/gh/rhosocial/python-activerecord-sqlserver/branch/main/graph/badge.svg)](https://app.codecov.io/gh/rhosocial/python-activerecord-sqlserver/tree/main)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-sqlserver.svg)](https://github.com/rhosocial/python-activerecord-sqlserver/blob/main/LICENSE)
[![Powered by vistart](https://img.shields.io/badge/Powered_by-vistart-blue.svg)](https://github.com/vistart)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>SQL Server Backend for rhosocial-activerecord</h3>
    <p><b>T-SQL Support · Enterprise Features · Sync & Async</b></p>
</div>

> **Note**: This is a backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It cannot be used standalone.

## Why This Backend?

### 1. SQL Server-Specific Optimizations

| Feature | This Backend | Generic Solutions |
|---------|-------------|-------------------|
| **RETURNING/OUTPUT** | Native `OUTPUT` clause | Manual SELECT-after-write |
| **Temporal Tables** | `FOR SYSTEM_TIME` | Application-level audit logs |
| **Partitioning** | `PARTITION` schemes/functions | Manual sharding |
| **Sequences** | Native `CREATE SEQUENCE` | Identity/application counters |

### 2. True Sync-Async Parity

Same API surface for both sync and async operations:

```python
# Sync
users = User.query().where(User.c.age >= 18).all()

# Async - just add await
users = await User.query().where(User.c.age >= 18).all()
```

### 3. Built for Production

- **Connection pooling** with configurable pool sizes
- **Transaction support** with proper isolation levels
- **Error mapping** from SQL Server error codes to Python exceptions
- **Type adapters** for SQL Server-specific data types

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-sqlserver
```

### Basic Usage

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from typing import Optional

class User(ActiveRecord):
    __table_name__ = "users"
    id: Optional[int] = None
    name: str
    email: str

# Configure
config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="YourStrong!Passw0rd"
)
User.configure(config, SQLServerBackend)

# Use
user = User(name="Alice", email="alice@example.com")
user.save()

# Query with parameter binding
results = User.query().where("email = ?", ("alice@example.com",)).all()
```

> 💡 **AI Prompt**: "How do I configure connection pooling for SQL Server?"

## SQL Server-Specific Features

### OUTPUT / RETURNING

Retrieve inserted or updated rows with the `OUTPUT` clause:

```python
# INSERT with OUTPUT
user = User(name="Alice", email="alice@example.com")
user.save()
print(user.id)  # Populated automatically via OUTPUT
```

### Temporal Tables

Query historical state with `FOR SYSTEM_TIME`:

```python
# As of a specific time
User.query().where(
    "user_id = ? FOR SYSTEM_TIME AS OF ?",
    (1, "2026-06-30T12:00:00"),
).all()
```

### Partitioned Tables

SQL Server partition schemes and functions:

```python
# Partitioned table DDL support
class Orders(ActiveRecord):
    __table_name__ = "orders"
    __partition__ = {
        "column": "order_date",
        "scheme": "ps_order_date",
    }
    order_id: int
    order_date: datetime
```

### Sequences

Native sequence support:

```python
# Use a sequence-backed column
class Ticket(ActiveRecord):
    __table_name__ = "tickets"
    ticket_no: int  # NEXT VALUE FOR ticket_seq
```

## Requirements

- **Python**: 3.9+ (including 3.13t/3.14t free-threaded builds)
- **Core**: `rhosocial-activerecord>=1.0.0`
- **Driver**: `pyodbc>=5.0.0` (with ODBC Driver 17+ for SQL Server)

## SQL Server Version Compatibility

| Feature | Min Version | Notes |
|---------|-------------|-------|
| Basic operations | 2017+ | Core functionality |
| Temporal tables | 2016+ | `FOR SYSTEM_TIME` |
| Sequences | 2012+ | `CREATE SEQUENCE` |
| Partitioning | 2008+ | Partition functions/schemes |
| Columnstore indexes | 2014+ | Analytics acceleration |
| Memory-optimized tables | 2014+ | In-memory OLTP |
| PIVOT/UNPIVOT | 2005+ | Row-to-column transforms |
| OUTPUT clause | 2005+ | RETURNING equivalent |
| JSON functions | 2016+ | `JSON_VALUE`, `JSON_QUERY` |
| STRING_AGG | 2017+ | String aggregation |
| UTF-8 collation | 2019+ | `_UTF8` collations |

**Recommended**: SQL Server 2019+ for optimal feature support.

## Get Started with AI Code Agents

This project supports AI-assisted development. Clone and open in your preferred tool:

```bash
git clone https://github.com/rhosocial/python-activerecord-sqlserver.git
cd python-activerecord-sqlserver
```

### Example AI Prompts

- "How do I configure connection pooling for SQL Server?"
- "Show me how to use temporal tables"
- "How do I use the OUTPUT clause with INSERT?"
- "Create a model with a partitioned table"

### For Any LLM

Feed the documentation files in `docs/` to your preferred LLM for context-aware assistance.

## Testing

> ⚠️ **CRITICAL**: Tests MUST run serially. Do NOT use `pytest -n auto` or parallel execution.

```bash
# Run all tests
PYTHONPATH=src pytest tests/

# Run specific feature tests
PYTHONPATH=src pytest tests/rhosocial/activerecord_sqlserver_test/feature/basic/
PYTHONPATH=src pytest tests/rhosocial/activerecord_sqlserver_test/feature/query/
```

See the [Testing Documentation](https://github.com/rhosocial/python-activerecord/blob/main/.claude/testing.md) for details.

## Documentation

- **[Getting Started](docs/en_US/getting_started/)** — Installation and configuration
- **[SQL Server Features](docs/en_US/sqlserver_specific_features/)** — SQL Server-specific capabilities
- **[Type Adapters](docs/en_US/type_adapters/)** — Data type handling
- **[Transaction Support](docs/en_US/transaction_support/)** — Transaction management

## Comparison with Other Backends

| Feature | SQL Server | PostgreSQL | SQLite |
|---------|-----------|------------|--------|
| **RETURNING** | ✅ OUTPUT | ✅ RETURNING | ✅ RETURNING |
| **Temporal Tables** | ✅ | ❌ | ❌ |
| **Sequences** | ✅ Native | ✅ Native | ⚠️ Emulated |
| **Arrays** | ❌ | ✅ Native | ❌ |
| **JSON Type** | ⚠️ Functions only | ✅ JSONB | ⚠️ JSON1 extension |

> 💡 **AI Prompt**: "When should I choose SQL Server over PostgreSQL for my project?"

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-sqlserver">GitHub</a> · <a href="https://docs.python-activerecord.dev.rho.social/backends/sqlserver.html">Documentation</a> · <a href="https://pypi.org/project/rhosocial-activerecord-sqlserver/">PyPI</a></p>
</div>