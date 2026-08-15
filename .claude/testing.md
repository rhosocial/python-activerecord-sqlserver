# Testing Guide - python-activerecord-sqlserver

> SQL Server backend implementation for rhosocial-activerecord

## Project-Specific Information

| Item | Value |
|------|-------|
| **Python Version** | 3.8+ |
| **Database Driver** | pyodbc |
| **Free-Threading Support** | ✅ Yes |

## Dependencies

```toml
dependencies = [
    "pyodbc>=5.3.0",
    "rhosocial-activerecord"
]
```

## Quick Test Commands

```bash
cd /mnt/i/GitHubRepositories/rhosocial/python-activerecord-sqlserver
source .venv/bin/activate
export PYTHONPATH=src
pytest tests/ -v
```

## Key Differences from Core

- Uses SQL Server-specific dialect in `src/rhosocial/activerecord/backend/impl/sqlserver/dialect.py`
- Schema files in `tests/rhosocial/activerecord_sqlserver_test/`
- Provider implementation in `tests/providers/`

## Reference

- [Core testing guide](../python-activerecord/.claude/testing.md)
- [SQL Server backend development](../python-activerecord/.claude/backend_development.md)