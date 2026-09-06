# Supported Versions

## SQL Server Version Support

| SQL Server Version | Support Status | Notes |
|--------------------|----------------|-------|
| SQL Server 2016 | ✅ Supported | Introduced native JSON support |
| SQL Server 2017 | ✅ Supported | |
| SQL Server 2019 | ✅ Supported | Version tuple (15, 0, 0) |
| SQL Server 2022 | ✅ Recommended | Current mainstream version (16, 0, 0) |
| SQL Server 2025 | ✅ Supported | Latest version (17, 0, 0) |
| Azure SQL Database | ✅ Supported | Compatible with the 2022 feature set |

> **Important**: This backend is designed exclusively for Microsoft SQL Server. The dialect behavior is tightly coupled with T-SQL version-specific features. The dialect adapts to the actual server version at connection time via `SERVERPROPERTY('ProductVersion')`.

## Version-Specific Feature Detection

The dialect adjusts its behavior based on the detected server version:

| Feature | Minimum Version |
|---------|-----------------|
| CTEs (recursive) | 2008 |
| MERGE statement | 2008 |
| Window functions (enhanced) | 2012 |
| `OFFSET ... FETCH` pagination | 2012 |
| Columnstore indexes | 2012+ |
| Native JSON functions | 2016 |
| `APPROX_COUNT_DISTINCT` | 2019 |
| `JSON_OBJECT` / `JSON_ARRAY` | 2022 |
| Bitwise functions (new) | 2022 |

## Python Version Requirements

| Python Version | Support Status | Notes |
|----------------|----------------|-------|
| 3.9 | ✅ Supported | |
| 3.10 | ✅ Supported | |
| 3.11 | ✅ Supported | |
| 3.12 | ✅ Supported | |
| 3.13 | ✅ Supported | |
| 3.14 | ✅ Supported | |

## Dependency Requirements

| Dependency | Version | Notes |
|-----------|---------|-------|
| rhosocial-activerecord | >=1.0.0.dev0,<2.0.0 | Core library |
| pyodbc | >=5.3.0 | SQL Server driver (required) |
| aioodbc | >=0.5.0 | Async driver (optional, for async support) |
| ODBC Driver for SQL Server | 17 or 18 | System-level ODBC driver (required) |

⚠️ **Note**: SQL Server access requires a system-level ODBC driver in addition to the `pyodbc` Python package.

💡 *AI Prompt:* "What are the differences between SQL Server 2019 and 2022 that affect SQL generation?"
